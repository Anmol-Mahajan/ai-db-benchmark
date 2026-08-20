# AI Database Benchmark Lab

Local-first benchmark framework for comparing database behavior in AI-heavy systems. The project includes structured baselines for SQLite and DuckDB, local vector benchmarks for Qdrant Local, Chroma, LanceDB, and Milvus Lite, plus service-backed pgvector, Qdrant Server, and Weaviate runs.

PostgreSQL + pgvector, Qdrant Server, and Weaviate are Docker-backed targets and are run only when those services are started explicitly. Remote/cloud databases are not included in the local dashboard comparison.

The main adoption question is whether an LLM-facing database workflow can answer production-shaped business questions over 1M+ synthetic enterprise rows while keeping database reads, LLM reasoning, answer accuracy, and write-back persistence measured separately.

## Hardware Assumptions

The project is designed for an Apple Silicon Mac, especially an M1 with 16 GB unified memory and a 256 GB SSD. Smoke runs use 1,000 synthetic customers by default so the framework can be verified quickly.

The `million` preset targets more than one million total generated enterprise rows across customers, contracts, invoices, opportunities, support tickets, notes, and call transcripts. With the default seed it produces 120,663 customers and 1,000,009 total rows, rather than one million customers.

Python 3.11+ is preferred for the full roadmap. The current MVP code also runs on Python 3.9 because the local system Python in this workspace is 3.9.6.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

For local vector smoke benchmarks:

```bash
python -m pip install -e ".[vector,dev]"
```

## Doctor

```bash
python -m ai_db_benchmark.cli doctor
```

The doctor checks Python, architecture, RAM and disk basics, writable data directories, DuckDB and psutil packages, plus optional Docker and Ollama availability. Optional services are warnings only for this stage.

## Generate Data

```bash
python -m ai_db_benchmark.cli generate-data --size smoke
python -m ai_db_benchmark.cli generate-data --size million
python -m ai_db_benchmark.cli generate-data --customers 250 --seed 42
```

Generated data is written under `data/generated/`, which is ignored by Git.

## Run Smoke Benchmarks

SQLite:

```bash
python -m ai_db_benchmark.cli benchmark --database sqlite --suite all --customers 200 --warmup 1 --iterations 3 --batch-size 25
```

DuckDB:

```bash
python -m ai_db_benchmark.cli benchmark --database duckdb --suite all --customers 200 --warmup 1 --iterations 3 --batch-size 25
```

Results are appended to:

```text
data/results/benchmark_results.jsonl
data/results/benchmark_results.csv
```

No benchmark results are fabricated. The CLI prints only measurements produced by the local run.

## Dashboard

Build a static local front-end from actual benchmark results:

```bash
python -m ai_db_benchmark.cli dashboard
```

Open `dashboard/index.html` in a browser. The compact dashboard shows visual bar/card summaries plus one comparison table covering:

- structured baselines: SQLite, DuckDB
- local vector smoke: Qdrant Local, Chroma, LanceDB, Milvus Lite
- service vector smoke: PostgreSQL + pgvector, Qdrant Server, Weaviate

## Excel Workbook Workload

The workbook in `data/raw/MSP_Sales_Performance_Demo_Data_Updated_With_Contracts.xlsx` can be imported into a local SQLite database for AI workflow testing:

```bash
python -m ai_db_benchmark.cli import-excel
python -m ai_db_benchmark.cli excel-risk-query --limit 5 --renewal-days 120 --show-sql
```

The fixed account-risk query joins these workbook tables:

- `customers`
- `contracts`
- `contract_services`
- `existing_customer_billing`
- `opportunities`
- `salespeople`

The LLM path does not let Ollama write or invent SQL. It sends only the predefined query result as JSON context:

```bash
python -m ai_db_benchmark.cli ollama-excel-risk --limit 5 --show-context
```

Ollama must be running locally at `http://127.0.0.1:11434` with at least one model already installed. The project will not pull models automatically.

## LLM Accuracy And Write-Back Benchmark

Compare local Ollama workflows across the relational baseline databases:

```bash
python -m ai_db_benchmark.cli llm-benchmark --database all --size million --warmup 0 --iterations 1 --context-limit 5 --model qwen3:4b-instruct
```

Each database gets the same deterministic synthetic dataset and the same complex account-health task:

```text
Which accounts need immediate executive attention when combining revenue decline,
renewal exposure, invoice health, support burden, open pipeline, commercial notes,
and recent call activity? Rank the riskiest accounts and recommend the next action
for each.
```

The benchmark stores separate rows for:

- `account_health_360_context_retrieval`
- `account_health_360_ollama_generation`
- `account_health_360_answer_accuracy`
- `account_health_360_recommendation_writeback`
- `account_health_360_end_to_end`

The database step uses an approved `complex_account_health_360` query joining and aggregating customers, salespeople, contracts, invoices, opportunities, support tickets, notes, and call transcripts. Ollama receives only the retrieved JSON context; it is not allowed to invent or execute SQL.

Answer accuracy is scored against the database-ranked result set using strict JSON validation, precision@k, recall@k, rank accuracy, and hallucinated customer-ID rate. Validated recommendations are written to the benchmark-owned `ai_recommendations` table and read back to verify persistence. This means database execution time, local model generation, validation accuracy, database write latency, and end-to-end latency are not mixed together.

## Vector Benchmark Stage

Run a small local vector smoke benchmark:

```bash
python -m ai_db_benchmark.cli vector-benchmark --database chroma --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
python -m ai_db_benchmark.cli vector-benchmark --database qdrant --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
python -m ai_db_benchmark.cli vector-benchmark --database lancedb --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
python -m ai_db_benchmark.cli vector-benchmark --database milvus-lite --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
```

Or run all local vector stores:

```bash
python -m ai_db_benchmark.cli vector-benchmark --database embedded --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
```

The vector stage uses deterministic local hash embeddings for smoke testing. Embeddings are generated outside the measured database operations and fed identically to each vector store. The benchmark records vector count, embedding model, dimension, distance metric, index type, Recall@5, and Recall@10.

Milvus Lite may need permission to bind a local Unix socket in restricted environments.

## Docker Service Benchmarks

Start service-backed databases one at a time or together:

```bash
docker compose up -d postgres
docker compose up -d qdrant
docker compose up -d weaviate
```

Run the remaining local service vector benchmarks:

```bash
python -m ai_db_benchmark.cli vector-benchmark --database pgvector --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
python -m ai_db_benchmark.cli vector-benchmark --database qdrant-server --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
python -m ai_db_benchmark.cli vector-benchmark --database weaviate --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
```

Run all local service-backed vector targets:

```bash
python -m ai_db_benchmark.cli vector-benchmark --database service --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
```

Stop services without deleting volumes:

```bash
docker compose down
```

## Workloads

The structured benchmark covers:

- single customer insert
- batched customer insert
- primary-key customer read
- indexed region filter read
- customer health update
- renewal-risk join across customers, contracts, and support tickets
- complex account-health 360 query across customers, salespeople, contracts, invoices, opportunities, support tickets, notes, and call transcripts
- revenue aggregation by region across customers and invoices

Each workload records median latency, p95, p99, throughput, failures, CPU usage, process RAM, system memory pressure when psutil is available, and database storage size.

The vector benchmark covers:

- vector ingestion
- top-k vector search
- metadata-filtered vector search
- Recall@5 and Recall@10 against exact ground truth
- vector storage size and local resource usage

## Tests

```bash
python -m pytest
```

Default tests do not require PostgreSQL, Qdrant Server, Weaviate, Ollama, or Docker.

## Cleanup

Generated databases and result files are ignored by Git. Remove local generated artifacts manually when you want a fresh run:

```bash
rm -rf data/generated data/results
mkdir -p data/generated data/results
```

Do not delete results you still need for comparison; result files are append-only by design.
