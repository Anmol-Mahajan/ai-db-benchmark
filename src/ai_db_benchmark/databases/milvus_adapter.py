from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ai_db_benchmark.databases.vector_base import directory_size_bytes
from ai_db_benchmark.vector.schemas import SearchResult, VectorRecord


class MilvusLiteAdapter:
    name = "milvus-lite"
    index_type = "auto-index"
    distance_metric = "cosine"

    def __init__(self, db_path: Path, collection_name: str = "ai_db_benchmark_vectors") -> None:
        self.db_path = db_path
        self.collection_name = collection_name
        self._client = None
        self._id_to_record: Dict[int, str] = {}

    def connect(self) -> None:
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:
            raise RuntimeError("Milvus Lite benchmark requires pymilvus; install with .[vector]") from exc
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = MilvusClient(str(self.db_path))

    def close(self) -> None:
        self._client = None

    @property
    def client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            raise RuntimeError("MilvusLiteAdapter is not connected")
        return self._client

    def reset(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()
        self._id_to_record = {}
        self.connect()

    def create_collection(self, dimension: int) -> None:
        if self.client.has_collection(self.collection_name):
            self.client.drop_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            dimension=dimension,
            metric_type="COSINE",
            auto_id=False,
        )

    def upsert_vectors(self, records: Sequence[VectorRecord]) -> int:
        rows = []
        for index, record in enumerate(records, start=1):
            self._id_to_record[index] = record.record_id
            rows.append(
                {
                    "id": index,
                    "vector": record.vector,
                    "record_id": record.record_id,
                    "document": record.document,
                    "source": str(record.metadata.get("source")),
                    "customer_id": int(record.metadata.get("customer_id", 0)),
                    "segment": str(record.metadata.get("segment")),
                    "region": str(record.metadata.get("region")),
                    "industry": str(record.metadata.get("industry")),
                }
            )
        self.client.insert(collection_name=self.collection_name, data=rows)
        self.client.flush(collection_name=self.collection_name)
        return len(records)

    def search(self, vector: Sequence[float], top_k: int, filters: Optional[Dict[str, object]] = None) -> List[SearchResult]:
        filter_expr = None
        if filters:
            filter_expr = " and ".join(f"{key} == '{_milvus_literal(value)}'" for key, value in filters.items())
        response = self.client.search(
            collection_name=self.collection_name,
            data=[list(vector)],
            limit=top_k,
            filter=filter_expr,
            output_fields=["record_id", "source", "customer_id", "segment", "region", "industry"],
        )
        results: List[SearchResult] = []
        for hit in response[0]:
            entity = hit.get("entity", {})
            results.append(
                SearchResult(
                    record_id=str(entity.get("record_id") or self._id_to_record.get(int(hit["id"]))),
                    score=float(hit.get("distance", 0.0)),
                    metadata=dict(entity),
                )
            )
        return results

    def count(self) -> int:
        stats = self.client.get_collection_stats(self.collection_name)
        return int(stats.get("row_count", 0))

    def database_version(self) -> str:
        try:
            import pymilvus

            return str(getattr(pymilvus, "__version__", "pymilvus"))
        except ImportError:
            return "missing"

    def storage_bytes(self) -> int:
        return directory_size_bytes(self.db_path)


def _milvus_literal(value: object) -> str:
    return str(value).replace("'", "\\'")
