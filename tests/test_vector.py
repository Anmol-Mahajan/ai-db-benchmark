from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ai_db_benchmark.benchmark.vector_runner import VectorBenchmarkRunner
from ai_db_benchmark.config import BenchmarkConfig
from ai_db_benchmark.data.generator import generate_enterprise_dataset
from ai_db_benchmark.vector.embeddings import build_vector_records, embed_text, make_ollama_embed_fn
from ai_db_benchmark.vector.evaluation import exact_top_k, recall_at_k
from ai_db_benchmark.vector.schemas import SearchResult, VectorRecord


def test_hash_embeddings_are_deterministic_and_normalised() -> None:
    first = embed_text("customer may churn", 16)
    second = embed_text("customer may churn", 16)

    assert first == second
    assert len(first) == 16
    assert round(sum(value * value for value in first), 6) == 1.0


def test_vector_records_use_enterprise_metadata() -> None:
    dataset = generate_enterprise_dataset(20, seed=11)
    records = build_vector_records(dataset, dimension=8, limit=10)

    assert len(records) == 10
    assert {"customer_id", "segment", "region", "industry"} <= set(records[0].metadata)


def test_build_vector_records_uses_custom_embed_fn() -> None:
    dataset = generate_enterprise_dataset(20, seed=11)
    calls: List[str] = []

    def fake_embed(text: str) -> List[float]:
        calls.append(text)
        return [3.0, 4.0]

    records = build_vector_records(dataset, dimension=8, limit=3, embed_fn=fake_embed)

    assert len(records) == 3
    assert len(calls) == 3
    assert all(record.vector == [3.0, 4.0] for record in records)


class FakeOllamaClient:
    def embed(self, text: str, model: str) -> List[float]:
        return [1.0, 0.0, 0.0]


def test_make_ollama_embed_fn_normalises_client_vector() -> None:
    embed_fn = make_ollama_embed_fn("nomic-embed-text", client=FakeOllamaClient())

    assert embed_fn("hello") == [1.0, 0.0, 0.0]


def test_exact_recall_metrics() -> None:
    dataset = generate_enterprise_dataset(10, seed=12)
    records = build_vector_records(dataset, dimension=8, limit=5)
    expected = exact_top_k(records, records[0].vector, top_k=3)
    actual = [SearchResult(record_id=record_id, score=1.0, metadata={}) for record_id in expected[:2]]

    assert expected[0] == records[0].record_id
    assert recall_at_k(expected, actual, 2) == 1.0


def test_vector_runner_records_search_and_recall(tmp_path: Path) -> None:
    dataset = generate_enterprise_dataset(30, seed=13)
    records = build_vector_records(dataset, dimension=8, limit=15)
    config = BenchmarkConfig(
        dataset_size="custom",
        seed=13,
        warmup_iterations=1,
        measured_iterations=2,
        top_k=5,
        vector_dimension=8,
        dataset_sizes={"custom": 30},
        vector_dataset_sizes={"custom": 15},
    )
    adapter = ExactMemoryVectorAdapter(tmp_path)
    adapter.connect()
    try:
        results = VectorBenchmarkRunner(config).run(
            adapter,
            records,
            benchmark_run_id="test-vector-run",
            dataset_name=dataset.name,
            dataset_hash=dataset.stable_hash(),
            seed=dataset.seed,
        )
    finally:
        adapter.close()

    names = {result.workload_name for result in results}
    assert {"vector_ingest", "vector_search_top_k", "vector_filtered_search_top_k"} <= names
    assert all(result.failures == 0 for result in results)
    assert [result for result in results if result.workload_name == "vector_search_top_k"][0].retrieval_recall_at_5 == 1.0


def test_vector_runner_records_configured_embedding_metadata(tmp_path: Path) -> None:
    dataset = generate_enterprise_dataset(30, seed=13)
    records = build_vector_records(dataset, dimension=8, limit=15)
    config = BenchmarkConfig(
        dataset_size="custom",
        seed=13,
        warmup_iterations=1,
        measured_iterations=2,
        top_k=5,
        vector_dimension=8,
        dataset_sizes={"custom": 30},
        vector_dataset_sizes={"custom": 15},
    )
    adapter = ExactMemoryVectorAdapter(tmp_path)
    adapter.connect()
    try:
        results = VectorBenchmarkRunner(
            config,
            embedding_model_name="ollama:nomic-embed-text",
            embedding_dimension=768,
        ).run(
            adapter,
            records,
            benchmark_run_id="test-vector-run-real-embed",
            dataset_name=dataset.name,
            dataset_hash=dataset.stable_hash(),
            seed=dataset.seed,
        )
    finally:
        adapter.close()

    assert all(result.embedding_model == "ollama:nomic-embed-text" for result in results)
    assert all(result.embedding_dimension == 768 for result in results)


class ExactMemoryVectorAdapter:
    name = "exact-memory"
    index_type = "exact-scan"
    distance_metric = "cosine"

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.records: List[VectorRecord] = []

    def connect(self) -> None:
        self.db_path.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        return None

    def reset(self) -> None:
        self.records = []

    def create_collection(self, dimension: int) -> None:
        return None

    def upsert_vectors(self, records: Sequence[VectorRecord]) -> int:
        self.records = list(records)
        return len(records)

    def search(self, vector: Sequence[float], top_k: int, filters: Optional[Dict[str, object]] = None) -> List[SearchResult]:
        region = str(filters["region"]) if filters and "region" in filters else None
        ids = exact_top_k(self.records, vector, top_k=top_k, region=region)
        by_id = {record.record_id: record for record in self.records}
        return [SearchResult(record_id=record_id, score=1.0, metadata=by_id[record_id].metadata) for record_id in ids]

    def count(self) -> int:
        return len(self.records)

    def database_version(self) -> str:
        return "test"

    def storage_bytes(self) -> int:
        return 0
