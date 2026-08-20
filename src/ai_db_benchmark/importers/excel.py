from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple
from zipfile import ZipFile
import xml.etree.ElementTree as ET


SPREADSHEET_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}


@dataclass(frozen=True)
class SheetPreview:
    name: str
    dimension: str
    row_count: int
    column_count: int
    columns: List[str]
    samples: List[List[object]]


@dataclass(frozen=True)
class WorkbookTable:
    name: str
    columns: List[str]
    rows: List[Dict[str, object]]


def preview_workbook(path: Path, sample_rows: int = 2) -> List[SheetPreview]:
    if not path.exists():
        raise FileNotFoundError(path)
    with ZipFile(path) as workbook:
        shared_strings = _shared_strings(workbook)
        sheets = _sheet_targets(workbook)
        return [
            _preview_sheet(workbook, sheet_name, target, shared_strings, sample_rows)
            for sheet_name, target in sheets
        ]


def load_workbook_tables(path: Path) -> List[WorkbookTable]:
    if not path.exists():
        raise FileNotFoundError(path)
    with ZipFile(path) as workbook:
        shared_strings = _shared_strings(workbook)
        tables: List[WorkbookTable] = []
        for sheet_name, target in _sheet_targets(workbook):
            rows = _read_sheet_rows(workbook, target, shared_strings)
            if not rows:
                tables.append(WorkbookTable(name=sheet_name, columns=[], rows=[]))
                continue
            columns = [str(value).strip() for value in rows[0]]
            records: List[Dict[str, object]] = []
            for row in rows[1:]:
                padded = _pad_row(row, len(columns))
                records.append(dict(zip(columns, padded)))
            tables.append(WorkbookTable(name=sheet_name, columns=columns, rows=records))
        return tables


def _shared_strings(workbook: ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    values: List[str] = []
    for item in root.findall("a:si", SPREADSHEET_NS):
        values.append("".join(text.text or "" for text in item.findall(".//a:t", SPREADSHEET_NS)))
    return values


def _sheet_targets(workbook: ZipFile) -> List[Tuple[str, str]]:
    root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    relmap = {
        rel.attrib["Id"]: _normalise_target(rel.attrib["Target"])
        for rel in rels.findall("rel:Relationship", REL_NS)
    }
    targets: List[Tuple[str, str]] = []
    for sheet in root.findall("a:sheets/a:sheet", SPREADSHEET_NS):
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        targets.append((sheet.attrib["name"], relmap[rel_id]))
    return targets


def _normalise_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return str(PurePosixPath("xl") / target)


def _preview_sheet(
    workbook: ZipFile,
    name: str,
    target: str,
    shared_strings: List[str],
    sample_rows: int,
) -> SheetPreview:
    root = ET.fromstring(workbook.read(target))
    dimension_node = root.find("a:dimension", SPREADSHEET_NS)
    dimension = dimension_node.attrib.get("ref", "unknown") if dimension_node is not None else "unknown"
    row_count = _row_count_from_dimension(dimension)
    rows = _rows_from_root(root, shared_strings, limit=sample_rows + 1)
    columns = [str(value) for value in rows[0]] if rows else []
    return SheetPreview(
        name=name,
        dimension=dimension,
        row_count=row_count,
        column_count=len(columns),
        columns=columns,
        samples=rows[1:],
    )


def _read_sheet_rows(workbook: ZipFile, target: str, shared_strings: List[str]) -> List[List[object]]:
    root = ET.fromstring(workbook.read(target))
    return _rows_from_root(root, shared_strings)


def _rows_from_root(
    root: ET.Element,
    shared_strings: List[str],
    limit: Optional[int] = None,
) -> List[List[object]]:
    rows: List[List[object]] = []
    row_nodes: Iterable[ET.Element] = root.findall("a:sheetData/a:row", SPREADSHEET_NS)
    for index, row in enumerate(row_nodes):
        if limit is not None and index >= limit:
            break
        values: List[object] = []
        for cell in row.findall("a:c", SPREADSHEET_NS):
            ref = cell.attrib.get("r", "")
            column_index = _cell_column_index(ref)
            while len(values) < column_index:
                values.append("")
            values.append(_cell_value(cell, shared_strings))
        rows.append(values)
    return rows


def _pad_row(row: List[object], width: int) -> List[object]:
    if len(row) >= width:
        return row[:width]
    return row + [""] * (width - len(row))


def _cell_column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha()).upper()
    if not letters:
        return 0
    value = 0
    for character in letters:
        value = value * 26 + (ord(character) - ord("A") + 1)
    return max(0, value - 1)


def _cell_value(cell: ET.Element, shared_strings: List[str]) -> object:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("a:v", SPREADSHEET_NS)
    inline_node = cell.find("a:is", SPREADSHEET_NS)
    if cell_type == "s" and value_node is not None:
        return shared_strings[int(value_node.text or "0")]
    if cell_type == "inlineStr" and inline_node is not None:
        return "".join(text.text or "" for text in inline_node.findall(".//a:t", SPREADSHEET_NS))
    if value_node is None:
        return ""
    value = value_node.text or ""
    if cell_type == "b":
        return value == "1"
    return _numeric_or_text(value)


def _numeric_or_text(value: str) -> object:
    try:
        number = float(value)
    except ValueError:
        return value
    if number.is_integer():
        return int(number)
    return number


def _row_count_from_dimension(dimension: str) -> int:
    if ":" not in dimension:
        return 0
    end = dimension.split(":", 1)[1]
    digits = "".join(character for character in end if character.isdigit())
    if not digits:
        return 0
    return max(0, int(digits) - 1)
