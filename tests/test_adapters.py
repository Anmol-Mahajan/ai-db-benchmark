from pathlib import Path

import pytest

from ai_db_benchmark.data.generator import generate_enterprise_dataset
from ai_db_benchmark.databases.duckdb_adapter import DuckDBAdapter
from ai_db_benchmark.databases.sqlite_adapter import SQLiteAdapter


def _exercise_adapter(adapter) -> None:  # type: ignore[no-untyped-def]
    dataset = generate_enterprise_dataset(30, seed=99)
    adapter.connect()
    try:
        adapter.reset()
        adapter.seed(dataset)

        assert adapter.healthcheck()
        assert adapter.row_counts()["customers"] == 30
        assert adapter.point_read_customer(1)["customer_id"] == 1
        assert adapter.filtered_customers_by_region("na", 10)
        assert adapter.update_customer_health(1, 1) == 1
        assert isinstance(adapter.renewal_risk_join(5), list)
        complex_rows = adapter.complex_account_health(5)
        assert isinstance(complex_rows, list)
        if complex_rows:
            assert "risk_score" in complex_rows[0]
        assert len(adapter.revenue_by_region()) <= 4
        assert adapter.storage_bytes() >= 0
    finally:
        adapter.close()


def test_sqlite_adapter(tmp_path: Path) -> None:
    _exercise_adapter(SQLiteAdapter(tmp_path / "baseline.sqlite"))


def test_duckdb_adapter(tmp_path: Path) -> None:
    pytest.importorskip("duckdb")
    _exercise_adapter(DuckDBAdapter(tmp_path / "baseline.duckdb"))
