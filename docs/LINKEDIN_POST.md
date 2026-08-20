# LinkedIn Post Draft

Copy the text below directly into LinkedIn. Attach `dashboard/screenshot-hero.png` and `dashboard/screenshot-comparison.png` as the two images.

---

I kept seeing the same claim in AI engineering content: "just add a vector database." So I spent a week measuring what actually happens when you put a database underneath an AI agent, instead of taking that on faith.

I built a local benchmark lab on my M1 Mac: the same synthetic dataset (1,000,009 rows across customers, contracts, invoices, support tickets, notes, and call transcripts), the same complex question ("which accounts need executive attention right now, combining revenue decline, renewal risk, support load, and recent calls"), and the same local LLM (qwen3:4b via Ollama), run against 10 different databases — SQLite, DuckDB, PostgreSQL, and seven vector stores (Chroma, LanceDB, Milvus Lite, Qdrant, Weaviate, pgvector).

A few things I didn't expect:

→ DuckDB answered the complex analytical join in 70ms. SQLite took 610ms. Same query, same 1M rows, same machine — an 8-9x gap that's easy to miss if you only ever test with small data.

→ That gap almost disappears once the LLM starts talking. End-to-end, Ollama generation took 35-48 seconds regardless of which database sat underneath it. At today's local-LLM speeds, the database is rarely your bottleneck — but it will be the moment you're doing this at real traffic, not one request at a time.

→ Every vector database returned perfect recall@10 on the retrieval task. At this scale, accuracy isn't the differentiator — operational overhead, deployment mode, and cost are.

One design choice that mattered: the LLM never touches the raw tables. Context comes from one approved SQL join across customers, contracts, invoices, support tickets, notes, and calls — because a single order row (or a single customer row) never tells the whole story. Header-detail relational data has to be assembled before it's handed to a model, whether that's through a join like this or through flattening it into one document before embedding.

Everything here is measured, not modeled — no fabricated numbers, all results are append-only and reproducible. Fully open source: https://github.com/Anmol-Mahajan/ai-db-benchmark

#AI #Databases #RAG #LLM #Postgres #VectorDatabase #Benchmarking
