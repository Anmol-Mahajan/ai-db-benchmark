from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence


class PostgreSQLAdapter:
    name = "postgres"
    db_path = Path("postgres://localhost:5432/benchmark")

    def __init__(self, dsn: str = "postgresql://benchmark:benchmark@localhost:5432/benchmark") -> None:
        self.dsn = dsn
        self._conn = None

    def connect(self) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL benchmark requires psycopg; install with .[vector]") from exc
        self._conn = psycopg.connect(self.dsn)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def conn(self):  # type: ignore[no-untyped-def]
        if self._conn is None:
            raise RuntimeError("PostgreSQLAdapter is not connected")
        return self._conn

    def reset(self) -> None:
        with self.conn.cursor() as cur:
            for statement in SCHEMA_SQL.split(";"):
                if statement.strip():
                    cur.execute(statement)
        self.conn.commit()

    def seed(self, dataset) -> None:  # type: ignore[no-untyped-def]
        for table, rows in dataset.tables().items():
            self._insert_many(table, rows)
        self.conn.commit()

    def healthcheck(self) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
        return bool(row and row[0] == 1)

    def database_version(self) -> str:
        with self.conn.cursor() as cur:
            cur.execute("SELECT version()")
            row = cur.fetchone()
        return str(row[0]).split(",")[0] if row else "postgres unknown"

    def storage_bytes(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database())")
            row = cur.fetchone()
        return int(row[0]) if row else 0

    def row_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        with self.conn.cursor() as cur:
            for table in TABLES:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row = cur.fetchone()
                counts[table] = int(row[0]) if row else 0
        return counts

    def insert_customers(self, rows: Sequence[Mapping[str, object]]) -> int:
        self._insert_many("customers", rows)
        self.conn.commit()
        return len(rows)

    def point_read_customer(self, customer_id: int) -> Optional[Mapping[str, object]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM customers WHERE customer_id = %s", [customer_id])
            row = cur.fetchone()
            return _row_to_dict(cur, row) if row else None

    def filtered_customers_by_region(self, region: str, limit: int) -> List[Mapping[str, object]]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM customers WHERE region = %s ORDER BY customer_id LIMIT %s",
                [region, limit],
            )
            return [_row_to_dict(cur, row) for row in cur.fetchall()]

    def update_customer_health(self, customer_id: int, delta: int) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE customers
                SET customer_health_score = GREATEST(1, LEAST(100, customer_health_score + %s))
                WHERE customer_id = %s
                """,
                [delta, customer_id],
            )
            row_count = cur.rowcount
        self.conn.commit()
        return int(row_count)

    def renewal_risk_join(self, limit: int) -> List[Mapping[str, object]]:
        with self.conn.cursor() as cur:
            cur.execute(
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
                  AND ct.end_date BETWEEN DATE '2026-01-01' AND DATE '2026-04-01'
                  AND c.current_mrr < c.previous_mrr
                GROUP BY c.customer_id, c.customer_name, c.region, c.current_mrr, c.previous_mrr, ct.end_date
                ORDER BY open_ticket_count DESC, mrr_decline DESC, c.customer_id
                LIMIT %s
                """,
                [limit],
            )
            return [_row_to_dict(cur, row) for row in cur.fetchall()]

    def complex_account_health(self, limit: int) -> List[Mapping[str, object]]:
        with self.conn.cursor() as cur:
            cur.execute(COMPLEX_ACCOUNT_HEALTH_SQL, [limit])
            return [_row_to_dict(cur, row) for row in cur.fetchall()]

    def write_ai_recommendations(self, rows: Sequence[Mapping[str, object]]) -> int:
        self._insert_many("ai_recommendations", rows)
        self.conn.commit()
        return len(rows)

    def read_ai_recommendations(self, benchmark_run_id: str) -> List[Mapping[str, object]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM ai_recommendations
                WHERE benchmark_run_id = %s
                ORDER BY recommendation_id
                """,
                [benchmark_run_id],
            )
            return [_row_to_dict(cur, row) for row in cur.fetchall()]

    def revenue_by_region(self) -> List[Mapping[str, object]]:
        with self.conn.cursor() as cur:
            cur.execute(
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
            )
            return [_row_to_dict(cur, row) for row in cur.fetchall()]

    def _insert_many(self, table: str, rows: Sequence[Mapping[str, object]]) -> None:
        if not rows:
            return
        columns = list(rows[0].keys())
        if len(rows) >= 1000:
            self._copy_many(table, columns, rows)
            return
        placeholders = ", ".join("%s" for _ in columns)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        values = [[row.get(column) for column in columns] for row in rows]
        with self.conn.cursor() as cur:
            cur.executemany(sql, values)

    def _copy_many(self, table: str, columns: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
        column_sql = ", ".join(columns)
        with self.conn.cursor() as cur:
            with cur.copy(f"COPY {table} ({column_sql}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row([row.get(column) for column in columns])


def _row_to_dict(cursor, row) -> Mapping[str, object]:  # type: ignore[no-untyped-def]
    columns = [description.name for description in cursor.description]
    return dict(zip(columns, row))


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
DROP TABLE IF EXISTS ai_recommendations;
DROP TABLE IF EXISTS call_transcripts;
DROP TABLE IF EXISTS customer_notes;
DROP TABLE IF EXISTS support_tickets;
DROP TABLE IF EXISTS opportunities;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS contracts;
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
  created_at DATE NOT NULL,
  status TEXT NOT NULL,
  current_mrr DOUBLE PRECISION NOT NULL,
  previous_mrr DOUBLE PRECISION NOT NULL,
  annual_revenue DOUBLE PRECISION NOT NULL,
  account_manager_id INTEGER NOT NULL,
  customer_health_score INTEGER NOT NULL
);

CREATE INDEX idx_customers_region ON customers(region);
CREATE INDEX idx_customers_account_manager ON customers(account_manager_id);

CREATE TABLE contracts (
  contract_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  service_family TEXT NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  original_end_date DATE NOT NULL,
  contract_value DOUBLE PRECISION NOT NULL,
  recurring_revenue DOUBLE PRECISION NOT NULL,
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
  invoice_date DATE NOT NULL,
  amount DOUBLE PRECISION NOT NULL,
  gross_profit DOUBLE PRECISION NOT NULL,
  status TEXT NOT NULL
);

CREATE INDEX idx_invoices_customer ON invoices(customer_id);
CREATE INDEX idx_invoices_date ON invoices(invoice_date);

CREATE TABLE opportunities (
  opportunity_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  salesperson_id INTEGER NOT NULL,
  created_at DATE NOT NULL,
  closed_at DATE,
  stage TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  gross_profit DOUBLE PRECISION NOT NULL,
  service_family TEXT NOT NULL,
  won BOOLEAN NOT NULL
);

CREATE TABLE support_tickets (
  ticket_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  opened_at DATE NOT NULL,
  closed_at DATE,
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
  created_at DATE NOT NULL,
  author_id INTEGER NOT NULL,
  note_type TEXT NOT NULL,
  note_text TEXT NOT NULL
);

CREATE TABLE call_transcripts (
  transcript_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  salesperson_id INTEGER NOT NULL,
  call_date DATE NOT NULL,
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
  risk_score DOUBLE PRECISION NOT NULL,
  reason TEXT NOT NULL,
  recommended_action TEXT NOT NULL,
  source_record_ids TEXT NOT NULL,
  retrieval_latency_ms DOUBLE PRECISION NOT NULL,
  reasoning_latency_ms DOUBLE PRECISION NOT NULL,
  write_latency_ms DOUBLE PRECISION NOT NULL,
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
    SUM(CASE WHEN won = false THEN value ELSE 0 END) AS open_pipeline_value,
    SUM(CASE WHEN won = false THEN gross_profit ELSE 0 END) AS open_pipeline_gross_profit
  FROM opportunities
  GROUP BY customer_id
),
note_summary AS (
  SELECT
    customer_id,
    COUNT(*) AS note_count,
    SUM(CASE
      WHEN LOWER(note_text) LIKE '%%budget%%'
        OR LOWER(note_text) LIKE '%%sponsor%%'
        OR LOWER(note_text) LIKE '%%renewal%%'
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
LIMIT %s
"""
