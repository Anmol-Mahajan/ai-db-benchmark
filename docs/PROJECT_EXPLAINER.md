# AI Database Benchmark — Project Explainer

## What this is

A local-first benchmark lab that measures how different databases behave when they sit underneath an AI agent, not just how fast they run plain CRUD. Everything runs on a single Apple Silicon Mac (M1, 16 GB RAM). No results are fabricated or estimated — every number in the dashboard comes from an actual measured run, appended to `data/results/benchmark_results.jsonl`.

## Why I built it

Most "database for AI" comparisons only measure vector search recall or raw query latency in isolation. They rarely separate:

1. how fast the database answers the question the agent actually needs answered,
2. how much of the total time is really the LLM thinking, not the database,
3. whether the model's answer is actually correct, and
4. whether writing the model's output back to the database is fast and verified.

This project measures all four, side by side, on the same dataset and the same question, so the comparison is fair.

## The dataset

A deterministic synthetic enterprise dataset (seeded, so it's reproducible):

- `customers`, `salespeople`, `contracts`, `invoices`, `opportunities`, `support_tickets`, `customer_notes`, `call_transcripts`
- The `million` preset produces 120,663 customers and 1,000,009 total rows.

## The workflows measured

- **CRUD**: single/batched inserts, point reads, filtered reads, updates.
- **Analytics**: a `complex_account_health_360` query joining and aggregating all eight tables — the same query used to feed the LLM.
- **Vector search**: ingestion, top-k search, metadata-filtered search, Recall@5 / Recall@10 against exact ground truth, on 100 deterministic hash embeddings.
- **AI-agent workflow**: the full production-style path —
  1. retrieve context with the approved SQL query (no LLM-generated SQL, ever),
  2. send only that JSON context to a local Ollama model (`qwen3:4b-instruct`),
  3. validate the model's strict-JSON answer and score it against the database-ranked ground truth (precision@k, recall@k, rank accuracy, hallucinated-ID rate),
  4. write the validated recommendation back into an `ai_recommendations` table and read it back to confirm persistence.

## Databases compared (10 total)

| Database | Role |
|---|---|
| SQLite | embedded relational baseline |
| DuckDB | embedded analytical baseline |
| PostgreSQL | Docker relational service (LLM benchmark target) |
| PostgreSQL + pgvector | relational + vector in one system |
| Qdrant (local & server) | purpose-built vector database |
| Weaviate | AI-native vector database |
| Chroma | embedded retrieval store |
| Milvus Lite | embedded ANN vector database |
| LanceDB | embedded vector + scalar store |

## Key results (1M-row dataset)

**Structured analytics query, same complex join, same data:**

| Database | Median latency |
|---|---:|
| DuckDB | 70.25 ms |
| SQLite | 610.65 ms |

DuckDB was roughly 8–9x faster than SQLite on the exact same analytical join. That gap is invisible at small scale and only shows up once you're joining across a million rows.

**Full LLM agent workflow, end-to-end:**

| Database | DB retrieval | Ollama generation | End-to-end |
|---|---:|---:|---:|
| SQLite | 611.67 ms | 34,523.17 ms | 35,160.05 ms |
| DuckDB | 59.46 ms | 35,013.26 ms | 35,086.98 ms |
| PostgreSQL | 623.70 ms | 47,449.98 ms | 48,096.78 ms |

Once the LLM starts generating, the database gap almost disappears into the noise — local LLM inference is the dominant cost, not the database. That said, this only holds for a single request at a time; the database gap reappears immediately under concurrent load.

**Answer quality (all three databases, same question):** precision@k 1.000, recall@k 1.000, rank accuracy 1.000, hallucination rate 0.000. Write-back to `ai_recommendations` verified in every run.

**Vector search recall@10, across 7 vector databases:** every database returned 1.000. At this scale (100 vectors), recall isn't the differentiator between vector databases — deployment mode, operational overhead, and cost are.

## Re-testing with real embeddings, not just hash vectors

The vector benchmark's default embedding is a deterministic hash function — fast and reproducible, but not semantically meaningful. To see how the databases behave under a production-shaped workload, I re-ran all 7 vector databases with real 768-dimension embeddings from a local Ollama model (`nomic-embed-text`), ingesting and searching 1,000 real embeddings each (`vector-benchmark --embedding-model nomic-embed-text`):

| Database | Ingest (1,000 vectors) | Top-k search | Recall@10 |
|---|---:|---:|---:|
| LanceDB | 15.93 ms | 3.90 ms | 1.000 |
| Milvus Lite | 186.48 ms | 1.25 ms | 1.000 |
| PostgreSQL + pgvector | 309.66 ms | 6.04 ms | 1.000 |
| Chroma | 651.72 ms | 2.73 ms | 1.000 |
| Qdrant Server | 714.02 ms | 7.28 ms | 1.000 |
| Weaviate | 936.97 ms | 6.27 ms | 1.000 |
| Qdrant Local | 973.42 ms | 2.02 ms | 1.000 |

Recall stayed perfect across every database, even with real semantic embeddings — so at this scale, recall still isn't what separates them. Ingest latency is where the real gap shows up: LanceDB was roughly 60x faster than Qdrant Local for the same 1,000 real embeddings, and the embedded, file-based stores (LanceDB, Milvus Lite) meaningfully outpaced the Docker-service stores (Qdrant Server, Weaviate) on ingest, while search latency differences were much smaller across the board.

## A design decision worth explaining: why the LLM never touches raw rows

The AI-agent workflow does not let the model query the database or embed individual rows. It retrieves context through one approved SQL join across customers, contracts, invoices, support tickets, notes, and call transcripts, and only that joined JSON is sent to the model.

This mirrors a common mistake in real-world RAG systems: teams vector-embed relational rows directly — e.g. one row per order — and lose the surrounding context (the order header, the customer, the related line items). A single record from a header-detail relational structure rarely represents the full transaction. The fix, whether you're doing retrieval through SQL (as this project does) or through embeddings, is the same: assemble the full related record — header + details — into one unit (a join, or a flattened Markdown/JSON document) before it goes to the model or into the vector index.

## How to run it

```bash
source .venv/bin/activate
python -m ai_db_benchmark.cli doctor
python -m ai_db_benchmark.cli generate-data --size million
python -m ai_db_benchmark.cli benchmark --database duckdb --suite analytics --size million --warmup 0 --iterations 1
python -m ai_db_benchmark.cli llm-benchmark --database all --size million --context-limit 5 --model qwen3:4b-instruct
python -m ai_db_benchmark.cli dashboard
open dashboard/index.html
```

Full step-by-step instructions are in [docs/RUNBOOK.md](RUNBOOK.md). Current project state and latest numbers are in [docs/CHECKPOINT.md](CHECKPOINT.md).

## Scope and honesty about limits

- This is a single-node, single-request benchmark on one Apple Silicon machine — not a concurrency or production-load study.
- Vector benchmarks default to small (100-vector) deterministic hash embeddings for fast smoke testing; the `--embedding-model` flag switches to real local Ollama embeddings but was only tested up to 1,000 vectors here, not at million-row scale.
- Ollama generation time depends heavily on local hardware and the specific model (`qwen3:4b-instruct` here); it is not representative of hosted LLM APIs.
- No results are fabricated — everything shown in the dashboard is a real measured run, appended to `data/results/benchmark_results.jsonl`.

## Source

<https://github.com/Anmol-Mahajan/ai-db-benchmark>
