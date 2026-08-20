from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ai_db_benchmark.vector.schemas import SearchResult, VectorRecord


class PgVectorAdapter:
    name = "pgvector"
    index_type = "exact-scan"
    distance_metric = "cosine"
    db_path = Path("postgres://localhost:5432/benchmark")

    def __init__(self, dsn: str = "postgresql://benchmark:benchmark@localhost:5432/benchmark") -> None:
        self.dsn = dsn
        self._conn = None

    def connect(self) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("pgvector benchmark requires psycopg; install with .[vector]") from exc
        self._conn = psycopg.connect(self.dsn, autocommit=True)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self):  # type: ignore[no-untyped-def]
        if self._conn is None:
            raise RuntimeError("PgVectorAdapter is not connected")
        return self._conn

    def reset(self) -> None:
        if self._conn is None:
            self.connect()
        self.conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self.conn.execute("DROP TABLE IF EXISTS benchmark_vectors")

    def create_collection(self, dimension: int) -> None:
        self.conn.execute(
            f"""
            CREATE TABLE benchmark_vectors (
              record_id TEXT PRIMARY KEY,
              embedding vector({dimension}) NOT NULL,
              document TEXT NOT NULL,
              source TEXT NOT NULL,
              customer_id INTEGER NOT NULL,
              segment TEXT NOT NULL,
              region TEXT NOT NULL,
              industry TEXT NOT NULL
            )
            """
        )
        self.conn.execute("CREATE INDEX idx_benchmark_vectors_region ON benchmark_vectors(region)")

    def upsert_vectors(self, records: Sequence[VectorRecord]) -> int:
        rows = [
            (
                record.record_id,
                _vector_literal(record.vector),
                record.document,
                str(record.metadata.get("source")),
                int(record.metadata.get("customer_id", 0)),
                str(record.metadata.get("segment")),
                str(record.metadata.get("region")),
                str(record.metadata.get("industry")),
            )
            for record in records
        ]
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO benchmark_vectors
                (record_id, embedding, document, source, customer_id, segment, region, industry)
                VALUES (%s, %s::vector, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (record_id) DO UPDATE SET embedding = EXCLUDED.embedding
                """,
                rows,
            )
        return len(records)

    def search(self, vector: Sequence[float], top_k: int, filters: Optional[Dict[str, object]] = None) -> List[SearchResult]:
        params: List[object] = [_vector_literal(vector)]
        where = ""
        if filters:
            clauses = []
            for key, value in filters.items():
                if key not in {"region", "segment", "industry", "source"}:
                    raise ValueError(f"Unsupported pgvector filter: {key}")
                params.append(value)
                clauses.append(f"{key} = %s")
            where = "WHERE " + " AND ".join(clauses)
        params.append(top_k)
        rows = self.conn.execute(
            f"""
            SELECT record_id, 1 - (embedding <=> %s::vector) AS score, source, customer_id, segment, region, industry
            FROM benchmark_vectors
            {where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            [params[0]] + params[1:-1] + [params[0], params[-1]],
        ).fetchall()
        return [
            SearchResult(
                record_id=str(row[0]),
                score=float(row[1]),
                metadata={
                    "source": row[2],
                    "customer_id": row[3],
                    "segment": row[4],
                    "region": row[5],
                    "industry": row[6],
                },
            )
            for row in rows
        ]

    def count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM benchmark_vectors").fetchone()[0])

    def database_version(self) -> str:
        row = self.conn.execute(
            "SELECT version(), COALESCE((SELECT extversion FROM pg_extension WHERE extname = 'vector'), 'missing')"
        ).fetchone()
        return f"postgres {str(row[0]).split(',')[0]}; pgvector {row[1]}"

    def storage_bytes(self) -> int:
        return int(self.conn.execute("SELECT pg_total_relation_size('benchmark_vectors')").fetchone()[0])


def _vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(f"{value:.9f}" for value in vector) + "]"
