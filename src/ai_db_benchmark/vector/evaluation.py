from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set

from ai_db_benchmark.vector.embeddings import cosine_similarity
from ai_db_benchmark.vector.schemas import SearchResult, VectorRecord


def exact_top_k(
    records: Sequence[VectorRecord],
    query: Sequence[float],
    top_k: int,
    region: Optional[str] = None,
) -> List[str]:
    candidates = [
        record
        for record in records
        if region is None or str(record.metadata.get("region")) == region
    ]
    ranked = sorted(candidates, key=lambda record: cosine_similarity(record.vector, query), reverse=True)
    return [record.record_id for record in ranked[:top_k]]


def recall_at_k(expected_ids: Iterable[str], actual_results: Sequence[SearchResult], k: int) -> float:
    expected = list(expected_ids)[:k]
    if not expected:
        return 1.0
    actual: Set[str] = {result.record_id for result in actual_results[:k]}
    return len(set(expected) & actual) / len(expected)
