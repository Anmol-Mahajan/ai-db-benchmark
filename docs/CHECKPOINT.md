# AI Database Benchmark Checkpoint

Saved at: 2026-08-20T22:59:00Z

## Current State

The project now contains a local-first AI database benchmark framework with:

- deterministic synthetic enterprise data generation
- SQLite, DuckDB, and PostgreSQL relational baselines (`postgres` adapter, LLM benchmark only)
- vector benchmarks for Chroma, LanceDB, Milvus Lite, Qdrant Local, Qdrant Server, PostgreSQL + pgvector, and Weaviate
- Excel workbook preview/import/query support
- local Ollama response benchmarking
- LLM answer accuracy scoring against the database-ranked ground truth
- AI recommendation write-back and read-back verification through `ai_recommendations`
- compact static dashboard at `dashboard/index.html`
- pytest coverage for adapters, workloads, dashboard, Excel import, vector utilities, metrics, and LLM runner

## Databases In Scope

Currently compared locally:

- SQLite
- DuckDB
- PostgreSQL (relational, LLM benchmark only)
- Chroma
- LanceDB
- Milvus Lite
- PostgreSQL + pgvector
- Qdrant Local
- Qdrant Server
- Weaviate

Pinecone was removed from the local dashboard scope.

## Million-Row Dataset

The `million` preset targets roughly one million generated enterprise rows:

- customers: 120,663
- total rows with seed 42: 1,000,009
- tables: customers, salespeople, contracts, invoices, opportunities, support_tickets, customer_notes, call_transcripts

## Complex LLM Question

```text
Which accounts need immediate executive attention when combining revenue decline,
renewal exposure, invoice health, support burden, open pipeline, commercial notes,
and recent call activity? Rank the riskiest accounts and recommend the next action
for each.
```

The database retrieves context with the `complex_account_health_360` query. Ollama receives only the retrieved JSON context. The runner now validates strict JSON output, scores precision@k, recall@k, rank accuracy, and hallucinated customer-ID rate, then writes validated recommendations into `ai_recommendations` and reads them back.

## Latest 1M-Scale Results

Analytics-only complex query:

| Database | Workload | Median |
|---|---|---:|
| SQLite | complex_account_health_360 | 610.653 ms |
| DuckDB | complex_account_health_360 | 70.250 ms |

Complex LLM workflow with answer accuracy and write-back. `llm-benchmark --database all` now covers SQLite, DuckDB, and PostgreSQL (a dedicated relational `postgres` adapter, distinct from the `pgvector` vector adapter):

| Database | DB context retrieval | Ollama generation | Accuracy | Write/read-back | End-to-end |
|---|---:|---:|---:|---:|---:|
| SQLite | 611.670 ms | 34,523.174 ms | precision@k 1.000 / recall@k 1.000 / rank 1.000 / hallucination 0.000 | 24.662 ms, verified | 35,160.045 ms |
| DuckDB | 59.461 ms | 35,013.261 ms | precision@k 1.000 / recall@k 1.000 / rank 1.000 / hallucination 0.000 | 13.836 ms, verified | 35,086.976 ms |
| PostgreSQL | 623.701 ms | 47,449.985 ms | precision@k 1.000 / recall@k 1.000 / rank 1.000 / hallucination 0.000 | 21.604 ms, verified | 48,096.781 ms |

Run IDs:

- `20260820T215017Z-sqlite-million-llm`
- `20260820T215106Z-duckdb-million-llm`
- `20260820T220851Z-postgres-million-llm`

## Verification

Last full test run:

```bash
.venv/bin/python -m pytest
```

Result:

```text
20 passed
```

Dashboard regenerated with:

```bash
.venv/bin/python -m ai_db_benchmark.cli dashboard
```

## Notes

- Git is initialized with commits on `main`, pushed to `https://github.com/Anmol-Mahajan/ai-db-benchmark`.
- Benchmark results are append-only under `data/results/benchmark_results.jsonl`.
- Docker services (postgres, qdrant, weaviate) must be started via `./scripts/start_services.sh` before running the `postgres` LLM benchmark or service-backed vector benchmarks.
- Generated local database artifacts are under `data/generated/`.
