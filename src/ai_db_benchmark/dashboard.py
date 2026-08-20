from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from ai_db_benchmark.benchmark.results import load_results_jsonl
from ai_db_benchmark.config import project_path


DATABASE_MATRIX: List[Dict[str, str]] = [
    {
        "name": "SQLite",
        "deployment": "embedded local",
        "role": "transactional relational baseline",
        "stage": "current MVP",
        "workloads": "CRUD, reads, updates, LLM accuracy, recommendation write-back",
    },
    {
        "name": "DuckDB",
        "deployment": "embedded local",
        "role": "analytical SQL baseline",
        "stage": "current MVP",
        "workloads": "joins, aggregations, scans, LLM accuracy, recommendation write-back",
    },
    {
        "name": "PostgreSQL + pgvector",
        "deployment": "local Docker",
        "role": "relational and vector in one system",
        "stage": "service vector smoke",
        "workloads": "pgvector ingestion, search, filtering, Recall@k",
    },
    {
        "name": "PostgreSQL",
        "deployment": "local Docker",
        "role": "production-style relational database",
        "stage": "current LLM service target",
        "workloads": "structured joins, reads, writes, LLM accuracy",
    },
    {
        "name": "Qdrant Local",
        "deployment": "embedded/local files",
        "role": "purpose-built vector database",
        "stage": "current vector smoke",
        "workloads": "vector ingestion, search, filtering, Recall@k",
    },
    {
        "name": "Weaviate",
        "deployment": "local Docker",
        "role": "AI/vector database with hybrid search options",
        "stage": "service vector smoke",
        "workloads": "semantic vector search and metadata filtering",
    },
    {
        "name": "Chroma",
        "deployment": "embedded local",
        "role": "application-embedded retrieval store",
        "stage": "current vector smoke",
        "workloads": "local collections, vector search, filtering",
    },
    {
        "name": "Milvus Lite",
        "deployment": "embedded local",
        "role": "local Milvus vector database mode",
        "stage": "current vector smoke",
        "workloads": "vector ingestion, ANN search, filtering",
    },
    {
        "name": "LanceDB",
        "deployment": "embedded local",
        "role": "local vector and scalar data store",
        "stage": "current vector smoke",
        "workloads": "embedded vector retrieval and filtering",
    },
    {
        "name": "Qdrant Server",
        "deployment": "local Docker",
        "role": "purpose-built vector database service",
        "stage": "service vector smoke",
        "workloads": "service-mode ANN search, filtering, Recall@k",
    },
]


def generate_dashboard(results_path: Path, output_path: Path) -> Path:
    rows = load_results_jsonl(results_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = (
        DASHBOARD_TEMPLATE.replace("__RESULTS_JSON__", _script_safe_json(rows))
        .replace("__DATABASE_MATRIX_JSON__", _script_safe_json(DATABASE_MATRIX))
        .replace("__SOURCE_PATH__", _display_path(results_path))
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _script_safe_json(value: object) -> str:
    return json.dumps(value, sort_keys=True).replace("</", "<\\/")


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_path().resolve()))
    except ValueError:
        return path.name


DASHBOARD_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Database Benchmark Results</title>
  <style>
    :root {
      color-scheme: light;
      --paper: #fbfaf7;
      --ink: #171717;
      --muted: #62605a;
      --line: #d9d3c7;
      --line-strong: #9f9688;
      --surface: #ffffff;
      --panel: #f2efe8;
      --rail: #22201d;
      --teal: #087f7a;
      --green: #15803d;
      --amber: #b7791f;
      --red: #b42318;
      --blue: #2563eb;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Avenir Next, Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(23, 23, 23, 0.035) 1px, transparent 1px) 0 0 / 48px 48px,
        linear-gradient(0deg, rgba(23, 23, 23, 0.025) 1px, transparent 1px) 0 0 / 48px 48px,
        var(--paper);
      letter-spacing: 0;
    }

    .wrap {
      width: min(1240px, calc(100% - 32px));
      margin: 0 auto;
    }

    header {
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(242, 239, 232, 0.92)),
        var(--paper);
      border-bottom: 1px solid var(--line);
    }

    header::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(90deg, transparent 0 8%, rgba(8, 127, 122, 0.16) 8% 8.35%, transparent 8.35% 100%),
        linear-gradient(90deg, transparent 0 38%, rgba(183, 121, 31, 0.16) 38% 38.25%, transparent 38.25% 100%),
        linear-gradient(90deg, transparent 0 71%, rgba(37, 99, 235, 0.14) 71% 71.2%, transparent 71.2% 100%);
      pointer-events: none;
    }

    .hero {
      position: relative;
      min-height: 390px;
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(390px, 0.95fr);
      gap: 44px;
      align-items: center;
      padding: 44px 0 34px;
    }

    .eyebrow {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 18px;
      color: var(--teal);
      font-size: 0.78rem;
      font-weight: 800;
      text-transform: uppercase;
    }

    .eyebrow::before {
      content: "";
      width: 42px;
      height: 2px;
      background: var(--teal);
    }

    h1 {
      margin: 0;
      font-family: Georgia, Charter, "Times New Roman", serif;
      font-size: clamp(2.55rem, 6.2vw, 5.8rem);
      line-height: 0.92;
      font-weight: 700;
      max-width: 780px;
    }

    .subtle {
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 0.98rem;
      line-height: 1.55;
      max-width: 780px;
    }

    .hero-copy {
      font-size: 1.08rem;
      max-width: 700px;
      margin-top: 22px;
    }

    .hero-board {
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.78);
      border-radius: 8px;
      box-shadow: 0 22px 60px rgba(23, 23, 23, 0.09);
      overflow: hidden;
    }

    .board-row {
      display: grid;
      grid-template-columns: 110px 1fr auto;
      gap: 14px;
      align-items: center;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
    }

    .board-row:last-child { border-bottom: 0; }

    .board-key {
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 800;
      text-transform: uppercase;
    }

    .board-value {
      font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
      font-size: 1.1rem;
      font-weight: 800;
    }

    .board-note {
      color: var(--muted);
      font-size: 0.78rem;
      text-align: right;
    }

    .status {
      display: inline-flex;
      gap: 8px;
      align-items: center;
      margin-top: 26px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      color: var(--muted);
      font-size: 0.84rem;
    }

    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--green);
    }

    section {
      padding: 32px 0;
      border-bottom: 1px solid var(--line);
    }

    section.band {
      background: rgba(255, 255, 255, 0.58);
    }

    .section-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin-bottom: 18px;
    }

    h2 {
      margin: 0;
      font-size: 1.22rem;
      line-height: 1.2;
      font-weight: 850;
    }

    .kpis {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }

    .kpi,
    .panel,
    .insight {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }

    .kpi {
      padding: 18px;
      min-height: 118px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }

    .kpi span {
      display: block;
      color: var(--muted);
      font-size: 0.76rem;
      font-weight: 800;
      text-transform: uppercase;
      margin-bottom: 6px;
    }

    .kpi strong {
      display: block;
      font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
      font-size: clamp(1.45rem, 2.4vw, 2.1rem);
      line-height: 1.1;
    }

    .kpi small {
      color: var(--muted);
      line-height: 1.35;
    }

    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(360px, 0.92fr);
      gap: 16px;
      align-items: start;
    }

    .visual-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }

    .db-card {
      position: relative;
      min-height: 176px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      overflow: hidden;
    }

    .db-card::after {
      content: "";
      position: absolute;
      left: 18px;
      right: 18px;
      bottom: 16px;
      height: 8px;
      border-radius: 999px;
      background:
        linear-gradient(90deg, var(--card-color, var(--teal)) var(--measured-width, 100%), #e7e1d6 var(--measured-width, 100%));
    }

    .db-card h3 {
      margin: 0 0 8px;
      font-size: 1.04rem;
      line-height: 1.15;
    }

    .db-card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.42;
      font-size: 0.88rem;
    }

    .db-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-top: 14px;
      padding-bottom: 18px;
    }

    .phase-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(340px, 0.95fr);
      gap: 16px;
      align-items: stretch;
    }

    .phase-board {
      display: grid;
      gap: 12px;
      padding: 16px;
    }

    .phase-row {
      display: grid;
      grid-template-columns: minmax(150px, 210px) minmax(0, 1fr) 96px;
      gap: 12px;
      align-items: center;
      min-height: 42px;
    }

    .phase-label {
      color: var(--muted);
      font-size: 0.84rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .phase-value {
      font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
      font-weight: 800;
      text-align: right;
      font-size: 0.88rem;
    }

    .scope-map {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      padding: 16px;
    }

    .scope-node {
      min-height: 116px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
    }

    .scope-node strong {
      display: block;
      margin-bottom: 8px;
      font-size: 0.95rem;
    }

    .scope-node span {
      color: var(--muted);
      line-height: 1.35;
      font-size: 0.84rem;
    }

    .triple {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }

    .insight {
      padding: 18px;
      min-height: 148px;
    }

    .insight b {
      display: block;
      margin-bottom: 16px;
      font-size: 0.8rem;
      text-transform: uppercase;
      color: var(--muted);
    }

    .insight strong {
      display: block;
      font-size: 1.72rem;
      line-height: 1.08;
    }

    .insight p {
      margin: 12px 0 0;
      color: var(--muted);
      line-height: 1.45;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }

    .table-wrap {
      width: 100%;
      overflow-x: auto;
    }

    .table-wrap table {
      min-width: 1080px;
    }

    th, td {
      padding: 12px 13px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }

    th {
      color: var(--muted);
      font-size: 0.76rem;
      text-transform: uppercase;
      font-weight: 700;
      background: var(--panel);
    }

    tr:last-child td { border-bottom: 0; }

    .panel-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 13px 15px;
      border-bottom: 1px solid var(--line);
      font-weight: 820;
    }

    .chart {
      display: grid;
      gap: 9px;
      padding: 16px;
    }

    .bar-row {
      display: grid;
      grid-template-columns: minmax(170px, 260px) minmax(0, 1fr) 108px;
      gap: 10px;
      align-items: center;
      min-height: 34px;
    }

    .bar-label {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--muted);
      font-size: 0.84rem;
    }

    .bar-track {
      position: relative;
      height: 13px;
      border-radius: 6px;
      background: #e7e1d6;
      overflow: hidden;
    }

    .bar-fill {
      position: absolute;
      inset: 0 auto 0 0;
      width: var(--width);
      background: var(--fill, var(--teal));
    }

    .badge {
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 3px 8px;
      font-size: 0.76rem;
      color: var(--muted);
      background: #fff;
      white-space: nowrap;
    }

    .badge.current { color: var(--green); border-color: #a7d7b8; background: #f0fbf4; }
    .badge.next { color: var(--teal); border-color: #9ed7d5; background: #effafa; }
    .badge.optional { color: var(--amber); border-color: #e1c482; background: #fff8e8; }
    .badge.llm { color: var(--blue); border-color: #b5c8ff; background: #f1f5ff; }

    .empty {
      padding: 32px;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 8px;
      background: var(--surface);
    }

    footer {
      padding: 22px 0 32px;
      color: var(--muted);
      font-size: 0.84rem;
    }

    code {
      font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
      background: #eee7da;
      padding: 1px 5px;
      border-radius: 5px;
    }

    @media (max-width: 860px) {
      .hero, .grid, .triple, .visual-grid, .phase-grid, .scope-map { grid-template-columns: 1fr; }
      .hero { min-height: 0; padding-top: 34px; }
      .section-head { align-items: start; flex-direction: column; }
      .kpis { grid-template-columns: 1fr 1fr; }
      .bar-row { grid-template-columns: 1fr; gap: 5px; }
      .phase-row { grid-template-columns: 1fr; gap: 6px; }
      .phase-value { text-align: left; }
      .board-row { grid-template-columns: 1fr; gap: 6px; }
      .board-note { text-align: left; }
      .status { white-space: normal; }
      table { font-size: 0.84rem; }
      th, td { padding: 9px 8px; }
    }

    @media (max-width: 560px) {
      .kpis { grid-template-columns: 1fr; }
      h1 { font-size: 2.45rem; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <div>
        <div class="eyebrow">Apple Silicon local benchmark</div>
        <h1>AI database systems, measured end to end.</h1>
        <p class="subtle hero-copy">A local-first benchmark report separating database execution, vector retrieval, Ollama response latency, answer accuracy, and recommendation write-back over a complex account-health workload.</p>
        <div class="status"><span class="dot"></span><span id="statusText">Loading measured results</span></div>
      </div>
      <div class="hero-board" id="heroBoard"></div>
    </div>
  </header>

  <main>
    <section class="band">
      <div class="wrap">
        <div class="kpis" id="kpis"></div>
      </div>
    </section>

    <section>
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Executive Readout</h2>
            <p class="subtle">Latest local result rows distilled for a shareable benchmark snapshot.</p>
          </div>
          <span class="badge current">Measured only</span>
        </div>
        <div class="triple" id="insightsArea"></div>
      </div>
    </section>

    <section>
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Databases Compared</h2>
            <p class="subtle">Measured local databases are shown as visual tiles across structured SQL, vector search, local LLM accuracy, and write-back phases.</p>
          </div>
          <span class="badge current">9 measured locally</span>
        </div>
        <div class="visual-grid" id="databaseCards"></div>
      </div>
    </section>

    <section>
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Performance Map</h2>
            <p class="subtle">Visual readout across structured SQL, vector retrieval, local Ollama response, accuracy, and write-back phases.</p>
          </div>
          <span class="badge next">No fabricated rows</span>
        </div>
        <div id="performanceArea"></div>
      </div>
    </section>

    <section>
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Comparison Summary</h2>
            <p class="subtle">One table summarising the important factors that decide benchmark performance.</p>
          </div>
          <span class="badge current">Single table</span>
        </div>
        <div id="measuredTableArea"></div>
      </div>
    </section>
  </main>

  <footer>
    <div class="wrap">Source: __SOURCE_PATH__</div>
  </footer>

  <script>
    const RESULTS = __RESULTS_JSON__;
    const DATABASE_MATRIX = __DATABASE_MATRIX_JSON__;

    const fmtMs = value => `${Number(value || 0).toFixed(3)} ms`;
    const fmtRate = value => `${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}/s`;
    const fmtNumber = value => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 });
    const parseNotes = row => {
      try { return row.notes ? JSON.parse(row.notes) : {}; } catch { return {}; }
    };

    function latestRows(rows) {
      if (!rows.length) return [];
      const runIds = [...new Set(rows.map(row => row.benchmark_run_id))];
      const latestByDb = new Map();
      for (const runId of runIds) {
        const db = rows.find(row => row.benchmark_run_id === runId)?.database;
        if (db) latestByDb.set(db, runId);
      }
      return rows.filter(row => latestByDb.get(row.database) === row.benchmark_run_id);
    }

    function fastest(rows, workloadName) {
      const matches = latestRows(rows).filter(row => row.workload_name === workloadName && Number(row.failures || 0) === 0);
      return matches.sort((a, b) => Number(a.median_ms || 0) - Number(b.median_ms || 0))[0];
    }

    function latestAgentRows(rows) {
      return latestRows(rows.filter(row => row.workload_category === "ai_agent"));
    }

    function latestVectorRows(rows) {
      return latestRows(rows.filter(row => row.workload_category === "vector"));
    }

    function shortWorkloadName(name) {
      return name
        .replace("account_risk_", "")
        .replace("account_health_360_", "360 ")
        .replace(/_/g, " ");
    }

    function renderHero(rows) {
      const context = fastest(rows.filter(row => row.workload_category === "ai_agent"), "account_health_360_context_retrieval") || fastest(rows.filter(row => row.workload_category === "ai_agent"), "account_risk_context_retrieval");
      const e2e = fastest(rows.filter(row => row.workload_category === "ai_agent"), "account_health_360_end_to_end") || fastest(rows.filter(row => row.workload_category === "ai_agent"), "account_risk_end_to_end");
      const accuracy = latestAgentRows(rows).find(row => row.workload_name === "account_health_360_answer_accuracy");
      const vectorRows = latestVectorRows(rows);
      const bestRecall = vectorRows.length ? Math.max(...vectorRows.map(row => Number(row.retrieval_recall_at_10 || 0))) : 0;
      const model = latestAgentRows(rows).map(row => parseNotes(row).llm_model).find(Boolean) || "not recorded";
      document.getElementById("heroBoard").innerHTML = [
        ["Fastest DB phase", context ? context.database : "pending", context ? fmtMs(context.median_ms) : "run llm-benchmark"],
        ["Fastest E2E LLM", e2e ? e2e.database : "pending", e2e ? fmtMs(e2e.median_ms) : "run llm-benchmark"],
        ["AI Precision@k", accuracy ? Number(accuracy.answer_precision_at_k || 0).toFixed(3) : "pending", accuracy ? `${displayDatabaseName(accuracy.database)} answer scoring` : "run llm-benchmark"],
        ["Best Recall@10", bestRecall ? bestRecall.toFixed(3) : "pending", `${vectorRows.length} vector DBs`],
        ["Local model", model, "Ollama"],
      ].map(([key, value, note]) => `<div class="board-row">
        <div class="board-key">${key}</div>
        <div class="board-value">${value}</div>
        <div class="board-note">${note}</div>
      </div>`).join("");
    }

    function renderKpis(rows) {
      const dbs = new Set(rows.map(row => row.database));
      const vectorDbs = new Set(rows.filter(row => row.workload_category === "vector").map(row => row.database));
      const agentDbs = new Set(rows.filter(row => row.workload_category === "ai_agent").map(row => row.database));
      const failures = rows.reduce((sum, row) => sum + Number(row.failures || 0), 0);
      document.getElementById("statusText").textContent = rows.length ? `${rows.length} measured rows loaded` : "No measured results yet";
      document.getElementById("kpis").innerHTML = [
        ["Measured rows", rows.length, "Append-only local results"],
        ["Databases active", dbs.size, "Structured, vector, and AI-agent"],
        ["Vector DBs active", vectorDbs.size, "Recall-aware retrieval"],
        ["LLM DBs active", agentDbs.size, `${failures} recorded failures`],
      ].map(([label, value, note]) => `<div class="kpi"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join("");
    }

    function renderInsights(rows) {
      const context = fastest(rows.filter(row => row.workload_category === "ai_agent"), "account_health_360_context_retrieval") || fastest(rows.filter(row => row.workload_category === "ai_agent"), "account_risk_context_retrieval");
      const generation = fastest(rows.filter(row => row.workload_category === "ai_agent"), "account_health_360_ollama_generation") || fastest(rows.filter(row => row.workload_category === "ai_agent"), "account_risk_ollama_generation");
      const accuracy = latestAgentRows(rows).find(row => row.workload_name === "account_health_360_answer_accuracy");
      const vectorRows = latestVectorRows(rows);
      const vectorMedian = vectorRows.length ? vectorRows.reduce((sum, row) => sum + Number(row.median_ms || 0), 0) / vectorRows.length : 0;
      const recallAverage = vectorRows.length ? vectorRows.reduce((sum, row) => sum + Number(row.retrieval_recall_at_10 || 0), 0) / vectorRows.length : 0;
      document.getElementById("insightsArea").innerHTML = [
        ["DB context leader", context ? `${context.database} · ${fmtMs(context.median_ms)}` : "Pending", "Fastest measured database phase for the complex account-health workflow."],
        ["LLM generation cost", generation ? `${fmtMs(generation.median_ms)}` : "Pending", generation ? `${generation.database} with ${parseNotes(generation).llm_model || "local Ollama"}` : "Run the local LLM benchmark."],
        ["AI answer accuracy", accuracy ? `${Number(accuracy.answer_precision_at_k || 0).toFixed(3)} precision@k` : "Pending", accuracy ? `${Number(accuracy.answer_recall_at_k || 0).toFixed(3)} recall@k, ${Number(accuracy.answer_hallucination_rate || 0).toFixed(3)} hallucination rate.` : "Run the local LLM benchmark."],
      ].map(([label, value, copy]) => `<div class="insight"><b>${label}</b><strong>${value}</strong><p>${copy}</p></div>`).join("");
    }

    function displayDatabaseName(name) {
      return {
        "sqlite": "SQLite",
        "duckdb": "DuckDB",
        "postgres": "PostgreSQL",
        "chroma": "Chroma",
        "lancedb": "LanceDB",
        "milvus-lite": "Milvus Lite",
        "pgvector": "PostgreSQL + pgvector",
        "qdrant-local": "Qdrant Local",
        "qdrant-server": "Qdrant Server",
        "weaviate": "Weaviate",
      }[name] || name;
    }

    function databaseColor(name) {
      if (["sqlite", "duckdb"].includes(name)) return "var(--teal)";
      if (name === "postgres") return "var(--blue)";
      if (["pgvector", "qdrant-server", "weaviate"].includes(name)) return "var(--blue)";
      return "var(--green)";
    }

    function databaseMode(name) {
      if (["sqlite", "duckdb"].includes(name)) return "Structured baseline";
      if (name === "postgres") return "Docker relational service";
      if (["pgvector", "qdrant-server", "weaviate"].includes(name)) return "Docker service vector";
      return "Embedded vector";
    }

    function renderDatabaseCards(rows) {
      const measured = new Set(rows.map(row => row.database));
      const measuredNames = [...measured].sort();
      const cards = measuredNames.map(name => {
        const count = rows.filter(row => row.database === name).length;
        const categories = [...new Set(rows.filter(row => row.database === name).map(row => row.workload_category))].join(", ");
        return {
          name: displayDatabaseName(name),
          mode: databaseMode(name),
          note: categories || "measured locally",
          count,
          measured: true,
          color: databaseColor(name),
        };
      });

      document.getElementById("databaseCards").innerHTML = cards.map(card => `<article class="db-card" style="--card-color:${card.color}; --measured-width:${card.measured ? "100%" : "38%"}">
        <h3>${card.name}</h3>
        <p>${card.mode}</p>
        <div class="db-meta">
          <span class="badge ${card.measured ? "current" : "optional"}">${card.measured ? "measured" : "optional"}</span>
          <span class="badge next">${card.count} result rows</span>
        </div>
        <p>${card.note}</p>
      </article>`).join("");
    }

    function renderPerformanceMap(rows) {
      const structured = latestRows(rows.filter(row => row.workload_category !== "vector" && row.workload_category !== "ai_agent"));
      const vectors = latestVectorRows(rows);
      const agents = latestAgentRows(rows);
      const latest = structured.concat(vectors, agents);
      if (!latest.length) {
        document.getElementById("performanceArea").innerHTML = `<div class="empty">No measured result rows yet.</div>`;
        return;
      }
      const ordered = latest
        .slice()
        .sort((a, b) => Number(a.median_ms || 0) - Number(b.median_ms || 0))
        .slice(0, 12);
      const maxMedian = Math.max(...ordered.map(row => Number(row.median_ms || 0)), 0.001);
      const bars = ordered.map(row => {
        const width = Math.max(2, (Number(row.median_ms || 0) / maxMedian) * 100);
        const fill = row.workload_category === "ai_agent" ? "var(--blue)" : row.workload_category === "vector" ? "var(--green)" : "var(--teal)";
        return `<div class="phase-row">
          <div class="phase-label">${displayDatabaseName(row.database)} · ${shortWorkloadName(row.workload_name)}</div>
          <div class="bar-track"><div class="bar-fill" style="--width:${width}%; --fill:${fill}"></div></div>
          <div class="phase-value">${fmtMs(row.median_ms)}</div>
        </div>`;
      }).join("");
      const scopeNodes = [
        ["Structured", `${new Set(structured.map(row => row.database)).size} DBs`, "CRUD, joins, updates, and aggregations."],
        ["Vector", `${new Set(vectors.map(row => row.database)).size} DBs`, "Ingestion, top-k search, filters, Recall@k."],
        ["LLM", `${new Set(agents.map(row => row.database)).size} DBs`, "Context retrieval, generation, accuracy, write-back."],
        ["Scale", "1M-row ready", "The million preset targets roughly one million total rows."],
      ].map(([label, value, note]) => `<div class="scope-node"><strong>${label}: ${value}</strong><span>${note}</span></div>`).join("");
      document.getElementById("performanceArea").innerHTML = `<div class="phase-grid">
        <div class="panel">
          <div class="panel-title"><span>Fastest Latest Workloads</span><span class="badge current">visual</span></div>
          <div class="phase-board">${bars}</div>
        </div>
        <div class="panel">
          <div class="panel-title"><span>Benchmark Coverage</span><span class="badge next">scope</span></div>
          <div class="scope-map">${scopeNodes}</div>
        </div>
      </div>`;
    }

    function renderMeasuredTable(rows) {
      const target = document.getElementById("measuredTableArea");
      if (!rows.length) {
        target.innerHTML = `<div class="empty">No benchmark rows were found. Run a smoke benchmark to populate this table.</div>`;
        return;
      }
      const byDb = [...new Set(rows.map(row => row.database))].sort().map(database => {
        const dbRows = rows.filter(row => row.database === database);
        const areas = [...new Set(dbRows.map(row => row.workload_category))].sort();
        const successRows = dbRows.filter(row => Number(row.failures || 0) === 0);
        const fastest = successRows.slice().sort((a, b) => Number(a.median_ms || 0) - Number(b.median_ms || 0))[0];
        const bestP95 = successRows.slice().sort((a, b) => Number(a.p95_ms || 0) - Number(b.p95_ms || 0))[0];
        const llm = dbRows
          .filter(row => row.workload_name === "account_health_360_end_to_end" || row.workload_name === "account_risk_end_to_end")
          .slice()
          .sort((a, b) => String(b.run_started_at || "").localeCompare(String(a.run_started_at || "")))[0];
        const accuracy = dbRows
          .filter(row => row.workload_name === "account_health_360_answer_accuracy")
          .slice()
          .sort((a, b) => String(b.run_started_at || "").localeCompare(String(a.run_started_at || "")))[0];
        const writeback = dbRows
          .filter(row => row.workload_name === "account_health_360_recommendation_writeback")
          .slice()
          .sort((a, b) => String(b.run_started_at || "").localeCompare(String(a.run_started_at || "")))[0];
        const recall = Math.max(...dbRows.map(row => Number(row.retrieval_recall_at_10 || 0)), 0);
        const storage = Math.max(...dbRows.map(row => Number(row.storage_mb || 0)), 0);
        const failures = dbRows.reduce((sum, row) => sum + Number(row.failures || 0), 0);
        const datasetRows = Math.max(...dbRows.map(row => Number(row.dataset_rows || 0)), 0);
        return { database, areas, fastest, bestP95, llm, accuracy, writeback, recall, storage, failures, datasetRows, rowCount: dbRows.length };
      });
      const table = byDb
        .map(row => {
          return `<tr>
            <td>${displayDatabaseName(row.database)}</td>
            <td>${databaseMode(row.database)}</td>
            <td>${row.areas.join(", ")}</td>
            <td>${row.fastest ? `${shortWorkloadName(row.fastest.workload_name)} · ${fmtMs(row.fastest.median_ms)}` : "pending"}</td>
            <td>${row.bestP95 ? fmtMs(row.bestP95.p95_ms) : "pending"}</td>
            <td>${row.llm ? fmtMs(row.llm.median_ms) : "not run"}</td>
            <td>${row.accuracy ? `${Number(row.accuracy.answer_precision_at_k || 0).toFixed(3)} / ${Number(row.accuracy.answer_recall_at_k || 0).toFixed(3)}` : "not run"}</td>
            <td>${row.writeback ? (row.writeback.write_verified ? "verified" : "failed") : "not run"}</td>
            <td>${row.recall ? row.recall.toFixed(3) : "not vector"}</td>
            <td>${fmtNumber(row.datasetRows)}</td>
            <td>${row.storage.toFixed(3)} MB</td>
            <td>${row.failures}</td>
          </tr>`;
        }).join("");
      target.innerHTML = `<div class="panel table-wrap">
        <div class="panel-title"><span>Database Performance Summary</span><span class="badge current">${byDb.length} databases</span></div>
        <table>
          <thead><tr><th>Database</th><th>Mode</th><th>Measured Areas</th><th>Fastest Workload</th><th>Best P95</th><th>LLM E2E</th><th>AI Precision/Recall</th><th>Write-Back</th><th>Recall@10</th><th>Rows</th><th>Storage</th><th>Failures</th></tr></thead>
          <tbody>${table}</tbody>
        </table>
      </div>`;
    }

    function stageBadge(stage) {
      const cls = stage.includes("current") ? "current" : stage.includes("optional") ? "optional" : "next";
      return `<span class="badge ${cls}">${stage}</span>`;
    }

    renderHero(RESULTS);
    renderKpis(RESULTS);
    renderInsights(RESULTS);
    renderDatabaseCards(RESULTS);
    renderPerformanceMap(RESULTS);
    renderMeasuredTable(RESULTS);
  </script>
</body>
</html>
"""
