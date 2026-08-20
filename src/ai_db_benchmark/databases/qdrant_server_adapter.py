from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ai_db_benchmark.vector.schemas import SearchResult, VectorRecord


class QdrantServerAdapter:
    name = "qdrant-server"
    index_type = "hnsw"
    distance_metric = "cosine"
    db_path = Path("http://localhost:6333")

    def __init__(self, url: str = "http://localhost:6333", collection_name: str = "ai_db_benchmark_vectors") -> None:
        self.url = url
        self.collection_name = collection_name
        self._client = None

    def connect(self) -> None:
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise RuntimeError("Qdrant Server benchmark requires qdrant-client; install with .[vector]") from exc
        self._client = QdrantClient(url=self.url, timeout=10)

    def close(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if close:
                close()
        self._client = None

    @property
    def client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            raise RuntimeError("QdrantServerAdapter is not connected")
        return self._client

    def reset(self) -> None:
        if self._client is None:
            self.connect()
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)

    def create_collection(self, dimension: int) -> None:
        from qdrant_client import models

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
        )

    def upsert_vectors(self, records: Sequence[VectorRecord]) -> int:
        from qdrant_client import models

        points = [
            models.PointStruct(
                id=index + 1,
                vector=record.vector,
                payload={**record.metadata, "record_id": record.record_id, "document": record.document},
            )
            for index, record in enumerate(records)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        return len(records)

    def search(self, vector: Sequence[float], top_k: int, filters: Optional[Dict[str, object]] = None) -> List[SearchResult]:
        query_filter = None
        if filters:
            from qdrant_client import models

            query_filter = models.Filter(
                must=[models.FieldCondition(key=key, match=models.MatchValue(value=value)) for key, value in filters.items()]
            )
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=list(vector),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return [
            SearchResult(
                record_id=str(point.payload.get("record_id")),
                score=float(point.score),
                metadata=dict(point.payload),
            )
            for point in response.points
        ]

    def count(self) -> int:
        return int(self.client.count(collection_name=self.collection_name, exact=True).count)

    def database_version(self) -> str:
        try:
            response = self.client.get_locks()
            return f"qdrant-server {type(response).__name__}"
        except Exception:
            return "qdrant-server"

    def storage_bytes(self) -> int:
        return 0
