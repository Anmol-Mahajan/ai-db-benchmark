from __future__ import annotations

import hashlib
import math
from typing import Callable, Iterable, List, Optional

from ai_db_benchmark.data.schemas import DatasetBundle
from ai_db_benchmark.vector.schemas import VectorRecord


EMBEDDING_MODEL_NAME = "deterministic-hash-embedding-v1"

EmbedFn = Callable[[str], List[float]]


def build_vector_records(
    dataset: DatasetBundle,
    dimension: int,
    limit: int,
    embed_fn: Optional[EmbedFn] = None,
) -> List[VectorRecord]:
    records: List[VectorRecord] = []
    customers_by_id = {int(row["customer_id"]): row for row in dataset.customers}

    def embed(text: str) -> List[float]:
        return embed_fn(text) if embed_fn else embed_text(text, dimension)

    for note in dataset.customer_notes:
        if len(records) >= limit:
            break
        customer_id = int(note["customer_id"])
        customer = customers_by_id[customer_id]
        document = str(note["note_text"])
        records.append(
            VectorRecord(
                record_id=f"note-{note['note_id']}",
                vector=embed(document),
                document=document,
                metadata={
                    "source": "customer_notes",
                    "customer_id": customer_id,
                    "segment": customer["segment"],
                    "region": customer["region"],
                    "industry": customer["industry"],
                },
            )
        )

    for transcript in dataset.call_transcripts:
        if len(records) >= limit:
            break
        customer_id = int(transcript["customer_id"])
        customer = customers_by_id[customer_id]
        document = str(transcript["transcript_text"])
        records.append(
            VectorRecord(
                record_id=f"call-{transcript['transcript_id']}",
                vector=embed(document),
                document=document,
                metadata={
                    "source": "call_transcripts",
                    "customer_id": customer_id,
                    "segment": customer["segment"],
                    "region": customer["region"],
                    "industry": customer["industry"],
                },
            )
        )

    return records


def embed_text(text: str, dimension: int) -> List[float]:
    values: List[float] = []
    counter = 0
    while len(values) < dimension:
        digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
        for byte in digest:
            values.append((byte / 127.5) - 1.0)
            if len(values) == dimension:
                break
        counter += 1
    return _normalise(values)


def make_ollama_embed_fn(model: str, client: Optional[object] = None) -> EmbedFn:
    """Build an embed function backed by a real local Ollama embedding model."""
    from ai_db_benchmark.llm.ollama_client import OllamaClient

    active_client = client or OllamaClient()

    def _embed(text: str) -> List[float]:
        return _normalise(active_client.embed(text, model))

    return _embed


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _normalise(values: List[float]) -> List[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]
