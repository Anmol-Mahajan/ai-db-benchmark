from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ai_db_benchmark.databases.vector_base import directory_size_bytes
from ai_db_benchmark.vector.schemas import SearchResult, VectorRecord


class LanceDBAdapter:
    name = "lancedb"
    index_type = "flat"
    distance_metric = "cosine"

    def __init__(self, db_path: Path, table_name: str = "ai_db_benchmark_vectors") -> None:
        self.db_path = db_path
        self.table_name = table_name
        self._db = None
        self._table = None

    def connect(self) -> None:
        try:
            import lancedb
        except ImportError as exc:
            raise RuntimeError("LanceDB benchmark requires lancedb; install with .[vector]") from exc
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self.db_path))

    def close(self) -> None:
        self._db = None
        self._table = None

    @property
    def db(self):  # type: ignore[no-untyped-def]
        if self._db is None:
            raise RuntimeError("LanceDBAdapter is not connected")
        return self._db

    @property
    def table(self):  # type: ignore[no-untyped-def]
        if self._table is None:
            raise RuntimeError("LanceDB table is not created")
        return self._table

    def reset(self) -> None:
        self.close()
        if self.db_path.exists():
            shutil.rmtree(self.db_path)
        self.connect()

    def create_collection(self, dimension: int) -> None:
        sample = [
            {
                "record_id": "__sample__",
                "vector": [0.0 for _ in range(dimension)],
                "document": "",
                "source": "sample",
                "customer_id": 0,
                "segment": "sample",
                "region": "sample",
                "industry": "sample",
            }
        ]
        self._table = self.db.create_table(self.table_name, data=sample, mode="overwrite")
        self.table.delete("record_id = '__sample__'")

    def upsert_vectors(self, records: Sequence[VectorRecord]) -> int:
        rows = [
            {
                "record_id": record.record_id,
                "vector": record.vector,
                "document": record.document,
                "source": str(record.metadata.get("source")),
                "customer_id": int(record.metadata.get("customer_id", 0)),
                "segment": str(record.metadata.get("segment")),
                "region": str(record.metadata.get("region")),
                "industry": str(record.metadata.get("industry")),
            }
            for record in records
        ]
        self.table.add(rows)
        return len(records)

    def search(self, vector: Sequence[float], top_k: int, filters: Optional[Dict[str, object]] = None) -> List[SearchResult]:
        query = self.table.search(list(vector)).metric("cosine").limit(top_k)
        if filters:
            clauses = [f"{key} = '{_sql_literal(value)}'" for key, value in filters.items()]
            query = query.where(" AND ".join(clauses))
        rows = query.to_list()
        return [
            SearchResult(
                record_id=str(row["record_id"]),
                score=1.0 - float(row.get("_distance", 0.0)),
                metadata={key: row.get(key) for key in ["source", "customer_id", "segment", "region", "industry"]},
            )
            for row in rows
        ]

    def count(self) -> int:
        return int(self.table.count_rows())

    def database_version(self) -> str:
        try:
            import lancedb

            return str(getattr(lancedb, "__version__", "lancedb"))
        except ImportError:
            return "missing"

    def storage_bytes(self) -> int:
        return directory_size_bytes(self.db_path)


def _sql_literal(value: object) -> str:
    return str(value).replace("'", "''")
