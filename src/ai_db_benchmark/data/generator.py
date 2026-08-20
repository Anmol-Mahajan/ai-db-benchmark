from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Dict, List

from ai_db_benchmark.data.schemas import DatasetBundle


SEGMENTS = ["enterprise", "mid_market", "smb"]
INDUSTRIES = ["software", "finance", "healthcare", "manufacturing", "retail", "logistics"]
REGIONS = ["na", "emea", "apac", "latam"]
STATUSES = ["active", "at_risk", "paused"]
SERVICE_FAMILIES = ["analytics", "workflow", "security", "data_platform", "support"]
TEAMS = ["growth", "enterprise", "retention"]


def _iso(day: date) -> str:
    return day.isoformat()


def _money(rng: random.Random, low: int, high: int) -> float:
    return float(rng.randrange(low, high, 50))


def generate_enterprise_dataset(customer_count: int, seed: int = 42, name: str = "synthetic-enterprise") -> DatasetBundle:
    if customer_count < 1:
        raise ValueError("customer_count must be >= 1")

    rng = random.Random(seed)
    base_day = date(2026, 1, 1)
    salesperson_count = max(5, min(250, customer_count // 80))

    salespeople: List[Dict[str, object]] = []
    for salesperson_id in range(1, salesperson_count + 1):
        salespeople.append(
            {
                "salesperson_id": salesperson_id,
                "salesperson_name": f"Salesperson {salesperson_id:03d}",
                "team": TEAMS[salesperson_id % len(TEAMS)],
                "territory": REGIONS[salesperson_id % len(REGIONS)],
                "active": salesperson_id % 17 != 0,
            }
        )

    customers: List[Dict[str, object]] = []
    contracts: List[Dict[str, object]] = []
    invoices: List[Dict[str, object]] = []
    opportunities: List[Dict[str, object]] = []
    support_tickets: List[Dict[str, object]] = []
    customer_notes: List[Dict[str, object]] = []
    call_transcripts: List[Dict[str, object]] = []

    contract_id = 1
    invoice_id = 1
    opportunity_id = 1
    ticket_id = 1
    note_id = 1
    transcript_id = 1

    for customer_id in range(1, customer_count + 1):
        segment = rng.choice(SEGMENTS)
        industry = rng.choice(INDUSTRIES)
        region = rng.choice(REGIONS)
        salesperson_id = rng.randint(1, salesperson_count)
        previous_mrr = _money(rng, 500, 50000)
        current_mrr = max(0.0, previous_mrr + _money(rng, -5000, 7500))
        created_at = base_day - timedelta(days=rng.randint(60, 2200))
        health = max(1, min(100, int(rng.gauss(72, 18))))

        customers.append(
            {
                "customer_id": customer_id,
                "customer_name": f"Customer {customer_id:05d}",
                "segment": segment,
                "industry": industry,
                "region": region,
                "created_at": _iso(created_at),
                "status": "at_risk" if health < 45 else rng.choice(STATUSES),
                "current_mrr": current_mrr,
                "previous_mrr": previous_mrr,
                "annual_revenue": current_mrr * 12,
                "account_manager_id": salesperson_id,
                "customer_health_score": health,
            }
        )

        for _ in range(1 + (customer_id % 3 == 0)):
            start = base_day - timedelta(days=rng.randint(30, 730))
            end = base_day + timedelta(days=rng.randint(-60, 365))
            recurring = max(100.0, current_mrr * rng.uniform(0.35, 1.2))
            contracts.append(
                {
                    "contract_id": contract_id,
                    "customer_id": customer_id,
                    "service_family": rng.choice(SERVICE_FAMILIES),
                    "start_date": _iso(start),
                    "end_date": _iso(end),
                    "original_end_date": _iso(end - timedelta(days=rng.choice([0, 0, 30, 60]))),
                    "contract_value": recurring * 12,
                    "recurring_revenue": recurring,
                    "status": "active" if end >= base_day else "expired",
                    "renewal_status": rng.choice(["pending", "likely", "risk", "renewed"]),
                    "auto_renew": rng.random() < 0.35,
                    "salesperson_id": salesperson_id,
                }
            )
            contract_id += 1

        for month in range(3):
            amount = max(50.0, current_mrr * rng.uniform(0.7, 1.2))
            invoices.append(
                {
                    "invoice_id": invoice_id,
                    "customer_id": customer_id,
                    "invoice_date": _iso(base_day - timedelta(days=30 * month + rng.randint(0, 10))),
                    "amount": amount,
                    "gross_profit": amount * rng.uniform(0.45, 0.82),
                    "status": rng.choice(["paid", "paid", "paid", "open", "overdue"]),
                }
            )
            invoice_id += 1

        if rng.random() < 0.45:
            won = rng.random() < 0.38
            opportunities.append(
                {
                    "opportunity_id": opportunity_id,
                    "customer_id": customer_id,
                    "salesperson_id": salesperson_id,
                    "created_at": _iso(base_day - timedelta(days=rng.randint(1, 180))),
                    "closed_at": _iso(base_day - timedelta(days=rng.randint(0, 90))) if won else None,
                    "stage": "closed_won" if won else rng.choice(["discovery", "proposal", "negotiation"]),
                    "value": _money(rng, 1000, 120000),
                    "gross_profit": _money(rng, 500, 70000),
                    "service_family": rng.choice(SERVICE_FAMILIES),
                    "won": won,
                }
            )
            opportunity_id += 1

        for _ in range(rng.randint(0, 2)):
            opened = base_day - timedelta(days=rng.randint(1, 180))
            closed = None if rng.random() < 0.28 else opened + timedelta(days=rng.randint(1, 20))
            support_tickets.append(
                {
                    "ticket_id": ticket_id,
                    "customer_id": customer_id,
                    "opened_at": _iso(opened),
                    "closed_at": _iso(closed) if closed else None,
                    "priority": rng.choice(["low", "medium", "high", "urgent"]),
                    "status": "open" if closed is None else "closed",
                    "category": rng.choice(["billing", "reliability", "onboarding", "feature_request"]),
                    "resolution_time_minutes": None if closed is None else rng.randint(30, 24000),
                    "sentiment": rng.choice(["positive", "neutral", "negative"]),
                }
            )
            ticket_id += 1

        note_theme = rng.choice(["expansion interest", "budget concern", "executive sponsor change", "smooth renewal"])
        customer_notes.append(
            {
                "note_id": note_id,
                "customer_id": customer_id,
                "created_at": _iso(base_day - timedelta(days=rng.randint(0, 120))),
                "author_id": salesperson_id,
                "note_type": rng.choice(["qbr", "support", "renewal", "commercial"]),
                "note_text": f"{note_theme} discussed for customer {customer_id:05d}.",
            }
        )
        note_id += 1

        if rng.random() < 0.5:
            call_transcripts.append(
                {
                    "transcript_id": transcript_id,
                    "customer_id": customer_id,
                    "salesperson_id": salesperson_id,
                    "call_date": _iso(base_day - timedelta(days=rng.randint(0, 90))),
                    "duration_seconds": rng.randint(300, 3600),
                    "transcript_text": f"Call covered {rng.choice(SERVICE_FAMILIES)} usage, renewal timing, and next actions.",
                }
            )
            transcript_id += 1

    return DatasetBundle(
        name=name,
        seed=seed,
        customers=customers,
        salespeople=salespeople,
        contracts=contracts,
        invoices=invoices,
        opportunities=opportunities,
        support_tickets=support_tickets,
        customer_notes=customer_notes,
        call_transcripts=call_transcripts,
    )
