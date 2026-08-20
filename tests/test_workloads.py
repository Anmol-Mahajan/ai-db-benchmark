from pathlib import Path

from ai_db_benchmark.benchmark.runner import BenchmarkRunner
from ai_db_benchmark.config import BenchmarkConfig
from ai_db_benchmark.data.generator import generate_enterprise_dataset
from ai_db_benchmark.databases.sqlite_adapter import SQLiteAdapter


def test_runner_executes_crud_and_analytics_workloads(tmp_path: Path) -> None:
    dataset = generate_enterprise_dataset(40, seed=5)
    config = BenchmarkConfig(
        dataset_size="custom",
        seed=5,
        warmup_iterations=1,
        measured_iterations=2,
        batch_size=5,
        dataset_sizes={"custom": 40},
    )
    adapter = SQLiteAdapter(tmp_path / "runner.sqlite")
    adapter.connect()
    try:
        adapter.reset()
        adapter.seed(dataset)
        results = BenchmarkRunner(config).run_suite(adapter, dataset, "test-run", suite="all")
    finally:
        adapter.close()

    names = {result.workload_name for result in results}
    assert "insert_one_customer" in names
    assert "renewal_risk_join" in names
    assert "complex_account_health_360" in names
    assert all(result.successes == 2 for result in results)
    assert all(result.failures == 0 for result in results)
