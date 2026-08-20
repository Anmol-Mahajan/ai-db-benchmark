from __future__ import annotations

import json
from pathlib import Path

from ai_db_benchmark.benchmark.results import load_results_jsonl
from ai_db_benchmark.config import project_path


def generate_dashboard(results_path: Path, output_path: Path) -> Path:
    rows = load_results_jsonl(results_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = (
        DASHBOARD_TEMPLATE.replace("__RESULTS_JSON__", _script_safe_json(rows))
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
      background: linear-gradient(90deg, transparent 0 8%, rgba(8, 127, 122, 0.12) 8% 8.2%, transparent 8.2% 100%);
      pointer-events: none;
    }

    .hero {
      position: relative;
      min-height: 0;
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(390px, 0.95fr);
      gap: 32px;
      align-items: center;
      padding: 34px 0 28px;
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
      font-family: Avenir Next, Inter, ui-sans-serif, system-ui, sans-serif;
      font-size: clamp(1.6rem, 2.6vw, 2.15rem);
      line-height: 1.25;
      font-weight: 800;
      max-width: 620px;
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
      box-shadow: 0 10px 26px rgba(23, 23, 23, 0.06);
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
    .panel {
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

    .bar-value {
      font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
      font-weight: 800;
      text-align: right;
      font-size: 0.88rem;
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
      .hero { grid-template-columns: 1fr; min-height: 0; padding-top: 34px; }
      .section-head { align-items: start; flex-direction: column; }
      .kpis { grid-template-columns: 1fr 1fr; }
      .bar-row { grid-template-columns: 1fr; gap: 5px; }
      .bar-value { text-align: left; }
      .board-row { grid-template-columns: 1fr; gap: 6px; }
      .board-note { text-align: left; }
      .status { white-space: normal; }
      table { font-size: 0.84rem; }
      th, td { padding: 9px 8px; }
    }

    @media (max-width: 560px) {
      .kpis { grid-template-columns: 1fr; }
      h1 { font-size: 1.5rem; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <div>
        <div class="eyebrow">Local benchmark on Apple Silicon</div>
        <h1>A local test of scaling a database and LLM stack toward production.</h1>
        <p class="subtle hero-copy">Personal, local-only measurements of database execution, vector retrieval, Ollama response latency, answer accuracy, and recommendation write-back over the same workload.</p>
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
            <h2>Local Latency Measurements</h2>
            <p class="subtle">Median latency recorded locally for the same workload on each database, showing how the stack behaves as data scale grows.</p>
          </div>
        </div>
        <div id="chartArea"></div>
      </div>
    </section>

    <section>
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Measurement Summary</h2>
            <p class="subtle">One table summarising what was measured for each database in this local test.</p>
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
      const maxDatasetRows = Math.max(...rows.map(row => Number(row.dataset_rows || 0)), 0);
      const dbCount = new Set(rows.map(row => row.database)).size;
      const vectorRows = latestVectorRows(rows);
      const vectorDbCount = new Set(vectorRows.map(row => row.database)).size;
      const accuracyRows = latestAgentRows(rows).filter(row => row.workload_name === "account_health_360_answer_accuracy");
      const avgPrecision = accuracyRows.length
        ? accuracyRows.reduce((sum, row) => sum + Number(row.answer_precision_at_k || 0), 0) / accuracyRows.length
        : 0;
      const model = latestAgentRows(rows).map(row => parseNotes(row).llm_model).find(Boolean) || "not recorded";
      document.getElementById("heroBoard").innerHTML = [
        ["Dataset scale", maxDatasetRows ? `${fmtNumber(maxDatasetRows)} rows` : "pending", "synthetic enterprise dataset"],
        ["Databases tested", dbCount, "structured, vector, and LLM workflows"],
        ["Vector databases tested", vectorDbCount, "local ingest and search"],
        ["Local model", model, "Ollama"],
        ["Answer accuracy (avg)", accuracyRows.length ? avgPrecision.toFixed(3) : "pending", "precision@k across tested databases"],
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

    function barChart(title, badge, entries) {
      if (!entries.length) return "";
      const maxValue = Math.max(...entries.map(entry => entry.value), 0.001);
      const bars = entries.map(entry => {
        const width = Math.max(2, (entry.value / maxValue) * 100);
        return `<div class="bar-row">
          <div class="bar-label">${entry.label}</div>
          <div class="bar-track"><div class="bar-fill" style="--width:${width}%; --fill:${entry.color}"></div></div>
          <div class="bar-value">${entry.display}</div>
        </div>`;
      }).join("");
      return `<div class="panel">
        <div class="panel-title"><span>${title}</span><span class="badge ${badge}">${entries.length} databases</span></div>
        <div class="chart">${bars}</div>
      </div>`;
    }

    function renderComparisonCharts(rows) {
      const target = document.getElementById("chartArea");
      const structuredRows = rows.filter(row => row.workload_name === "complex_account_health_360");
      const maxStructuredRows = Math.max(...structuredRows.map(row => Number(row.dataset_rows || 0)), 0);
      const structuredEntries = latestRows(structuredRows.filter(row => Number(row.dataset_rows || 0) === maxStructuredRows))
        .slice()
        .sort((a, b) => Number(a.median_ms || 0) - Number(b.median_ms || 0))
        .map(row => ({ label: displayDatabaseName(row.database), value: Number(row.median_ms || 0), display: fmtMs(row.median_ms), color: databaseColor(row.database) }));
      const llmEntries = latestAgentRows(rows)
        .filter(row => row.workload_name === "account_health_360_end_to_end" || row.workload_name === "account_risk_end_to_end")
        .slice()
        .sort((a, b) => Number(a.median_ms || 0) - Number(b.median_ms || 0))
        .map(row => ({ label: displayDatabaseName(row.database), value: Number(row.median_ms || 0), display: fmtMs(row.median_ms), color: databaseColor(row.database) }));
      const recallByDb = new Map();
      for (const row of rows.filter(row => row.workload_category === "vector")) {
        const current = recallByDb.get(row.database) || 0;
        recallByDb.set(row.database, Math.max(current, Number(row.retrieval_recall_at_10 || 0)));
      }
      const recallEntries = [...recallByDb.entries()]
        .sort((a, b) => b[1] - a[1])
        .map(([database, recall]) => ({ label: displayDatabaseName(database), value: recall, display: recall.toFixed(3), color: databaseColor(database) }));
      const ingestEntries = latestVectorRows(rows)
        .filter(row => row.workload_name === "vector_ingest")
        .slice()
        .sort((a, b) => Number(a.median_ms || 0) - Number(b.median_ms || 0))
        .map(row => ({ label: displayDatabaseName(row.database), value: Number(row.median_ms || 0), display: fmtMs(row.median_ms), color: databaseColor(row.database) }));
      const searchEntries = latestVectorRows(rows)
        .filter(row => row.workload_name === "vector_search_top_k")
        .slice()
        .sort((a, b) => Number(a.median_ms || 0) - Number(b.median_ms || 0))
        .map(row => ({ label: displayDatabaseName(row.database), value: Number(row.median_ms || 0), display: fmtMs(row.median_ms), color: databaseColor(row.database) }));
      const embeddingModel = latestVectorRows(rows).map(row => row.embedding_model).find(Boolean) || "not recorded";
      const charts = [
        barChart("Structured Query Latency (complex account-health, 1M rows)", "current", structuredEntries),
        barChart("LLM End-to-End Latency (context + generation + write-back)", "llm", llmEntries),
        barChart(`Vector Ingest Latency (${embeddingModel})`, "next", ingestEntries),
        barChart(`Vector Top-K Search Latency (${embeddingModel})`, "next", searchEntries),
        barChart("Vector Search Recall@10", "current", recallEntries),
      ].filter(Boolean).join("");
      target.innerHTML = charts || `<div class="empty">No measured result rows yet.</div>`;
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
          <thead><tr><th>Database</th><th>Mode</th><th>Measured Areas</th><th>Lowest-Latency Workload</th><th>Lowest P95</th><th>LLM E2E</th><th>AI Precision/Recall</th><th>Write-Back</th><th>Recall@10</th><th>Rows</th><th>Storage</th><th>Failures</th></tr></thead>
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
    renderComparisonCharts(RESULTS);
    renderMeasuredTable(RESULTS);
  </script>
</body>
</html>
"""
