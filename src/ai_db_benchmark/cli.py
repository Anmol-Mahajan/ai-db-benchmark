from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from ai_db_benchmark.benchmark.results import append_results_jsonl, load_results_jsonl, utc_run_id, write_results_csv
from ai_db_benchmark.benchmark.llm_runner import LLMResponseBenchmarkRunner
from ai_db_benchmark.benchmark.runner import BenchmarkRunner
from ai_db_benchmark.benchmark.vector_runner import VectorBenchmarkRunner
from ai_db_benchmark.config import BenchmarkConfig, load_benchmark_config, project_path
from ai_db_benchmark.dashboard import generate_dashboard
from ai_db_benchmark.data.generator import generate_enterprise_dataset
from ai_db_benchmark.data.loaders import save_dataset
from ai_db_benchmark.databases.chroma_adapter import ChromaAdapter
from ai_db_benchmark.databases.duckdb_adapter import DuckDBAdapter
from ai_db_benchmark.databases.lancedb_adapter import LanceDBAdapter
from ai_db_benchmark.databases.milvus_adapter import MilvusLiteAdapter
from ai_db_benchmark.databases.postgres_adapter import PostgreSQLAdapter
from ai_db_benchmark.databases.pgvector_adapter import PgVectorAdapter
from ai_db_benchmark.databases.qdrant_adapter import QdrantLocalAdapter
from ai_db_benchmark.databases.qdrant_server_adapter import QdrantServerAdapter
from ai_db_benchmark.databases.sqlite_adapter import SQLiteAdapter
from ai_db_benchmark.databases.weaviate_adapter import WeaviateAdapter
from ai_db_benchmark.databases.workbook_sqlite import import_workbook_to_sqlite
from ai_db_benchmark.doctor import run_doctor
from ai_db_benchmark.importers.excel import preview_workbook
from ai_db_benchmark.llm.ollama_client import OllamaClient, OllamaUnavailable
from ai_db_benchmark.vector.embeddings import EMBEDDING_MODEL_NAME, build_vector_records, make_ollama_embed_fn
from ai_db_benchmark.workloads.excel_risk import (
    run_workbook_account_risk_query,
    workbook_context_for_llm,
    workbook_risk_prompt,
)


DEFAULT_WORKBOOK_PATH = project_path("data", "raw", "MSP_Sales_Performance_Demo_Data_Updated_With_Contracts.xlsx")
DEFAULT_WORKBOOK_DB_PATH = project_path("data", "generated", "excel_workbook.sqlite")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-db-benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Check local machine readiness")

    generate_parser = subparsers.add_parser("generate-data", help="Generate deterministic synthetic data")
    generate_parser.add_argument("--size", default=None, choices=["smoke", "small", "medium", "million", "large"])
    generate_parser.add_argument("--customers", type=int, default=None)
    generate_parser.add_argument("--seed", type=int, default=None)
    generate_parser.add_argument("--output", type=Path, default=None)

    preview_parser = subparsers.add_parser("preview-excel", help="Preview an Excel workbook as benchmark source data")
    preview_parser.add_argument("--path", type=Path, default=DEFAULT_WORKBOOK_PATH)
    preview_parser.add_argument("--samples", type=int, default=2)

    import_excel_parser = subparsers.add_parser("import-excel", help="Import workbook sheets into local SQLite")
    import_excel_parser.add_argument("--path", type=Path, default=DEFAULT_WORKBOOK_PATH)
    import_excel_parser.add_argument("--database", type=Path, default=DEFAULT_WORKBOOK_DB_PATH)

    risk_parser = subparsers.add_parser("excel-risk-query", help="Run the fixed multi-table Excel risk query")
    risk_parser.add_argument("--path", type=Path, default=DEFAULT_WORKBOOK_PATH)
    risk_parser.add_argument("--database", type=Path, default=DEFAULT_WORKBOOK_DB_PATH)
    risk_parser.add_argument("--limit", type=int, default=10)
    risk_parser.add_argument("--renewal-days", type=int, default=120)
    risk_parser.add_argument("--refresh", action="store_true")
    risk_parser.add_argument("--show-sql", action="store_true")

    ollama_parser = subparsers.add_parser("ollama-excel-risk", help="Summarize Excel risk rows with local Ollama")
    ollama_parser.add_argument("--path", type=Path, default=DEFAULT_WORKBOOK_PATH)
    ollama_parser.add_argument("--database", type=Path, default=DEFAULT_WORKBOOK_DB_PATH)
    ollama_parser.add_argument("--limit", type=int, default=10)
    ollama_parser.add_argument("--renewal-days", type=int, default=120)
    ollama_parser.add_argument("--refresh", action="store_true")
    ollama_parser.add_argument("--model", default=None)
    ollama_parser.add_argument("--show-sql", action="store_true")
    ollama_parser.add_argument("--show-context", action="store_true")

    llm_benchmark_parser = subparsers.add_parser("llm-benchmark", help="Benchmark local Ollama response workflows across databases")
    llm_benchmark_parser.add_argument("--database", choices=["sqlite", "duckdb", "postgres", "all"], required=True)
    llm_benchmark_parser.add_argument("--model", default=None)
    llm_benchmark_parser.add_argument("--size", choices=["smoke", "small", "medium", "million", "large"], default=None)
    llm_benchmark_parser.add_argument("--customers", type=int, default=None)
    llm_benchmark_parser.add_argument("--seed", type=int, default=None)
    llm_benchmark_parser.add_argument("--warmup", type=int, default=0)
    llm_benchmark_parser.add_argument("--iterations", type=int, default=1)
    llm_benchmark_parser.add_argument("--context-limit", type=int, default=10)
    llm_benchmark_parser.add_argument("--results", type=Path, default=project_path("data", "results", "benchmark_results.jsonl"))

    benchmark_parser = subparsers.add_parser("benchmark", help="Run a local baseline benchmark")
    benchmark_parser.add_argument("--database", choices=["sqlite", "duckdb", "postgres"], required=True)
    benchmark_parser.add_argument("--suite", choices=["all", "crud", "analytics"], default="all")
    benchmark_parser.add_argument("--size", choices=["smoke", "small", "medium", "million", "large"], default=None)
    benchmark_parser.add_argument("--customers", type=int, default=None)
    benchmark_parser.add_argument("--seed", type=int, default=None)
    benchmark_parser.add_argument("--warmup", type=int, default=None)
    benchmark_parser.add_argument("--iterations", type=int, default=None)
    benchmark_parser.add_argument("--batch-size", type=int, default=None)
    benchmark_parser.add_argument("--results", type=Path, default=project_path("data", "results", "benchmark_results.jsonl"))

    vector_parser = subparsers.add_parser("vector-benchmark", help="Run local vector-store benchmarks")
    vector_parser.add_argument(
        "--database",
        choices=[
            "chroma",
            "qdrant",
            "qdrant-local",
            "qdrant-server",
            "lancedb",
            "milvus-lite",
            "pgvector",
            "weaviate",
            "embedded",
            "service",
            "all",
        ],
        required=True,
    )
    vector_parser.add_argument("--size", choices=["smoke", "small", "medium", "million", "large"], default=None)
    vector_parser.add_argument("--customers", type=int, default=None)
    vector_parser.add_argument("--vectors", type=int, default=None)
    vector_parser.add_argument("--seed", type=int, default=None)
    vector_parser.add_argument("--warmup", type=int, default=None)
    vector_parser.add_argument("--iterations", type=int, default=None)
    vector_parser.add_argument("--top-k", type=int, default=None)
    vector_parser.add_argument("--dimension", type=int, default=None)
    vector_parser.add_argument("--embedding-model", default=None, help="Local Ollama embedding model to use instead of the deterministic hash embedding")
    vector_parser.add_argument("--results", type=Path, default=project_path("data", "results", "benchmark_results.jsonl"))

    report_parser = subparsers.add_parser("report", help="Print a compact result table")
    report_parser.add_argument("--results", type=Path, default=project_path("data", "results", "benchmark_results.jsonl"))

    dashboard_parser = subparsers.add_parser("dashboard", help="Build a static local results dashboard")
    dashboard_parser.add_argument("--results", type=Path, default=project_path("data", "results", "benchmark_results.jsonl"))
    dashboard_parser.add_argument("--output", type=Path, default=project_path("dashboard", "index.html"))

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "doctor":
        return _doctor()
    if args.command == "generate-data":
        return _generate_data(args)
    if args.command == "preview-excel":
        return _preview_excel(args)
    if args.command == "import-excel":
        return _import_excel(args)
    if args.command == "excel-risk-query":
        return _excel_risk_query(args)
    if args.command == "ollama-excel-risk":
        return _ollama_excel_risk(args)
    if args.command == "llm-benchmark":
        return _llm_benchmark(args)
    if args.command == "benchmark":
        return _benchmark(args)
    if args.command == "vector-benchmark":
        return _vector_benchmark(args)
    if args.command == "report":
        return _report(args.results)
    if args.command == "dashboard":
        output = generate_dashboard(args.results, args.output)
        print(f"Dashboard written to: {output}")
        return 0
    parser.error("unknown command")
    return 2


def _doctor() -> int:
    checks = run_doctor()
    print("AI Database Benchmark Doctor")
    failures = 0
    for check in checks:
        marker = "PASS" if check.ok else ("WARN" if not check.required else "FAIL")
        print(f"{marker:4} {check.name}: {check.detail}")
        if check.required and not check.ok:
            failures += 1
    return 1 if failures else 0


def _config_from_args(args: argparse.Namespace) -> BenchmarkConfig:
    base = load_benchmark_config()
    dataset_size = args.size or base.dataset_size
    dataset_sizes = dict(base.dataset_sizes)
    if args.customers is not None:
        dataset_size = "custom"
        dataset_sizes["custom"] = args.customers
    return BenchmarkConfig(
        dataset_size=dataset_size,
        seed=args.seed if args.seed is not None else base.seed,
        warmup_iterations=args.warmup if getattr(args, "warmup", None) is not None else base.warmup_iterations,
        measured_iterations=args.iterations if getattr(args, "iterations", None) is not None else base.measured_iterations,
        batch_size=args.batch_size if getattr(args, "batch_size", None) is not None else base.batch_size,
        top_k=args.top_k if getattr(args, "top_k", None) is not None else base.top_k,
        vector_dimension=args.dimension if getattr(args, "dimension", None) is not None else base.vector_dimension,
        store_raw_samples=base.store_raw_samples,
        dataset_sizes=dataset_sizes,
        vector_dataset_sizes=base.vector_dataset_sizes,
    )


def _generate_data(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    dataset = generate_enterprise_dataset(config.customer_count, seed=config.seed, name=f"synthetic-enterprise-{config.dataset_size}")
    output = args.output or project_path("data", "generated", f"{dataset.name}.json")
    save_dataset(dataset, output)
    print(f"Generated {len(dataset.customers)} customers / {dataset.total_rows()} total rows at {output}")
    print(f"Dataset hash: {dataset.stable_hash()}")
    return 0


def _preview_excel(args: argparse.Namespace) -> int:
    sheets = preview_workbook(args.path, sample_rows=args.samples)
    print(f"Workbook: {args.path}")
    print(f"Sheets: {len(sheets)}")
    for sheet in sheets:
        print()
        print(f"{sheet.name}: {sheet.row_count} rows x {sheet.column_count} columns ({sheet.dimension})")
        print("Columns:", ", ".join(sheet.columns))
        for sample in sheet.samples:
            print("Sample:", sample)
    return 0


def _import_excel(args: argparse.Namespace) -> int:
    result = import_workbook_to_sqlite(args.path, args.database, replace=True)
    print(f"Imported workbook: {result.source_path}")
    print(f"SQLite database: {result.database_path}")
    print(f"Source SHA256: {result.source_sha256}")
    print("Tables:")
    for table_name, count in sorted(result.table_counts.items()):
        print(f"  {table_name}: {count} rows")
    return 0


def _ensure_excel_database(args: argparse.Namespace) -> Path:
    if getattr(args, "refresh", False) or not args.database.exists():
        result = import_workbook_to_sqlite(args.path, args.database, replace=True)
        print(f"Imported workbook into {result.database_path}")
    return args.database


def _excel_risk_query(args: argparse.Namespace) -> int:
    database_path = _ensure_excel_database(args)
    result = run_workbook_account_risk_query(
        database_path,
        limit=args.limit,
        renewal_days=args.renewal_days,
    )
    _print_risk_query_result(result, show_sql=args.show_sql)
    return 0


def _ollama_excel_risk(args: argparse.Namespace) -> int:
    database_path = _ensure_excel_database(args)
    result = run_workbook_account_risk_query(
        database_path,
        limit=args.limit,
        renewal_days=args.renewal_days,
    )
    context_json = workbook_context_for_llm(result)
    if args.show_sql or args.show_context:
        _print_risk_query_result(result, show_sql=args.show_sql)
    if args.show_context:
        print()
        print("LLM context JSON:")
        print(context_json)

    client = OllamaClient()
    try:
        model = client.choose_model(args.model)
        generation = client.generate(workbook_risk_prompt(context_json), model=model, temperature=0.0)
    except OllamaUnavailable as exc:
        print(f"Ollama unavailable: {exc}", file=sys.stderr)
        print("The database query completed; start Ollama and install a local model to run the AI summary.", file=sys.stderr)
        return 1

    print()
    print(f"Ollama model: {generation.model}")
    print(f"Database latency: {result.database_latency_ms:.3f} ms")
    print(f"LLM generation latency: {generation.latency_ms:.3f} ms")
    print("Ollama response:")
    print(generation.response)
    return 0


def _llm_benchmark(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    dataset = generate_enterprise_dataset(
        config.customer_count,
        seed=config.seed,
        name=f"synthetic-enterprise-{config.dataset_size}",
    )
    client = OllamaClient()
    try:
        model = client.choose_model(args.model)
    except OllamaUnavailable as exc:
        print(f"Ollama unavailable: {exc}", file=sys.stderr)
        return 1

    database_names = ["sqlite", "duckdb", "postgres"] if args.database == "all" else [args.database]
    all_results = []
    failed = False
    for database in database_names:
        adapter = _adapter(database)
        run_id = utc_run_id(adapter.name, config.dataset_size, "llm")
        print(f"Running LLM response benchmark for {adapter.name} with model {model}...")
        adapter.connect()
        try:
            adapter.reset()
            adapter.seed(dataset)
            runner = LLMResponseBenchmarkRunner(config, context_limit=args.context_limit)
            results = runner.run(adapter, dataset, client, model, run_id)
        except Exception as exc:
            failed = True
            print(f"FAILED {database}: {exc}", file=sys.stderr)
            continue
        finally:
            adapter.close()

        append_results_jsonl(args.results, results)
        write_results_csv(args.results.with_suffix(".csv"), results)
        all_results.extend(results)
        print(f"Run id: {run_id}")
        for result in results:
            line = (
                f"{result.database:6} {result.workload_name:40} "
                f"median={result.median_ms:.3f}ms p95={result.p95_ms:.3f}ms failures={result.failures}"
            )
            if result.workload_name == "account_health_360_answer_accuracy":
                line += (
                    f" precision@k={result.answer_precision_at_k:.3f}"
                    f" recall@k={result.answer_recall_at_k:.3f}"
                    f" rank_accuracy={result.answer_rank_accuracy:.3f}"
                    f" hallucination_rate={result.answer_hallucination_rate:.3f}"
                )
            if result.workload_name == "account_health_360_recommendation_writeback":
                line += f" write_verified={result.write_verified}"
            print(line)

    if all_results:
        print(f"Results appended to: {args.results}")
    return 1 if failed and not all_results else 0


def _print_risk_query_result(result, show_sql: bool = False) -> None:
    print("Tables queried: customers, contracts, contract_services, existing_customer_billing, opportunities, salespeople")
    print(f"SQL parameters: renewal_days={result.params[0]}, limit={result.params[1]}")
    print(f"Database latency: {result.database_latency_ms:.3f} ms")
    print(f"Rows returned: {len(result.rows)}")
    if show_sql:
        print()
        print("SQL:")
        print(result.sql)
    print()
    print("Rows:")
    print(json.dumps(result.rows, indent=2, sort_keys=True, default=str))


def _benchmark(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    dataset = generate_enterprise_dataset(config.customer_count, seed=config.seed, name=f"synthetic-enterprise-{config.dataset_size}")
    adapter = _adapter(args.database)
    run_id = utc_run_id(args.database, config.dataset_size, args.suite)
    adapter.connect()
    try:
        adapter.reset()
        adapter.seed(dataset)
        counts = adapter.row_counts()
        if counts["customers"] != len(dataset.customers):
            raise RuntimeError(f"seed correctness check failed: expected {len(dataset.customers)} customers, got {counts['customers']}")
        runner = BenchmarkRunner(config)
        results = runner.run_suite(adapter, dataset, run_id, suite=args.suite)
        append_results_jsonl(args.results, results)
        write_results_csv(args.results.with_suffix(".csv"), results)
    finally:
        adapter.close()

    print(f"Run id: {run_id}")
    print(f"Results appended to: {args.results}")
    for result in results:
        print(
            f"{result.database:6} {result.workload_name:30} "
            f"median={result.median_ms:.3f}ms p95={result.p95_ms:.3f}ms "
            f"throughput={result.throughput_per_second:.2f}/s failures={result.failures}"
        )
    return 0


def _vector_benchmark(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    vector_limit = args.vectors if args.vectors is not None else config.vector_count
    customer_count = max(config.customer_count, vector_limit)
    dataset = generate_enterprise_dataset(customer_count, seed=config.seed, name=f"synthetic-enterprise-{config.dataset_size}")

    embed_fn = None
    embedding_model_name = EMBEDDING_MODEL_NAME
    embedding_dimension = config.vector_dimension
    if args.embedding_model:
        embed_fn = make_ollama_embed_fn(args.embedding_model)
        probe_vector = embed_fn("embedding dimension probe")
        embedding_model_name = f"ollama:{args.embedding_model}"
        embedding_dimension = len(probe_vector)
        print(f"Using real embeddings from Ollama model {args.embedding_model} ({embedding_dimension} dimensions)")

    records = build_vector_records(dataset, dimension=config.vector_dimension, limit=vector_limit, embed_fn=embed_fn)
    if len(records) < vector_limit:
        raise RuntimeError(f"generated only {len(records)} vector records; expected {vector_limit}")

    database_names = _vector_database_names(args.database)
    all_results = []
    failed = False
    for database in database_names:
        adapter = _vector_adapter(database)
        run_id = utc_run_id(adapter.name, config.dataset_size, "vector")
        print(f"Running vector benchmark for {adapter.name} with {len(records)} vectors...")
        try:
            runner = VectorBenchmarkRunner(config, embedding_model_name=embedding_model_name, embedding_dimension=embedding_dimension)
            results = runner.run(adapter, records, run_id, dataset.name, dataset.stable_hash(), config.seed)
        except Exception as exc:
            failed = True
            print(f"FAILED {database}: {exc}", file=sys.stderr)
            continue
        finally:
            try:
                adapter.close()
            except Exception:
                pass

        all_results.extend(results)
        append_results_jsonl(args.results, results)
        write_results_csv(args.results.with_suffix(".csv"), results)
        print(f"Run id: {run_id}")
        for result in results:
            print(
                f"{result.database:12} {result.workload_name:30} "
                f"median={result.median_ms:.3f}ms p95={result.p95_ms:.3f}ms "
                f"recall@10={result.retrieval_recall_at_10:.3f} failures={result.failures}"
            )

    if all_results:
        print(f"Results appended to: {args.results}")
    return 1 if failed and not all_results else 0


def _adapter(database: str):
    if database == "sqlite":
        return SQLiteAdapter(project_path("data", "generated", "sqlite_baseline.db"))
    if database == "duckdb":
        return DuckDBAdapter(project_path("data", "generated", "duckdb_baseline.duckdb"))
    if database == "postgres":
        return PostgreSQLAdapter()
    raise ValueError(f"Unsupported database: {database}")


def _vector_adapter(database: str):
    base = project_path("data", "generated", "vector")
    if database == "chroma":
        return ChromaAdapter(base / "chroma")
    if database in {"qdrant", "qdrant-local"}:
        return QdrantLocalAdapter(base / "qdrant")
    if database == "qdrant-server":
        return QdrantServerAdapter()
    if database == "lancedb":
        return LanceDBAdapter(base / "lancedb")
    if database == "milvus-lite":
        return MilvusLiteAdapter(base / "milvus_lite.db")
    if database == "pgvector":
        return PgVectorAdapter()
    if database == "weaviate":
        return WeaviateAdapter()
    raise ValueError(f"Unsupported vector database: {database}")


def _vector_database_names(selection: str) -> List[str]:
    embedded = ["chroma", "qdrant-local", "lancedb", "milvus-lite"]
    service = ["pgvector", "qdrant-server", "weaviate"]
    if selection == "embedded":
        return embedded
    if selection == "service":
        return service
    if selection == "all":
        return embedded + service
    return [selection]


def _report(results_path: Path) -> int:
    rows = load_results_jsonl(results_path)
    if not rows:
        print(f"No results found at {results_path}")
        return 0
    print(f"Loaded {len(rows)} result rows from {results_path}")
    for row in rows[-20:]:
        accuracy = ""
        if row.get("workload_name") == "account_health_360_answer_accuracy":
            accuracy = (
                f" precision@k={float(row.get('answer_precision_at_k') or 0.0):.3f}"
                f" recall@k={float(row.get('answer_recall_at_k') or 0.0):.3f}"
                f" hallucination_rate={float(row.get('answer_hallucination_rate') or 0.0):.3f}"
            )
        print(
            f"{row['benchmark_run_id']} {row['database']} {row['workload_name']} "
            f"median={float(row['median_ms']):.3f}ms p95={float(row['p95_ms']):.3f}ms "
            f"recall@10={float(row.get('retrieval_recall_at_10') or 0.0):.3f}{accuracy}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
