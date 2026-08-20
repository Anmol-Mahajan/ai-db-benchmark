from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class LatencySummary:
    successes: int
    failures: int
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    stddev_ms: float


def percentile(values: Iterable[float], percentile_value: float) -> float:
    samples = sorted(values)
    if not samples:
        return 0.0
    if len(samples) == 1:
        return samples[0]
    rank = (len(samples) - 1) * (percentile_value / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return samples[int(rank)]
    weight = rank - lower
    return samples[lower] * (1 - weight) + samples[upper] * weight


def summarize_latencies(latencies_ms: List[float], failures: int = 0) -> LatencySummary:
    if not latencies_ms:
        return LatencySummary(0, failures, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return LatencySummary(
        successes=len(latencies_ms),
        failures=failures,
        mean_ms=statistics.fmean(latencies_ms),
        median_ms=statistics.median(latencies_ms),
        p95_ms=percentile(latencies_ms, 95),
        p99_ms=percentile(latencies_ms, 99),
        min_ms=min(latencies_ms),
        max_ms=max(latencies_ms),
        stddev_ms=statistics.stdev(latencies_ms) if len(latencies_ms) > 1 else 0.0,
    )
