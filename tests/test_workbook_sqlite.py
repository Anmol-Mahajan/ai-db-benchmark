from pathlib import Path
from typing import List, Sequence
from zipfile import ZipFile

from ai_db_benchmark.databases.workbook_sqlite import import_workbook_to_sqlite, sanitize_identifier
from ai_db_benchmark.workloads.excel_risk import WORKBOOK_ACCOUNT_RISK_SQL, run_workbook_account_risk_query


def test_import_workbook_and_run_six_table_risk_query(tmp_path: Path) -> None:
    workbook = tmp_path / "risk.xlsx"
    database = tmp_path / "risk.sqlite"
    _write_workbook(
        workbook,
        {
            "Customers": [
                ["CustomerID", "CustomerName", "Segment", "Region"],
                ["C001", "Acme", "Enterprise", "East"],
            ],
            "Salespeople": [
                ["SalespersonID", "Salesperson"],
                ["S001", "Alice"],
            ],
            "Contracts": [
                [
                    "ContractID",
                    "CustomerID",
                    "AccountOwnerID",
                    "ContractStatus",
                    "DaysToRenewal",
                    "RenewalRisk",
                    "ContractMRR",
                    "ContractARR",
                    "SuggestedAction",
                    "HealthCheckRequired",
                ],
                ["K001", "C001", "S001", "Active", 30, "High", 1000, 12000, "Book review", True],
            ],
            "ContractServices": [
                ["ContractServiceID", "ContractID", "CustomerID", "Service"],
                ["KS001", "K001", "C001", "Managed IT"],
            ],
            "ExistingCustomerBilling": [
                ["BillingID", "CustomerID", "ContractID", "AccountOwnerID", "PaymentStatus", "TotalBilled", "GrossProfit"],
                ["B001", "C001", "K001", "S001", "Overdue", 1200, 400],
            ],
            "Opportunities": [
                ["OpportunityID", "CustomerID", "SalespersonID", "OpportunityType", "Stage", "PipelineValue"],
                ["O001", "C001", "S001", "Cross-sell", "Proposal", 5000],
            ],
        },
    )

    imported = import_workbook_to_sqlite(workbook, database)
    result = run_workbook_account_risk_query(database, limit=5, renewal_days=120)

    assert imported.table_counts["contracts"] == 1
    assert result.rows[0]["customer_id"] == "C001"
    assert result.rows[0]["account_owner"] == "Alice"
    assert result.rows[0]["open_or_overdue_billing"] == 1200
    assert result.rows[0]["open_cross_sell_pipeline"] == 5000
    assert all(
        table in WORKBOOK_ACCOUNT_RISK_SQL
        for table in [
            "customers",
            "contracts",
            "contract_services",
            "existing_customer_billing",
            "opportunities",
            "salespeople",
        ]
    )


def test_sanitize_identifier_handles_excel_names() -> None:
    assert sanitize_identifier("ExistingCustomerBilling") == "existing_customer_billing"
    assert sanitize_identifier("Primary Key") == "primary_key"
    assert sanitize_identifier("123 Field") == "c_123_field"


def _write_workbook(path: Path, sheets: dict) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", _workbook_xml(list(sheets)))
        archive.writestr("xl/_rels/workbook.xml.rels", _rels_xml(len(sheets)))
        for index, rows in enumerate(sheets.values(), start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))


def _workbook_xml(sheet_names: Sequence[str]) -> str:
    sheet_nodes = "\n".join(
        f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
      xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
      <sheets>{sheet_nodes}</sheets>
    </workbook>"""


def _rels_xml(sheet_count: int) -> str:
    rel_nodes = "\n".join(
        f'<Relationship Id="rId{index}" Type="worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      {rel_nodes}
    </Relationships>"""


def _sheet_xml(rows: Sequence[Sequence[object]]) -> str:
    row_nodes: List[str] = []
    for row_index, row in enumerate(rows, start=1):
        cell_nodes = []
        for column_index, value in enumerate(row, start=1):
            ref = f"{_column_letter(column_index)}{row_index}"
            if isinstance(value, bool):
                cell_nodes.append(f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>')
            elif isinstance(value, (int, float)):
                cell_nodes.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cell_nodes.append(f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>')
        row_nodes.append(f'<row r="{row_index}">{"".join(cell_nodes)}</row>')
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
      <sheetData>{"".join(row_nodes)}</sheetData>
    </worksheet>"""


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters
