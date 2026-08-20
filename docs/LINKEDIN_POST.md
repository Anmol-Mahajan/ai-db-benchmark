# LinkedIn Post Draft

Copy the text below directly into LinkedIn. Attach `dashboard/Measurement Summary.png` and `dashboard/Performance Comparison.png` as the two images (retake these from the dashboard if you want the new vector-search context-retrieval chart included).

---

I kept seeing the same claim in AI engineering content: "just add a vector database." So I spent a week measuring what actually happens when you put a database underneath an AI agent, instead of taking that on faith.

I built a local benchmark lab on my M1 Mac: the same synthetic dataset (1,000,009 rows across customers, contracts, invoices, support tickets, notes, and call transcripts), the same complex question ("which accounts need executive attention right now, combining revenue decline, renewal risk, support load, and recent calls"), and the same local LLM (qwen3:4b via Ollama), run against 10 different databases — SQLite, DuckDB, PostgreSQL, and seven vector stores (Chroma, LanceDB, Milvus Lite, Qdrant, Weaviate, pgvector).

A few things I didn't expect:

→ DuckDB answered the complex analytical join in 70ms. SQLite took 610ms. Same query, same 1M rows, same machine — an 8-9x gap that's easy to miss if you only ever test with small data.

→ That gap almost disappears once the LLM starts talking. End-to-end, Ollama generation took 35-48 seconds regardless of which database sat underneath it — including PostgreSQL, whose own query was just as fast as SQLite's; its longer end-to-end time tracked back to local machine load, not the database.

→ Every vector database returned perfect recall@10 on the retrieval task. At this scale, accuracy isn't the differentiator — operational overhead, deployment mode, and cost are.

→ I also swapped the SQL join for vector search: real embeddings over the same customer notes and call transcripts, feeding the LLM directly. Retrieval dropped from ~620ms to 47ms — but the accounts it surfaced had zero overlap with the SQL-ranked risk list. Fast retrieval isn't the same as the right context: a single note or call transcript never tells the whole story, the way a join across revenue, support, and pipeline data does.

Everything here is measured, not modeled — no fabricated numbers, all results are append-only and reproducible. Fully open source: https://github.com/Anmol-Mahajan/ai-db-benchmark

#AI #Databases #RAG #LLM #Postgres #VectorDatabase #Benchmarking
