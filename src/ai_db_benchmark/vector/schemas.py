from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping


@dataclass(frozen=True)
class VectorRecord:
    record_id: str
    vector: List[float]
    document: str
    metadata: Dict[str, object]


@dataclass(frozen=True)
class SearchResult:
    record_id: str
    score: float
    metadata: Mapping[str, object]
