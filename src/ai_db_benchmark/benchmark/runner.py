from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Callable, List, Mapping, Sequence

from ai_db_benchmark.benchmark.metrics import summarize_latencies
from ai_db_benchmark.benchmark.results import BenchmarkResult
from ai_db_benchmark.benchmark.system_monitor import snapshot, usage_between
from ai_db_benchmark.config import BenchmarkConfig
from ai_db_benchmark.data.schemas import DatasetBundle
from ai_db_benchmark.databases.base import RelationalAdapter


Operation = Callable[[], int]


class BenchmarkRunner:
    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config

    def run_suite(
        self,
        adapter: RelationalAdapter,
        dataset: DatasetBundle,
        benchmark_run_id: str,
        suite: str = "all",
    ) -> List[BenchmarkResult]:
        if suite not in {"all", "crud", "analytics"}:
            raise ValueError("suite must be one of: all, crud, analytics")

        rng = random.Random(dataset.seed)
        started = datetime.now(timezone.utc).isoformat()
        results: List[BenchmarkResult] = []

        if suite in {"all", "crud"}:
            results.extend(
                [
                    self._measure(adapter, dataset, benchmark_run_id, started, "crud", "insert_one_customer", 1, lambda: adapter.insert_customers([self._new_customer(dataset, rng, 1)[0]])),
                    self._measure(adapter, dataset, benchmark_run_id, started, "crud", "insert_batch_customers", self.config.batch_size, lambda: adapter.insert_customers(self._new_customer(dataset, rng, self.config.batch_size))),
                    self._measure(adapter, dataset, benchmark_run_id, started, "crud", "point_read_customer", 1, lambda: 1 if adapter.point_read_customer(rng.randint(1, len(dataset.customers))) else 0),
                    self._measure(adapter, dataset, benchmark_run_id, started, "crud", "filtered_read_region", 25, lambda: len(adapter.filtered_customers_by_region(rng.choice(["na", "emea", "apac", "latam"]), 25))),
                    self._measure(adapter, dataset, benchmark_run_id, started, "crud", "update_customer_health", 1, lambda: adapter.update_customer_health(rng.randint(1, len(dataset.customers)), rng.choice([-2, -1, 1, 2]))),
                ]
            )

        if suite in {"all", "analytics"}:
            results.extend(
                [
                    self._measure(adapter, dataset, benchmark_run_id, started, "analytics", "renewal_risk_join", 20, lambda: len(adapter.renewal_risk_join(20))),
                    self._measure(adapter, dataset, benchmark_run_id, started, "analytics", "complex_account_health_360", 50, lambda: len(adapter.complex_account_health(50))),
                    self._measure(adapter, dataset, benchmark_run_id, started, "analytics", "revenue_by_region_aggregation", 4, lambda: len(adapter.revenue_by_region())),
                ]
            )

        return results

    def _measure(
        self,
        adapter: RelationalAdapter,
        dataset: DatasetBundle,
        benchmark_run_id: str,
        started: str,
        category: str,
        name: str,
        operation_rows: int,
        operation: Operation,
    ) -> BenchmarkResult:
        for _ in range(self.config.warmup_iterations):
            operation()

        latencies_ms: List[float] = []
        failures = 0
        rows_processed = 0
        before = snapshot()
        for _ in range(self.config.measured_iterations):
            started_ns = time.perf_counter_ns()
            try:
                rows_processed += int(operation())
            except Exception:
                failures += 1
                continue
            finally:
                elapsed_ns = time.perf_counter_ns() - started_ns
            latencies_ms.append(elapsed_ns / 1_000_000)
        after = snapshot()

        summary = summarize_latencies(latencies_ms, failures=failures)
        resources = usage_between(before, after)
        throughput = rows_processed / resources.duration_seconds if resources.duration_seconds > 0 else 0.0
        return BenchmarkResult(
            benchmark_run_id=benchmark_run_id,
            run_started_at=started,
            architecture="relational-baseline",
            database=adapter.name,
            database_version=adapter.database_version(),
            workload_category=category,
            workload_name=name,
            dataset_name=dataset.name,
            dataset_rows=dataset.total_rows(),
            dataset_hash=dataset.stable_hash(),
            seed=dataset.seed,
            warmup_iterations=self.config.warmup_iterations,
            measured_iterations=self.config.measured_iterations,
            successes=summary.successes,
            failures=summary.failures,
            mean_ms=round(summary.mean_ms, 6),
            median_ms=round(summary.median_ms, 6),
            p95_ms=round(summary.p95_ms, 6),
            p99_ms=round(summary.p99_ms, 6),
            min_ms=round(summary.min_ms, 6),
            max_ms=round(summary.max_ms, 6),
            stddev_ms=round(summary.stddev_ms, 6),
            throughput_per_second=round(throughput, 6),
            peak_process_memory_mb=round(resources.peak_process_memory_mb, 3),
            peak_system_memory_percent=round(resources.peak_system_memory_percent, 3),
            cpu_percent=round(resources.cpu_percent, 3),
            storage_mb=round(adapter.storage_bytes() / (1024 * 1024), 6),
            row_count=operation_rows,
        )

    def _new_customer(self, dataset: DatasetBundle, rng: random.Random, count: int) -> Sequence[Mapping[str, object]]:
        base_id = 10_000_000 + rng.randint(1, 1_000_000_000)
        rows = []
        for offset in range(count):
            customer_id = base_id + offset
            previous_mrr = float(rng.randrange(500, 50000, 50))
            current_mrr = max(0.0, previous_mrr + float(rng.randrange(-1000, 2000, 50)))
            rows.append(
                {
                    "customer_id": customer_id,
                    "customer_name": f"Benchmark Customer {customer_id}",
                    "segment": rng.choice(["enterprise", "mid_market", "smb"]),
                    "industry": rng.choice(["software", "finance", "healthcare", "manufacturing"]),
                    "region": rng.choice(["na", "emea", "apac", "latam"]),
                    "created_at": "2026-01-01",
                    "status": "active",
                    "current_mrr": current_mrr,
                    "previous_mrr": previous_mrr,
                    "annual_revenue": current_mrr * 12,
                    "account_manager_id": int(dataset.salespeople[0]["salesperson_id"]),
                    "customer_health_score": rng.randint(30, 95),
                }
            )
        return rows
