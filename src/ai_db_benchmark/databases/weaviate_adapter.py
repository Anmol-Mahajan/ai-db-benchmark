from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ai_db_benchmark.vector.schemas import SearchResult, VectorRecord


class WeaviateAdapter:
    name = "weaviate"
    index_type = "hnsw"
    distance_metric = "cosine"
    db_path = Path("http://localhost:8080")

    def __init__(self, url: str = "http://localhost:8080", class_name: str = "BenchmarkVector") -> None:
        self.url = url.rstrip("/")
        self.class_name = class_name

    def connect(self) -> None:
        self._wait_ready()

    def close(self) -> None:
        return None

    def reset(self) -> None:
        self.connect()
        request = urllib.request.Request(
            f"{self.url}/v1/schema/{self.class_name}",
            method="DELETE",
        )
        try:
            urllib.request.urlopen(request, timeout=10).read()
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise

    def create_collection(self, dimension: int) -> None:
        payload = {
            "class": self.class_name,
            "vectorizer": "none",
            "vectorIndexType": "hnsw",
            "vectorIndexConfig": {"distance": "cosine"},
            "properties": [
                {"name": "record_id", "dataType": ["text"], "tokenization": "field"},
                {"name": "document", "dataType": ["text"]},
                {"name": "source", "dataType": ["text"], "tokenization": "field"},
                {"name": "customer_id", "dataType": ["int"]},
                {"name": "segment", "dataType": ["text"], "tokenization": "field"},
                {"name": "region", "dataType": ["text"], "tokenization": "field"},
                {"name": "industry", "dataType": ["text"], "tokenization": "field"},
            ],
        }
        self._json_request("POST", "/v1/schema", payload)

    def upsert_vectors(self, records: Sequence[VectorRecord]) -> int:
        objects = [
            {
                "class": self.class_name,
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, record.record_id)),
                "vector": record.vector,
                "properties": {
                    "record_id": record.record_id,
                    "document": record.document,
                    "source": str(record.metadata.get("source")),
                    "customer_id": int(record.metadata.get("customer_id", 0)),
                    "segment": str(record.metadata.get("segment")),
                    "region": str(record.metadata.get("region")),
                    "industry": str(record.metadata.get("industry")),
                },
            }
            for record in records
        ]
        self._json_request("POST", "/v1/batch/objects", {"objects": objects})
        return len(records)

    def search(self, vector: Sequence[float], top_k: int, filters: Optional[Dict[str, object]] = None) -> List[SearchResult]:
        where = ""
        if filters:
            where = f", where: {_where_filter_literal(filters)}"
        query = {
            "query": f"""
            {{
              Get {{
                {self.class_name}(
                  nearVector: {{vector: {_graphql_literal(list(vector))}}},
                  limit: {top_k}
                  {where}
                ) {{
                  record_id
                  source
                  customer_id
                  segment
                  region
                  industry
                  _additional {{ id distance }}
                }}
              }}
            }}
            """
        }
        response = self._json_request("POST", "/v1/graphql", query)
        rows = response.get("data", {}).get("Get", {}).get(self.class_name, [])
        return [
            SearchResult(
                record_id=str(row["record_id"]),
                score=1.0 - float(row.get("_additional", {}).get("distance", 0.0)),
                metadata={key: row.get(key) for key in ["source", "customer_id", "segment", "region", "industry"]},
            )
            for row in rows
        ]

    def count(self) -> int:
        query = {
            "query": f"{{ Aggregate {{ {self.class_name} {{ meta {{ count }} }} }} }}"
        }
        response = self._json_request("POST", "/v1/graphql", query)
        return int(response["data"]["Aggregate"][self.class_name][0]["meta"]["count"])

    def database_version(self) -> str:
        try:
            meta = self._json_request("GET", "/v1/meta", None)
            return f"weaviate {meta.get('version', 'unknown')}"
        except Exception:
            return "weaviate"

    def storage_bytes(self) -> int:
        return 0

    def _wait_ready(self) -> None:
        deadline = time.time() + 60
        last_error = ""
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{self.url}/v1/.well-known/ready", timeout=5) as response:
                    if response.status == 200:
                        return
            except Exception as exc:
                last_error = str(exc)
            time.sleep(1)
        raise RuntimeError(f"Weaviate is not ready at {self.url}: {last_error}")

    def _json_request(self, method: str, path: str, payload: Optional[Dict[str, object]]) -> Dict[str, object]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
        return json.loads(body.decode("utf-8")) if body else {}


def _graphql_literal(value: object) -> str:
    return json.dumps(value)


def _where_filter_literal(filters: Dict[str, object]) -> str:
    operands = [
        f'{{path: ["{_graphql_name(key)}"], operator: Equal, valueText: {_graphql_literal(str(value))}}}'
        for key, value in filters.items()
    ]
    if len(operands) == 1:
        return operands[0]
    return "{operator: And, operands: [" + ", ".join(operands) + "]}"


def _graphql_name(value: str) -> str:
    if not value.replace("_", "").isalnum():
        raise ValueError(f"Unsupported Weaviate filter name: {value}")
    return value
