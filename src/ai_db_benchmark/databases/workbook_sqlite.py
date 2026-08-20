from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import sqlite3
from typing import Dict, Iterable, List, Mapping, Sequence

from ai_db_benchmark.importers.excel import WorkbookTable, load_workbook_tables


@dataclass(frozen=True)
class WorkbookImportResult:
    database_path: Path
    source_path: Path
    source_sha256: str
    table_counts: Dict[str, int]


def import_workbook_to_sqlite(
    workbook_path: Path,
    database_path: Path,
    replace: bool = True,
) -> WorkbookImportResult:
    tables = load_workbook_tables(workbook_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if replace and database_path.exists():
        database_path.unlink()

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=OFF")
        table_counts: Dict[str, int] = {}
        for table in tables:
            table_name = sanitize_identifier(table.name)
            column_names = unique_identifiers(table.columns)
            _create_table(connection, table_name, column_names, table.rows)
            _insert_rows(connection, table_name, table.columns, column_names, table.rows)
            table_counts[table_name] = len(table.rows)
        _create_indexes(connection, table_counts)
        _record_import_metadata(connection, workbook_path, source_sha256(workbook_path), table_counts)
        connection.commit()

    return WorkbookImportResult(
        database_path=database_path,
        source_path=workbook_path,
        source_sha256=source_sha256(workbook_path),
        table_counts=table_counts,
    )


def sanitize_identifier(value: str) -> str:
    identifier = re.sub(r"(?<!^)(?=[A-Z][a-z])", "_", str(value).strip())
    identifier = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", identifier)
    identifier = re.sub(r"[^0-9A-Za-z]+", "_", identifier).strip("_").lower()
    if not identifier:
        identifier = "column"
    if identifier[0].isdigit():
        identifier = f"c_{identifier}"
    return identifier


def unique_identifiers(values: Sequence[str]) -> List[str]:
    counts: Dict[str, int] = {}
    identifiers: List[str] = []
    for value in values:
        base = sanitize_identifier(value)
        count = counts.get(base, 0)
        counts[base] = count + 1
        identifiers.append(base if count == 0 else f"{base}_{count + 1}")
    return identifiers


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_table(
    connection: sqlite3.Connection,
    table_name: str,
    columns: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> None:
    column_sql = ", ".join(
        f'"{column}" {_infer_sqlite_type(_values_for_column(rows, original_index))}'
        for original_index, column in enumerate(columns)
    )
    if not column_sql:
        column_sql = '"_empty" TEXT'
    connection.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    connection.execute(f'CREATE TABLE "{table_name}" ({column_sql})')


def _insert_rows(
    connection: sqlite3.Connection,
    table_name: str,
    original_columns: Sequence[str],
    sqlite_columns: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> None:
    if not rows or not sqlite_columns:
        return
    placeholders = ", ".join("?" for _ in sqlite_columns)
    column_sql = ", ".join(f'"{column}"' for column in sqlite_columns)
    sql = f'INSERT INTO "{table_name}" ({column_sql}) VALUES ({placeholders})'
    values = [
        tuple(_sqlite_value(row.get(original_column, "")) for original_column in original_columns)
        for row in rows
    ]
    connection.executemany(sql, values)


def _values_for_column(rows: Sequence[Mapping[str, object]], column_index: int) -> Iterable[object]:
    for row in rows:
        values = list(row.values())
        if column_index < len(values):
            yield values[column_index]


def _infer_sqlite_type(values: Iterable[object]) -> str:
    saw_value = False
    saw_float = False
    for value in values:
        value = _sqlite_value(value)
        if value is None:
            continue
        saw_value = True
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            continue
        if isinstance(value, float):
            saw_float = True
            continue
        return "TEXT"
    if saw_float:
        return "REAL"
    return "INTEGER" if saw_value else "TEXT"


def _sqlite_value(value: object) -> object:
    if value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    return value


def _create_indexes(connection: sqlite3.Connection, table_counts: Mapping[str, int]) -> None:
    candidates = {
        "customers": ["customer_id"],
        "contracts": ["customer_id", "account_owner_id", "days_to_renewal"],
        "contract_services": ["contract_id", "customer_id", "account_owner_id"],
        "existing_customer_billing": ["customer_id", "contract_id", "account_owner_id"],
        "opportunities": ["customer_id", "salesperson_id", "stage"],
        "salespeople": ["salesperson_id"],
        "customer_contract_summary": ["customer_id"],
    }
    for table_name, columns in candidates.items():
        if table_name not in table_counts:
            continue
        existing = _table_columns(connection, table_name)
        for column in columns:
            if column in existing:
                index_name = f"idx_{table_name}_{column}"
                connection.execute(
                    f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ("{column}")'
                )


def _table_columns(connection: sqlite3.Connection, table_name: str) -> List[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table_name}")')]


def _record_import_metadata(
    connection: sqlite3.Connection,
    workbook_path: Path,
    digest: str,
    table_counts: Mapping[str, int],
) -> None:
    connection.execute("DROP TABLE IF EXISTS benchmark_workbook_import")
    connection.execute(
        """
        CREATE TABLE benchmark_workbook_import (
            source_path TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            table_name TEXT NOT NULL,
            row_count INTEGER NOT NULL
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO benchmark_workbook_import
        (source_path, source_sha256, table_name, row_count)
        VALUES (?, ?, ?, ?)
        """,
        [(str(workbook_path), digest, table_name, count) for table_name, count in table_counts.items()],
    )
