from ai_db_benchmark.benchmark.metrics import percentile, summarize_latencies


def test_percentile_interpolates_samples() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    assert round(percentile([1.0, 2.0, 3.0, 4.0], 95), 2) == 3.85


def test_summarize_latencies_reports_core_stats() -> None:
    summary = summarize_latencies([1.0, 2.0, 3.0], failures=1)

    assert summary.successes == 3
    assert summary.failures == 1
    assert summary.median_ms == 2.0
    assert summary.p99_ms > summary.p95_ms
