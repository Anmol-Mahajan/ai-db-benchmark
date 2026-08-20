from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class BenchmarkResult:
    benchmark_run_id: str
    run_started_at: str
    architecture: str
    database: str
    database_version: str
    workload_category: str
    workload_name: str
    dataset_name: str
    dataset_rows: int
    dataset_hash: str
    seed: int
    warmup_iterations: int
    measured_iterations: int
    successes: int
    failures: int
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    stddev_ms: float
    throughput_per_second: float
    peak_process_memory_mb: float
    peak_system_memory_percent: float
    cpu_percent: float
    storage_mb: float
    row_count: int
    notes: str = ""
    vector_count: int = 0
    embedding_model: str = ""
    embedding_dimension: int = 0
    distance_metric: str = ""
    index_type: str = ""
    retrieval_recall_at_5: float = 0.0
    retrieval_recall_at_10: float = 0.0
    answer_precision_at_k: float = 0.0
    answer_recall_at_k: float = 0.0
    answer_rank_accuracy: float = 0.0
    answer_hallucination_rate: float = 0.0
    write_verified: bool = False


def utc_run_id(database: str, dataset_size: str, suite: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{database}-{dataset_size}-{suite}"


def append_results_jsonl(path: Path, results: Iterable[BenchmarkResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(asdict(result), sort_keys=True) + "\n")


def write_results_csv(path: Path, results: Iterable[BenchmarkResult]) -> None:
    rows = [asdict(result) for result in results]
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_results_jsonl(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    rows: List[Dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows
