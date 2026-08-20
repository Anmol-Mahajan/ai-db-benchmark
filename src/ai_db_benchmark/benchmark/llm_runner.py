from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from ai_db_benchmark.benchmark.metrics import summarize_latencies
from ai_db_benchmark.benchmark.results import BenchmarkResult
from ai_db_benchmark.benchmark.system_monitor import snapshot, usage_between
from ai_db_benchmark.config import BenchmarkConfig
from ai_db_benchmark.data.schemas import DatasetBundle
from ai_db_benchmark.databases.base import RelationalAdapter
from ai_db_benchmark.llm.ollama_client import OllamaGeneration
from ai_db_benchmark.workloads.agent_workflows import account_health_360_context, renewal_risk_prompt


class LocalLLMClient(Protocol):
    def generate(self, prompt: str, model: str, temperature: float = 0.0) -> OllamaGeneration: ...


# Returns (context rows, retrieval time in ms) so context can come from SQL or a vector search.
ContextProvider = Callable[[], Tuple[List[Mapping[str, object]], float]]


@dataclass(frozen=True)
class AgentIteration:
    context_rows: int
    context_hash: str
    prompt_hash: str
    response_hash: str
    response_chars: int
    valid_json: bool
    schema_valid: bool
    expected_customer_ids: List[int]
    returned_customer_ids: List[int]
    hallucinated_customer_ids: List[int]
    answer_precision_at_k: float
    answer_recall_at_k: float
    answer_rank_accuracy: float
    answer_hallucination_rate: float
    validation_ms: float
    retrieval_ms: float
    generation_ms: float
    write_ms: float
    readback_ms: float
    written_recommendations: int
    readback_recommendations: int
    write_verified: bool
    total_ms: float


class LLMResponseBenchmarkRunner:
    def __init__(
        self,
        config: BenchmarkConfig,
        context_limit: int = 10,
        context_provider: Optional[ContextProvider] = None,
    ) -> None:
        if context_limit < 1:
            raise ValueError("context_limit must be >= 1")
        self.config = config
        self.context_limit = context_limit
        self.context_provider = context_provider

    def run(
        self,
        adapter: RelationalAdapter,
        dataset: DatasetBundle,
        llm_client: LocalLLMClient,
        model: str,
        benchmark_run_id: str,
        retrieval_description: str = "database execution time for the predefined renewal-risk context query",
    ) -> List[BenchmarkResult]:
        for _ in range(self.config.warmup_iterations):
            self._run_iteration(adapter, llm_client, model)

        before = snapshot()
        iterations: List[AgentIteration] = []
        failures = 0
        for _ in range(self.config.measured_iterations):
            try:
                iterations.append(self._run_iteration(adapter, llm_client, model))
            except Exception:
                failures += 1
        after = snapshot()

        started = datetime.now(timezone.utc).isoformat()
        resources = usage_between(before, after)
        return [
            self._result(
                adapter,
                dataset,
                benchmark_run_id,
                started,
                resources,
                model,
                iterations,
                failures,
                "account_health_360_context_retrieval",
                [iteration.retrieval_ms for iteration in iterations],
                retrieval_description,
            ),
            self._result(
                adapter,
                dataset,
                benchmark_run_id,
                started,
                resources,
                model,
                iterations,
                failures,
                "account_health_360_ollama_generation",
                [iteration.generation_ms for iteration in iterations],
                "local Ollama generation time using retrieved database context",
            ),
            self._result(
                adapter,
                dataset,
                benchmark_run_id,
                started,
                resources,
                model,
                iterations,
                failures,
                "account_health_360_answer_accuracy",
                [iteration.validation_ms for iteration in iterations],
                "JSON/schema validation plus top-k answer accuracy against the database-ranked result set",
            ),
            self._result(
                adapter,
                dataset,
                benchmark_run_id,
                started,
                resources,
                model,
                iterations,
                failures,
                "account_health_360_recommendation_writeback",
                [iteration.write_ms + iteration.readback_ms for iteration in iterations],
                "validated AI recommendations written to the benchmark table and read back for persistence verification",
            ),
            self._result(
                adapter,
                dataset,
                benchmark_run_id,
                started,
                resources,
                model,
                iterations,
                failures,
                "account_health_360_end_to_end",
                [iteration.total_ms for iteration in iterations],
                "database retrieval, local Ollama generation, validation, recommendation write-back, and read-back verification",
            ),
        ]

    def _run_iteration(
        self,
        adapter: RelationalAdapter,
        llm_client: LocalLLMClient,
        model: str,
    ) -> AgentIteration:
        total_started = time.perf_counter_ns()

        if self.context_provider:
            rows, retrieval_ms = self.context_provider()
        else:
            retrieval_started = time.perf_counter_ns()
            rows = adapter.complex_account_health(self.context_limit)
            retrieval_ms = (time.perf_counter_ns() - retrieval_started) / 1_000_000

        context = account_health_360_context(rows)
        prompt = renewal_risk_prompt(context)
        generation = llm_client.generate(prompt, model=model, temperature=0.0)
        if not generation.response.strip():
            raise RuntimeError("Ollama returned an empty response")

        validation_started = time.perf_counter_ns()
        parsed_response = _parse_json_object(generation.response)
        validation = _validate_response(parsed_response, rows)
        validation_ms = (time.perf_counter_ns() - validation_started) / 1_000_000

        write_started = time.perf_counter_ns()
        write_benchmark_run_id = _sha256(
            f"{adapter.name}:{model}:{prompt}:{generation.response}:{write_started}"
        )[:24]
        recommendation_rows = _recommendation_rows(
            benchmark_run_id=write_benchmark_run_id,
            adapter_name=adapter.name,
            model=model,
            rows=rows,
            validation=validation,
            retrieval_ms=retrieval_ms,
            generation_ms=generation.latency_ms,
            validation_ms=validation_ms,
        )
        written = adapter.write_ai_recommendations(recommendation_rows)
        write_ms = (time.perf_counter_ns() - write_started) / 1_000_000

        readback_started = time.perf_counter_ns()
        persisted = adapter.read_ai_recommendations(_benchmark_write_id(recommendation_rows))
        readback_ms = (time.perf_counter_ns() - readback_started) / 1_000_000
        write_verified = written == len(recommendation_rows) == len(persisted)

        total_ms = (time.perf_counter_ns() - total_started) / 1_000_000
        return AgentIteration(
            context_rows=len(rows),
            context_hash=context.stable_hash(),
            prompt_hash=_sha256(prompt),
            response_hash=_sha256(generation.response),
            response_chars=len(generation.response),
            valid_json=validation.valid_json,
            schema_valid=validation.schema_valid,
            expected_customer_ids=validation.expected_customer_ids,
            returned_customer_ids=validation.returned_customer_ids,
            hallucinated_customer_ids=validation.hallucinated_customer_ids,
            answer_precision_at_k=validation.precision_at_k,
            answer_recall_at_k=validation.recall_at_k,
            answer_rank_accuracy=validation.rank_accuracy,
            answer_hallucination_rate=validation.hallucination_rate,
            validation_ms=validation_ms,
            retrieval_ms=retrieval_ms,
            generation_ms=generation.latency_ms,
            write_ms=write_ms,
            readback_ms=readback_ms,
            written_recommendations=written,
            readback_recommendations=len(persisted),
            write_verified=write_verified,
            total_ms=total_ms,
        )

    def _result(
        self,
        adapter: RelationalAdapter,
        dataset: DatasetBundle,
        benchmark_run_id: str,
        started: str,
        resources,
        model: str,
        iterations: Sequence[AgentIteration],
        failures: int,
        workload_name: str,
        latencies_ms: List[float],
        description: str,
    ) -> BenchmarkResult:
        summary = summarize_latencies(latencies_ms, failures=failures)
        row_count = iterations[-1].context_rows if iterations else 0
        precision = _mean([iteration.answer_precision_at_k for iteration in iterations])
        recall = _mean([iteration.answer_recall_at_k for iteration in iterations])
        rank_accuracy = _mean([iteration.answer_rank_accuracy for iteration in iterations])
        hallucination_rate = _mean([iteration.answer_hallucination_rate for iteration in iterations])
        write_verified = bool(iterations) and all(iteration.write_verified for iteration in iterations)
        notes = {
            "scenario": "account_health_360",
            "llm_model": model,
            "context_limit": self.context_limit,
            "description": description,
            "accuracy_method": (
                "The approved database query is treated as ground truth for the benchmark scenario. "
                "The LLM is scored on whether its strict-JSON answer returns the same ranked customer IDs "
                "from the retrieved context and whether validated recommendations are persisted."
            ),
            "iterations": [
                {
                    "context_rows": iteration.context_rows,
                    "context_hash": iteration.context_hash,
                    "prompt_hash": iteration.prompt_hash,
                    "response_hash": iteration.response_hash,
                    "response_chars": iteration.response_chars,
                    "valid_json": iteration.valid_json,
                    "schema_valid": iteration.schema_valid,
                    "expected_customer_ids": iteration.expected_customer_ids,
                    "returned_customer_ids": iteration.returned_customer_ids,
                    "hallucinated_customer_ids": iteration.hallucinated_customer_ids,
                    "answer_precision_at_k": round(iteration.answer_precision_at_k, 6),
                    "answer_recall_at_k": round(iteration.answer_recall_at_k, 6),
                    "answer_rank_accuracy": round(iteration.answer_rank_accuracy, 6),
                    "answer_hallucination_rate": round(iteration.answer_hallucination_rate, 6),
                    "retrieval_ms": round(iteration.retrieval_ms, 6),
                    "generation_ms": round(iteration.generation_ms, 6),
                    "validation_ms": round(iteration.validation_ms, 6),
                    "write_ms": round(iteration.write_ms, 6),
                    "readback_ms": round(iteration.readback_ms, 6),
                    "written_recommendations": iteration.written_recommendations,
                    "readback_recommendations": iteration.readback_recommendations,
                    "write_verified": iteration.write_verified,
                    "total_ms": round(iteration.total_ms, 6),
                }
                for iteration in iterations
            ],
        }
        throughput = summary.successes / resources.duration_seconds if resources.duration_seconds > 0 else 0.0
        return BenchmarkResult(
            benchmark_run_id=benchmark_run_id,
            run_started_at=started,
            architecture=f"local-ollama-{adapter.name}",
            database=adapter.name,
            database_version=adapter.database_version(),
            workload_category="ai_agent",
            workload_name=workload_name,
            dataset_name=dataset.name,
            dataset_rows=dataset.total_rows(),
            dataset_hash=dataset.stable_hash(),
            seed=dataset.seed,
            warmup_iterations=self.config.warmup_iterations,
            measured_iterations=self.config.measured_iterations,
            successes=summary.successes,
            failures=summary.failures,
            mean_ms=round(summary.mean_ms, 6),
            median_ms=round(summary.median_ms, 6),
            p95_ms=round(summary.p95_ms, 6),
            p99_ms=round(summary.p99_ms, 6),
            min_ms=round(summary.min_ms, 6),
            max_ms=round(summary.max_ms, 6),
            stddev_ms=round(summary.stddev_ms, 6),
            throughput_per_second=round(throughput, 6),
            peak_process_memory_mb=round(resources.peak_process_memory_mb, 3),
            peak_system_memory_percent=round(resources.peak_system_memory_percent, 3),
            cpu_percent=round(resources.cpu_percent, 3),
            storage_mb=round(adapter.storage_bytes() / (1024 * 1024), 6),
            row_count=row_count,
            notes=json.dumps(notes, sort_keys=True),
            answer_precision_at_k=round(precision, 6),
            answer_recall_at_k=round(recall, 6),
            answer_rank_accuracy=round(rank_accuracy, 6),
            answer_hallucination_rate=round(hallucination_rate, 6),
            write_verified=write_verified,
        )


@dataclass(frozen=True)
class ResponseValidation:
    valid_json: bool
    schema_valid: bool
    expected_customer_ids: List[int]
    returned_customer_ids: List[int]
    hallucinated_customer_ids: List[int]
    actions_by_customer_id: Dict[int, str]
    reasons_by_customer_id: Dict[int, str]
    precision_at_k: float
    recall_at_k: float
    rank_accuracy: float
    hallucination_rate: float


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_json_object(response: str) -> Mapping[str, Any]:
    text = response.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _validate_response(response: Mapping[str, Any], context_rows: Sequence[Mapping[str, object]]) -> ResponseValidation:
    expected_ids = [_int(row.get("customer_id")) for row in context_rows]
    expected_ids = [customer_id for customer_id in expected_ids if customer_id is not None]
    top_risks = response.get("top_risks") if isinstance(response, dict) else None
    actions = response.get("recommended_actions") if isinstance(response, dict) else None
    valid_json = bool(response)
    schema_valid = isinstance(top_risks, list) and isinstance(actions, list)

    returned_ids: List[int] = []
    reasons_by_customer_id: Dict[int, str] = {}
    if isinstance(top_risks, list):
        for item in top_risks:
            if not isinstance(item, dict):
                schema_valid = False
                continue
            customer_id = _int(item.get("customer_id"))
            if customer_id is None:
                schema_valid = False
                continue
            returned_ids.append(customer_id)
            reason = item.get("risk_reason")
            if isinstance(reason, str):
                reasons_by_customer_id[customer_id] = reason

    actions_by_customer_id: Dict[int, str] = {}
    if isinstance(actions, list):
        for item in actions:
            if not isinstance(item, dict):
                schema_valid = False
                continue
            customer_id = _int(item.get("customer_id"))
            action = item.get("action")
            if customer_id is None or not isinstance(action, str):
                schema_valid = False
                continue
            actions_by_customer_id[customer_id] = action

    expected_set = set(expected_ids)
    returned_set = set(returned_ids)
    correct = returned_set & expected_set
    hallucinated_ids = [customer_id for customer_id in returned_ids if customer_id not in expected_set]
    precision = len(correct) / len(returned_set) if returned_set else 0.0
    recall = len(correct) / len(expected_set) if expected_set else 0.0
    rank_matches = sum(1 for expected_id, returned_id in zip(expected_ids, returned_ids) if expected_id == returned_id)
    rank_accuracy = rank_matches / len(expected_ids) if expected_ids else 0.0
    hallucination_rate = len(hallucinated_ids) / len(returned_ids) if returned_ids else 0.0
    return ResponseValidation(
        valid_json=valid_json,
        schema_valid=schema_valid,
        expected_customer_ids=expected_ids,
        returned_customer_ids=returned_ids,
        hallucinated_customer_ids=hallucinated_ids,
        actions_by_customer_id=actions_by_customer_id,
        reasons_by_customer_id=reasons_by_customer_id,
        precision_at_k=precision,
        recall_at_k=recall,
        rank_accuracy=rank_accuracy,
        hallucination_rate=hallucination_rate,
    )


def _recommendation_rows(
    benchmark_run_id: str,
    adapter_name: str,
    model: str,
    rows: Sequence[Mapping[str, object]],
    validation: ResponseValidation,
    retrieval_ms: float,
    generation_ms: float,
    validation_ms: float,
) -> List[Mapping[str, object]]:
    rows_by_customer_id = {_int(row.get("customer_id")): row for row in rows}
    created_at = datetime.now(timezone.utc).isoformat()
    recommendation_rows: List[Mapping[str, object]] = []
    for index, customer_id in enumerate(validation.returned_customer_ids, start=1):
        if customer_id not in rows_by_customer_id:
            continue
        source_row = rows_by_customer_id[customer_id]
        recommendation_rows.append(
            {
                "recommendation_id": f"{benchmark_run_id}-{index:03d}",
                "customer_id": customer_id,
                "benchmark_run_id": benchmark_run_id,
                "model_name": model,
                "architecture": f"local-ollama-{adapter_name}",
                "recommendation_type": "account_health_360",
                "risk_score": float(source_row.get("risk_score") or 0.0),
                "reason": validation.reasons_by_customer_id.get(customer_id, ""),
                "recommended_action": validation.actions_by_customer_id.get(customer_id, ""),
                "source_record_ids": json.dumps({"customer_id": customer_id}, sort_keys=True),
                "retrieval_latency_ms": round(retrieval_ms, 6),
                "reasoning_latency_ms": round(generation_ms + validation_ms, 6),
                "write_latency_ms": 0.0,
                "created_at": created_at,
            }
        )
    return recommendation_rows


def _benchmark_write_id(rows: Sequence[Mapping[str, object]]) -> str:
    if not rows:
        return ""
    return str(rows[0]["benchmark_run_id"])


def _int(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
