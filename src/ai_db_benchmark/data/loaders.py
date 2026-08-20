from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ai_db_benchmark.data.schemas import DatasetBundle


def save_dataset(dataset: DatasetBundle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "name": dataset.name,
        "seed": dataset.seed,
        "tables": dataset.tables(),
        "table_counts": dataset.table_counts(),
        "dataset_hash": dataset.stable_hash(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def load_dataset(path: Path) -> DatasetBundle:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tables = payload["tables"]
    return DatasetBundle(
        name=payload["name"],
        seed=int(payload["seed"]),
        salespeople=list(tables["salespeople"]),
        customers=list(tables["customers"]),
        contracts=list(tables["contracts"]),
        invoices=list(tables["invoices"]),
        opportunities=list(tables["opportunities"]),
        support_tickets=list(tables["support_tickets"]),
        customer_notes=list(tables["customer_notes"]),
        call_transcripts=list(tables["call_transcripts"]),
    )
