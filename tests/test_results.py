from pathlib import Path

from ai_db_benchmark.benchmark.results import BenchmarkResult, append_results_jsonl, load_results_jsonl


def test_results_are_appended_as_jsonl(tmp_path: Path) -> None:
    result = BenchmarkResult(
        benchmark_run_id="run-1",
        run_started_at="2026-01-01T00:00:00+00:00",
        architecture="relational-baseline",
        database="sqlite",
        database_version="test",
        workload_category="crud",
        workload_name="point_read_customer",
        dataset_name="synthetic",
        dataset_rows=10,
        dataset_hash="abc",
        seed=42,
        warmup_iterations=1,
        measured_iterations=2,
        successes=2,
        failures=0,
        mean_ms=1.0,
        median_ms=1.0,
        p95_ms=1.0,
        p99_ms=1.0,
        min_ms=1.0,
        max_ms=1.0,
        stddev_ms=0.0,
        throughput_per_second=100.0,
        peak_process_memory_mb=10.0,
        peak_system_memory_percent=50.0,
        cpu_percent=3.0,
        storage_mb=1.0,
        row_count=1,
    )
    path = tmp_path / "results.jsonl"

    append_results_jsonl(path, [result])
    append_results_jsonl(path, [result])

    rows = load_results_jsonl(path)
    assert len(rows) == 2
    assert rows[0]["benchmark_run_id"] == "run-1"
