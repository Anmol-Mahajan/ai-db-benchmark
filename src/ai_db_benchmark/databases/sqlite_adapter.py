from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from ai_db_benchmark.data.schemas import DatasetBundle


class SQLiteAdapter:
    name = "sqlite"

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLiteAdapter is not connected")
        return self._conn

    def reset(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def seed(self, dataset: DatasetBundle) -> None:
        self._insert_many("salespeople", dataset.salespeople)
        self._insert_many("customers", dataset.customers)
        self._insert_many("contracts", dataset.contracts)
        self._insert_many("invoices", dataset.invoices)
        self._insert_many("opportunities", dataset.opportunities)
        self._insert_many("support_tickets", dataset.support_tickets)
        self._insert_many("customer_notes", dataset.customer_notes)
        self._insert_many("call_transcripts", dataset.call_transcripts)
        self.conn.commit()

    def healthcheck(self) -> bool:
        return self.conn.execute("SELECT 1").fetchone()[0] == 1

    def database_version(self) -> str:
        return str(self.conn.execute("SELECT sqlite_version()").fetchone()[0])

    def storage_bytes(self) -> int:
        total = 0
        for suffix in ("", "-wal", "-shm"):
            path = Path(str(self.db_path) + suffix)
            if path.exists():
                total += path.stat().st_size
        return total

    def row_counts(self) -> Dict[str, int]:
        return {table: int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in TABLES}

    def insert_customers(self, rows: Sequence[Mapping[str, object]]) -> int:
        self._insert_many("customers", rows)
        self.conn.commit()
        return len(rows)

    def point_read_customer(self, customer_id: int) -> Optional[Mapping[str, object]]:
        row = self.conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        return dict(row) if row else None

    def filtered_customers_by_region(self, region: str, limit: int) -> List[Mapping[str, object]]:
        rows = self.conn.execute(
            "SELECT * FROM customers WHERE region = ? ORDER BY customer_id LIMIT ?",
            (region, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def update_customer_health(self, customer_id: int, delta: int) -> int:
        cur = self.conn.execute(
            """
            UPDATE customers
            SET customer_health_score = max(1, min(100, customer_health_score + ?))
            WHERE customer_id = ?
            """,
            (delta, customer_id),
        )
        self.conn.commit()
        return int(cur.rowcount)

    def renewal_risk_join(self, limit: int) -> List[Mapping[str, object]]:
        rows = self.conn.execute(
            """
            SELECT
              c.customer_id,
              c.customer_name,
              c.region,
              c.current_mrr,
              c.previous_mrr,
              ct.end_date,
              COUNT(st.ticket_id) AS open_ticket_count,
              (c.previous_mrr - c.current_mrr) AS mrr_decline
            FROM customers c
            JOIN contracts ct ON ct.customer_id = c.customer_id
            LEFT JOIN support_tickets st ON st.customer_id = c.customer_id AND st.status = 'open'
            WHERE ct.status = 'active'
              AND ct.end_date BETWEEN '2026-01-01' AND '2026-04-01'
              AND c.current_mrr < c.previous_mrr
            GROUP BY c.customer_id, c.customer_name, c.region, c.current_mrr, c.previous_mrr, ct.end_date
            ORDER BY open_ticket_count DESC, mrr_decline DESC, c.customer_id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def complex_account_health(self, limit: int) -> List[Mapping[str, object]]:
        rows = self.conn.execute(
            COMPLEX_ACCOUNT_HEALTH_SQL,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def write_ai_recommendations(self, rows: Sequence[Mapping[str, object]]) -> int:
        self._insert_many("ai_recommendations", rows)
        self.conn.commit()
        return len(rows)

    def read_ai_recommendations(self, benchmark_run_id: str) -> List[Mapping[str, object]]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM ai_recommendations
            WHERE benchmark_run_id = ?
            ORDER BY recommendation_id
            """,
            (benchmark_run_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def revenue_by_region(self) -> List[Mapping[str, object]]:
        rows = self.conn.execute(
            """
            SELECT
              c.region,
              COUNT(DISTINCT c.customer_id) AS customer_count,
              SUM(i.amount) AS invoice_amount,
              AVG(c.customer_health_score) AS avg_health,
              SUM(i.gross_profit) AS gross_profit
            FROM customers c
            JOIN invoices i ON i.customer_id = c.customer_id
            GROUP BY c.region
            ORDER BY c.region
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def _insert_many(self, table: str, rows: Sequence[Mapping[str, object]]) -> None:
        if not rows:
            return
        columns = list(rows[0].keys())
        placeholders = ", ".join("?" for _ in columns)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        self.conn.executemany(sql, [[row.get(col) for col in columns] for row in rows])


TABLES = [
    "ai_recommendations",
    "call_transcripts",
    "customer_notes",
    "support_tickets",
    "opportunities",
    "invoices",
    "contracts",
    "customers",
    "salespeople",
]


SCHEMA_SQL = """
DROP TABLE IF EXISTS call_transcripts;
DROP TABLE IF EXISTS customer_notes;
DROP TABLE IF EXISTS support_tickets;
DROP TABLE IF EXISTS opportunities;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS contracts;
DROP TABLE IF EXISTS ai_recommendations;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS salespeople;

CREATE TABLE salespeople (
  salesperson_id INTEGER PRIMARY KEY,
  salesperson_name TEXT NOT NULL,
  team TEXT NOT NULL,
  territory TEXT NOT NULL,
  active BOOLEAN NOT NULL
);

CREATE TABLE customers (
  customer_id INTEGER PRIMARY KEY,
  customer_name TEXT NOT NULL,
  segment TEXT NOT NULL,
  industry TEXT NOT NULL,
  region TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL,
  current_mrr REAL NOT NULL,
  previous_mrr REAL NOT NULL,
  annual_revenue REAL NOT NULL,
  account_manager_id INTEGER NOT NULL,
  customer_health_score INTEGER NOT NULL
);

CREATE INDEX idx_customers_region ON customers(region);
CREATE INDEX idx_customers_account_manager ON customers(account_manager_id);

CREATE TABLE contracts (
  contract_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  service_family TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  original_end_date TEXT NOT NULL,
  contract_value REAL NOT NULL,
  recurring_revenue REAL NOT NULL,
  status TEXT NOT NULL,
  renewal_status TEXT NOT NULL,
  auto_renew BOOLEAN NOT NULL,
  salesperson_id INTEGER NOT NULL
);

CREATE INDEX idx_contracts_customer ON contracts(customer_id);
CREATE INDEX idx_contracts_end_date ON contracts(end_date);

CREATE TABLE invoices (
  invoice_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  invoice_date TEXT NOT NULL,
  amount REAL NOT NULL,
  gross_profit REAL NOT NULL,
  status TEXT NOT NULL
);

CREATE INDEX idx_invoices_customer ON invoices(customer_id);
CREATE INDEX idx_invoices_date ON invoices(invoice_date);

CREATE TABLE opportunities (
  opportunity_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  salesperson_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  closed_at TEXT,
  stage TEXT NOT NULL,
  value REAL NOT NULL,
  gross_profit REAL NOT NULL,
  service_family TEXT NOT NULL,
  won BOOLEAN NOT NULL
);

CREATE TABLE support_tickets (
  ticket_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  category TEXT NOT NULL,
  resolution_time_minutes INTEGER,
  sentiment TEXT NOT NULL
);

CREATE INDEX idx_tickets_customer_status ON support_tickets(customer_id, status);

CREATE TABLE customer_notes (
  note_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  author_id INTEGER NOT NULL,
  note_type TEXT NOT NULL,
  note_text TEXT NOT NULL
);

CREATE TABLE call_transcripts (
  transcript_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  salesperson_id INTEGER NOT NULL,
  call_date TEXT NOT NULL,
  duration_seconds INTEGER NOT NULL,
  transcript_text TEXT NOT NULL
);

CREATE TABLE ai_recommendations (
  recommendation_id TEXT PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  benchmark_run_id TEXT NOT NULL,
  model_name TEXT NOT NULL,
  architecture TEXT NOT NULL,
  recommendation_type TEXT NOT NULL,
  risk_score REAL NOT NULL,
  reason TEXT NOT NULL,
  recommended_action TEXT NOT NULL,
  source_record_ids TEXT NOT NULL,
  retrieval_latency_ms REAL NOT NULL,
  reasoning_latency_ms REAL NOT NULL,
  write_latency_ms REAL NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_ai_recommendations_run ON ai_recommendations(benchmark_run_id);
"""


COMPLEX_ACCOUNT_HEALTH_SQL = """
WITH contract_summary AS (
  SELECT
    customer_id,
    COUNT(*) AS contract_count,
    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_contract_count,
    MIN(CASE WHEN status = 'active' THEN end_date ELSE NULL END) AS nearest_contract_end_date,
    SUM(CASE WHEN status = 'active' THEN recurring_revenue ELSE 0 END) AS active_recurring_revenue,
    SUM(CASE WHEN status = 'active' AND renewal_status = 'risk' THEN 1 ELSE 0 END) AS risky_contract_count
  FROM contracts
  GROUP BY customer_id
),
invoice_summary AS (
  SELECT
    customer_id,
    COUNT(*) AS invoice_count,
    SUM(amount) AS total_invoice_amount,
    SUM(gross_profit) AS gross_profit,
    SUM(CASE WHEN status IN ('open', 'overdue') THEN amount ELSE 0 END) AS open_invoice_amount,
    SUM(CASE WHEN status = 'overdue' THEN amount ELSE 0 END) AS overdue_invoice_amount
  FROM invoices
  GROUP BY customer_id
),
ticket_summary AS (
  SELECT
    customer_id,
    COUNT(*) AS ticket_count,
    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_ticket_count,
    SUM(CASE WHEN priority IN ('high', 'urgent') AND status = 'open' THEN 1 ELSE 0 END) AS urgent_open_ticket_count,
    SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS negative_ticket_count
  FROM support_tickets
  GROUP BY customer_id
),
opportunity_summary AS (
  SELECT
    customer_id,
    COUNT(*) AS opportunity_count,
    SUM(CASE WHEN won = 0 THEN value ELSE 0 END) AS open_pipeline_value,
    SUM(CASE WHEN won = 0 THEN gross_profit ELSE 0 END) AS open_pipeline_gross_profit
  FROM opportunities
  GROUP BY customer_id
),
note_summary AS (
  SELECT
    customer_id,
    COUNT(*) AS note_count,
    SUM(CASE
      WHEN LOWER(note_text) LIKE '%budget%'
        OR LOWER(note_text) LIKE '%sponsor%'
        OR LOWER(note_text) LIKE '%renewal%'
      THEN 1 ELSE 0 END
    ) AS commercial_signal_count
  FROM customer_notes
  GROUP BY customer_id
),
call_summary AS (
  SELECT
    customer_id,
    COUNT(*) AS call_count,
    MAX(call_date) AS last_call_date,
    SUM(duration_seconds) AS total_call_seconds
  FROM call_transcripts
  GROUP BY customer_id
)
SELECT
  c.customer_id,
  c.customer_name,
  c.segment,
  c.industry,
  c.region,
  sp.salesperson_name AS account_manager,
  c.status,
  c.current_mrr,
  c.previous_mrr,
  (c.previous_mrr - c.current_mrr) AS mrr_decline,
  c.customer_health_score,
  COALESCE(cs.contract_count, 0) AS contract_count,
  COALESCE(cs.active_contract_count, 0) AS active_contract_count,
  cs.nearest_contract_end_date,
  COALESCE(cs.active_recurring_revenue, 0) AS active_recurring_revenue,
  COALESCE(cs.risky_contract_count, 0) AS risky_contract_count,
  COALESCE(inv.total_invoice_amount, 0) AS total_invoice_amount,
  COALESCE(inv.gross_profit, 0) AS gross_profit,
  COALESCE(inv.open_invoice_amount, 0) AS open_invoice_amount,
  COALESCE(inv.overdue_invoice_amount, 0) AS overdue_invoice_amount,
  COALESCE(ts.open_ticket_count, 0) AS open_ticket_count,
  COALESCE(ts.urgent_open_ticket_count, 0) AS urgent_open_ticket_count,
  COALESCE(ts.negative_ticket_count, 0) AS negative_ticket_count,
  COALESCE(opp.open_pipeline_value, 0) AS open_pipeline_value,
  COALESCE(opp.open_pipeline_gross_profit, 0) AS open_pipeline_gross_profit,
  COALESCE(ns.commercial_signal_count, 0) AS commercial_signal_count,
  COALESCE(call.call_count, 0) AS call_count,
  call.last_call_date,
  (
    CASE WHEN c.current_mrr < c.previous_mrr THEN 25 ELSE 0 END
    + CASE WHEN c.customer_health_score < 45 THEN 20 ELSE 0 END
    + COALESCE(ts.open_ticket_count, 0) * 4
    + COALESCE(ts.urgent_open_ticket_count, 0) * 8
    + COALESCE(cs.risky_contract_count, 0) * 10
    + CASE WHEN COALESCE(inv.overdue_invoice_amount, 0) > 0 THEN 10 ELSE 0 END
    + COALESCE(ns.commercial_signal_count, 0) * 3
  ) AS risk_score
FROM customers c
JOIN salespeople sp ON sp.salesperson_id = c.account_manager_id
LEFT JOIN contract_summary cs ON cs.customer_id = c.customer_id
LEFT JOIN invoice_summary inv ON inv.customer_id = c.customer_id
LEFT JOIN ticket_summary ts ON ts.customer_id = c.customer_id
LEFT JOIN opportunity_summary opp ON opp.customer_id = c.customer_id
LEFT JOIN note_summary ns ON ns.customer_id = c.customer_id
LEFT JOIN call_summary call ON call.customer_id = c.customer_id
WHERE c.status IN ('active', 'at_risk')
  AND (
    c.current_mrr < c.previous_mrr
    OR COALESCE(ts.open_ticket_count, 0) > 0
    OR COALESCE(cs.risky_contract_count, 0) > 0
    OR COALESCE(inv.overdue_invoice_amount, 0) > 0
  )
ORDER BY risk_score DESC, mrr_decline DESC, open_pipeline_value DESC, c.customer_id
LIMIT ?
"""
