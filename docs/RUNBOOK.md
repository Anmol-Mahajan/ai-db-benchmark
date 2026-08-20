# Runbook

Use this tomorrow to start, run, view, and stop the local benchmark safely.

## 1. Open The Project

```bash
cd "/Users/anmolmahajan/DB Benchmark"
source .venv/bin/activate
```

## 2. Check The Environment

```bash
python -m ai_db_benchmark.cli doctor
```

Expected basics:

- Docker is available if you want pgvector, Qdrant Server, or Weaviate.
- Ollama is available if you want LLM response benchmarks.
- The installed local model is currently `qwen3:4b-instruct`.

## 3. Start Ollama For LLM Benchmarks

Option A: open the app normally:

```bash
open -a Ollama
```

Then verify:

```bash
/Applications/Ollama.app/Contents/Resources/ollama list
```

You should see:

```text
qwen3:4b-instruct
```

## 4. Start Docker Databases Only If Needed

For service-backed vector DBs:

```bash
./scripts/start_services.sh postgres qdrant weaviate
docker compose ps
```

This starts:

- PostgreSQL + pgvector
- Qdrant Server
- Weaviate

You do not need Docker for:

- SQLite
- DuckDB
- Chroma
- LanceDB
- Milvus Lite
- Qdrant Local

## 5. Run The 1M-Row Structured Benchmark

The `million` preset uses 120,663 customers and produces 1,000,009 total synthetic enterprise rows with seed 42.

SQLite:

```bash
python -m ai_db_benchmark.cli benchmark --database sqlite --suite analytics --size million --warmup 0 --iterations 1 --batch-size 1000
```

DuckDB:

```bash
python -m ai_db_benchmark.cli benchmark --database duckdb --suite analytics --size million --warmup 0 --iterations 1 --batch-size 1000
```

The complex query is:

```text
complex_account_health_360
```

It joins and aggregates:

- customers
- salespeople
- contracts
- invoices
- opportunities
- support_tickets
- customer_notes
- call_transcripts

## 6. Run The 1M-Row LLM Accuracy And Write-Back Benchmark

```bash
python -m ai_db_benchmark.cli llm-benchmark --database all --size million --warmup 0 --iterations 1 --context-limit 5 --model qwen3:4b-instruct
```

The LLM question is:

```text
Which accounts need immediate executive attention when combining revenue decline,
renewal exposure, invoice health, support burden, open pipeline, commercial notes,
and recent call activity? Rank the riskiest accounts and recommend the next action
for each.
```

The benchmark records:

- database context retrieval time
- Ollama generation time
- answer validation latency
- precision@k, recall@k, rank accuracy, and hallucinated customer-ID rate
- recommendation write/read-back latency
- write-back verification into `ai_recommendations`
- end-to-end time

Ollama receives only JSON rows from the approved `complex_account_health_360` query. The model does not generate SQL in the default production-style path.

## 7. Run Vector Benchmarks

Embedded/local vector DBs:

```bash
python -m ai_db_benchmark.cli vector-benchmark --database embedded --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
```

Docker service vector DBs, after starting services:

```bash
python -m ai_db_benchmark.cli vector-benchmark --database service --vectors 100 --customers 100 --warmup 1 --iterations 3 --top-k 10 --dimension 64
```

## 8. Regenerate The Dashboard

```bash
python -m ai_db_benchmark.cli dashboard
open dashboard/index.html
```

The dashboard is compact and visual-heavy with one summary table.

## 9. Stop Everything

Stop Docker DB services only:

```bash
./scripts/stop_services.sh
```

Stop Docker DB services and Ollama:

```bash
./scripts/stop_services.sh --ollama
```

Equivalent manual commands:

```bash
docker compose down
osascript -e 'quit app "Ollama"' || true
pkill -TERM -f '/Applications/Ollama.app' || true
```

## 10. Verify Everything Is Closed

```bash
docker ps
docker compose ps
ps -axo pid,command | rg 'Ollama|ollama|llama-server|postgres|qdrant|weaviate|duckdb|sqlite|ai_db_benchmark'
```

Expected:

- `docker ps` prints no running containers.
- `docker compose ps` shows no running project services.
- the `ps | rg` command should only show the `rg` command itself, or nothing.

## 11. Results Location

Benchmark results are append-only:

```text
data/results/benchmark_results.jsonl
data/results/benchmark_results.csv
```

Generated databases are local:

```text
data/generated/
```
