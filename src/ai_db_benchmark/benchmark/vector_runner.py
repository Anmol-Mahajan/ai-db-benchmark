from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from ai_db_benchmark.benchmark.metrics import summarize_latencies
from ai_db_benchmark.benchmark.results import BenchmarkResult
from ai_db_benchmark.benchmark.system_monitor import snapshot, usage_between
from ai_db_benchmark.config import BenchmarkConfig
from ai_db_benchmark.databases.vector_base import VectorStoreAdapter
from ai_db_benchmark.vector.embeddings import EMBEDDING_MODEL_NAME
from ai_db_benchmark.vector.evaluation import exact_top_k, recall_at_k
from ai_db_benchmark.vector.schemas import VectorRecord


class VectorBenchmarkRunner:
    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config

    def run(
        self,
        adapter: VectorStoreAdapter,
        records: Sequence[VectorRecord],
        benchmark_run_id: str,
        dataset_name: str,
        dataset_hash: str,
        seed: int,
    ) -> List[BenchmarkResult]:
        if not records:
            raise ValueError("vector benchmark requires at least one record")

        started = datetime.now(timezone.utc).isoformat()
        results: List[BenchmarkResult] = []

        adapter.reset()
        adapter.create_collection(len(records[0].vector))
        results.append(
            self._measure_ingest(adapter, records, benchmark_run_id, started, dataset_name, dataset_hash, seed)
        )
        if adapter.count() != len(records):
            raise RuntimeError(f"{adapter.name} vector count check failed: expected {len(records)}, got {adapter.count()}")

        rng = random.Random(seed)
        queries = [records[rng.randrange(0, len(records))] for _ in range(self.config.measured_iterations)]
        warmups = [records[rng.randrange(0, len(records))] for _ in range(self.config.warmup_iterations)]
        results.append(
            self._measure_search(
                adapter,
                records,
                warmups,
                queries,
                benchmark_run_id,
                started,
                dataset_name,
                dataset_hash,
                seed,
                "vector_search_top_k",
                None,
            )
        )

        filter_region = str(records[0].metadata["region"])
        filtered_queries = [record for record in records if str(record.metadata.get("region")) == filter_region]
        if filtered_queries:
            warm_filtered = filtered_queries[: self.config.warmup_iterations]
            measured_filtered = filtered_queries[: self.config.measured_iterations]
            results.append(
                self._measure_search(
                    adapter,
                    records,
                    warm_filtered,
                    measured_filtered,
                    benchmark_run_id,
                    started,
                    dataset_name,
                    dataset_hash,
                    seed,
                    "vector_filtered_search_top_k",
                    {"region": filter_region},
                )
            )

        return results

    def _measure_ingest(
        self,
        adapter: VectorStoreAdapter,
        records: Sequence[VectorRecord],
        benchmark_run_id: str,
        started: str,
        dataset_name: str,
        dataset_hash: str,
        seed: int,
    ) -> BenchmarkResult:
        before = snapshot()
        started_ns = time.perf_counter_ns()
        failures = 0
        try:
            row_count = adapter.upsert_vectors(records)
        except Exception:
            failures = 1
            row_count = 0
            raise
        finally:
            elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        after = snapshot()
        resources = usage_between(before, after)
        summary = summarize_latencies([elapsed_ms], failures)
        throughput = row_count / resources.duration_seconds if resources.duration_seconds > 0 else 0.0
        return self._result(
            adapter,
            benchmark_run_id,
            started,
            dataset_name,
            dataset_hash,
            seed,
            "vector",
            "vector_ingest",
            summary,
            throughput,
            resources,
            len(records),
            len(records),
            0.0,
            0.0,
            measured_iterations=1,
            notes="Embeddings were precomputed outside the measured ingestion operation.",
        )

    def _measure_search(
        self,
        adapter: VectorStoreAdapter,
        all_records: Sequence[VectorRecord],
        warmups: Sequence[VectorRecord],
        queries: Sequence[VectorRecord],
        benchmark_run_id: str,
        started: str,
        dataset_name: str,
        dataset_hash: str,
        seed: int,
        workload_name: str,
        filters: Optional[Dict[str, object]],
    ) -> BenchmarkResult:
        for query in warmups:
            adapter.search(query.vector, self.config.top_k, filters=filters)

        latencies_ms: List[float] = []
        failures = 0
        recall_5: List[float] = []
        recall_10: List[float] = []
        rows = 0
        region = str(filters["region"]) if filters and "region" in filters else None
        before = snapshot()
        for query in queries:
            expected_10 = exact_top_k(all_records, query.vector, min(10, self.config.top_k), region=region)
            started_ns = time.perf_counter_ns()
            try:
                actual = adapter.search(query.vector, self.config.top_k, filters=filters)
            except Exception:
                failures += 1
                continue
            finally:
                elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            latencies_ms.append(elapsed_ms)
            rows += len(actual)
            recall_5.append(recall_at_k(expected_10, actual, min(5, self.config.top_k)))
            recall_10.append(recall_at_k(expected_10, actual, min(10, self.config.top_k)))
        after = snapshot()

        summary = summarize_latencies(latencies_ms, failures)
        resources = usage_between(before, after)
        throughput = rows / resources.duration_seconds if resources.duration_seconds > 0 else 0.0
        return self._result(
            adapter,
            benchmark_run_id,
            started,
            dataset_name,
            dataset_hash,
            seed,
            "vector",
            workload_name,
            summary,
            throughput,
            resources,
            len(all_records),
            self.config.top_k,
            sum(recall_5) / len(recall_5) if recall_5 else 0.0,
            sum(recall_10) / len(recall_10) if recall_10 else 0.0,
            self.config.measured_iterations,
            notes=f"filters={filters or {}}",
        )

    def _result(
        self,
        adapter: VectorStoreAdapter,
        benchmark_run_id: str,
        started: str,
        dataset_name: str,
        dataset_hash: str,
        seed: int,
        category: str,
        workload_name: str,
        summary,
        throughput: float,
        resources,
        vector_count: int,
        row_count: int,
        recall_5: float,
        recall_10: float,
        measured_iterations: int,
        notes: str,
    ) -> BenchmarkResult:
        return BenchmarkResult(
            benchmark_run_id=benchmark_run_id,
            run_started_at=started,
            architecture="vector-local",
            database=adapter.name,
            database_version=adapter.database_version(),
            workload_category=category,
            workload_name=workload_name,
            dataset_name=dataset_name,
            dataset_rows=vector_count,
            dataset_hash=dataset_hash,
            seed=seed,
            warmup_iterations=self.config.warmup_iterations,
            measured_iterations=measured_iterations,
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
            row_count=row_count,
            notes=notes,
            vector_count=vector_count,
            embedding_model=EMBEDDING_MODEL_NAME,
            embedding_dimension=self.config.vector_dimension,
            distance_metric=adapter.distance_metric,
            index_type=adapter.index_type,
            retrieval_recall_at_5=round(recall_5, 6),
            retrieval_recall_at_10=round(recall_10, 6),
        )
