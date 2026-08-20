from pathlib import Path
from zipfile import ZipFile

from ai_db_benchmark.importers.excel import load_workbook_tables, preview_workbook


def test_preview_workbook_reads_sheet_headers_and_samples(tmp_path: Path) -> None:
    workbook = tmp_path / "sample.xlsx"
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="Customers" sheetId="1" r:id="rId1"/></sheets>
            </workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>
            </Relationships>""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <si><t>CustomerID</t></si><si><t>Name</t></si><si><t>C001</t></si><si><t>Acme</t></si>
            </sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <dimension ref="A1:B2"/>
              <sheetData>
                <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>
                <row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row>
              </sheetData>
            </worksheet>""",
        )

    preview = preview_workbook(workbook)

    assert preview[0].name == "Customers"
    assert preview[0].columns == ["CustomerID", "Name"]
    assert preview[0].samples == [["C001", "Acme"]]

    tables = load_workbook_tables(workbook)
    assert tables[0].name == "Customers"
    assert tables[0].rows == [{"CustomerID": "C001", "Name": "Acme"}]
