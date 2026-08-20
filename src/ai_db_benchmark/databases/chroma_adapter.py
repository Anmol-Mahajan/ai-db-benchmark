from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ai_db_benchmark.databases.vector_base import directory_size_bytes
from ai_db_benchmark.vector.schemas import SearchResult, VectorRecord


class ChromaAdapter:
    name = "chroma"
    index_type = "hnsw"
    distance_metric = "cosine"

    def __init__(self, db_path: Path, collection_name: str = "ai_db_benchmark_vectors") -> None:
        self.db_path = db_path
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def connect(self) -> None:
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as exc:
            raise RuntimeError("Chroma benchmark requires chromadb; install with .[vector]") from exc
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False),
        )

    def close(self) -> None:
        self._client = None
        self._collection = None

    @property
    def client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            raise RuntimeError("ChromaAdapter is not connected")
        return self._client

    @property
    def collection(self):  # type: ignore[no-untyped-def]
        if self._collection is None:
            raise RuntimeError("Chroma collection is not created")
        return self._collection

    def reset(self) -> None:
        self.close()
        if self.db_path.exists():
            shutil.rmtree(self.db_path)
        self.connect()

    def create_collection(self, dimension: int) -> None:
        existing = [
            collection.name if hasattr(collection, "name") else str(collection)
            for collection in self.client.list_collections()
        ]
        if self.collection_name in existing:
            self.client.delete_collection(self.collection_name)
        self._collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine", "dimension": dimension},
        )

    def upsert_vectors(self, records: Sequence[VectorRecord]) -> int:
        self.collection.add(
            ids=[record.record_id for record in records],
            embeddings=[record.vector for record in records],
            documents=[record.document for record in records],
            metadatas=[record.metadata for record in records],
        )
        return len(records)

    def search(self, vector: Sequence[float], top_k: int, filters: Optional[Dict[str, object]] = None) -> List[SearchResult]:
        response = self.collection.query(
            query_embeddings=[list(vector)],
            n_results=top_k,
            where=filters,
            include=["metadatas", "distances"],
        )
        ids = response.get("ids", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]
        return [
            SearchResult(record_id=str(record_id), score=1.0 - float(distance), metadata=dict(metadata or {}))
            for record_id, metadata, distance in zip(ids, metadatas, distances)
        ]

    def count(self) -> int:
        return int(self.collection.count())

    def database_version(self) -> str:
        try:
            import chromadb

            return str(getattr(chromadb, "__version__", "chromadb"))
        except ImportError:
            return "missing"

    def storage_bytes(self) -> int:
        return directory_size_bytes(self.db_path)
