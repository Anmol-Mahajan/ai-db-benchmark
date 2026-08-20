from pathlib import Path
import json

from ai_db_benchmark.benchmark.llm_runner import LLMResponseBenchmarkRunner
from ai_db_benchmark.config import BenchmarkConfig
from ai_db_benchmark.data.generator import generate_enterprise_dataset
from ai_db_benchmark.databases.sqlite_adapter import SQLiteAdapter
from ai_db_benchmark.llm.ollama_client import OllamaGeneration


class FakeLLMClient:
    def generate(self, prompt: str, model: str, temperature: float = 0.0) -> OllamaGeneration:
        assert "CONTEXT_JSON" in prompt
        assert temperature == 0.0
        context = json.loads(prompt.split("CONTEXT_JSON:", 1)[1])
        first = context["rows"][0]
        return OllamaGeneration(
            model=model,
            response=json.dumps(
                {
                    "summary": "ok",
                    "top_risks": [
                        {
                            "customer_id": first["customer_id"],
                            "customer_name": first["customer_name"],
                            "risk_score": first["risk_score"],
                            "risk_reason": "highest database-ranked risk",
                        }
                    ],
                    "recommended_actions": [
                        {
                            "customer_id": first["customer_id"],
                            "action": "Schedule executive renewal review",
                            "priority": "high",
                        }
                    ],
                }
            ),
            latency_ms=12.5,
        )


def test_llm_response_runner_records_database_llm_and_total_phases(tmp_path: Path) -> None:
    dataset = generate_enterprise_dataset(80, seed=42, name="test-agent")
    adapter = SQLiteAdapter(tmp_path / "agent.sqlite")
    adapter.connect()
    try:
        adapter.reset()
        adapter.seed(dataset)
        config = BenchmarkConfig(
            dataset_size="custom",
            dataset_sizes={"custom": 80},
            warmup_iterations=0,
            measured_iterations=2,
        )
        runner = LLMResponseBenchmarkRunner(config, context_limit=5)

        results = runner.run(adapter, dataset, FakeLLMClient(), "fake-local-model", "run-llm")
        persisted = adapter.conn.execute("SELECT COUNT(*) FROM ai_recommendations").fetchone()[0]
    finally:
        adapter.close()

    assert [result.workload_name for result in results] == [
        "account_health_360_context_retrieval",
        "account_health_360_ollama_generation",
        "account_health_360_answer_accuracy",
        "account_health_360_recommendation_writeback",
        "account_health_360_end_to_end",
    ]
    assert all(result.workload_category == "ai_agent" for result in results)
    assert all(result.successes == 2 for result in results)
    assert results[1].median_ms == 12.5
    assert results[2].answer_precision_at_k == 1.0
    assert results[2].answer_recall_at_k == 0.2
    assert results[3].write_verified is True
    assert persisted == 2
    assert "fake-local-model" in results[0].notes
