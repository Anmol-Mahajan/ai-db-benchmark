from pathlib import Path

from ai_db_benchmark.benchmark.results import BenchmarkResult, append_results_jsonl
from ai_db_benchmark.dashboard import generate_dashboard


def test_generate_dashboard_embeds_results_and_database_matrix(tmp_path: Path) -> None:
    results_path = tmp_path / "results.jsonl"
    output_path = tmp_path / "index.html"
    append_results_jsonl(
        results_path,
        [
            BenchmarkResult(
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
                p95_ms=1.1,
                p99_ms=1.2,
                min_ms=0.9,
                max_ms=1.2,
                stddev_ms=0.1,
                throughput_per_second=100.0,
                peak_process_memory_mb=10.0,
                peak_system_memory_percent=50.0,
                cpu_percent=3.0,
                storage_mb=1.0,
                row_count=1,
            )
        ],
    )

    generate_dashboard(results_path, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "AI Database Benchmark Results" in html
    assert "point_read_customer" in html
    assert "PostgreSQL + pgvector" in html
