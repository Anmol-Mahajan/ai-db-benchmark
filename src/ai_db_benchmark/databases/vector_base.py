from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Protocol, Sequence

from ai_db_benchmark.vector.schemas import SearchResult, VectorRecord


class VectorStoreAdapter(Protocol):
    name: str
    db_path: Path
    index_type: str
    distance_metric: str

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def reset(self) -> None: ...
    def create_collection(self, dimension: int) -> None: ...
    def upsert_vectors(self, records: Sequence[VectorRecord]) -> int: ...
    def search(self, vector: Sequence[float], top_k: int, filters: Optional[Dict[str, object]] = None) -> List[SearchResult]: ...
    def count(self) -> int: ...
    def database_version(self) -> str: ...
    def storage_bytes(self) -> int: ...


def directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())
