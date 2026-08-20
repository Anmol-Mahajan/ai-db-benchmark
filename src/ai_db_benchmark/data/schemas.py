from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence


TableRows = List[Dict[str, object]]


@dataclass(frozen=True)
class DatasetBundle:
    name: str
    seed: int
    customers: TableRows
    salespeople: TableRows
    contracts: TableRows
    invoices: TableRows
    opportunities: TableRows
    support_tickets: TableRows
    customer_notes: TableRows
    call_transcripts: TableRows

    def tables(self) -> Dict[str, TableRows]:
        return {
            "salespeople": self.salespeople,
            "customers": self.customers,
            "contracts": self.contracts,
            "invoices": self.invoices,
            "opportunities": self.opportunities,
            "support_tickets": self.support_tickets,
            "customer_notes": self.customer_notes,
            "call_transcripts": self.call_transcripts,
        }

    def table_counts(self) -> Dict[str, int]:
        return {name: len(rows) for name, rows in self.tables().items()}

    def total_rows(self) -> int:
        return sum(self.table_counts().values())

    def stable_hash(self) -> str:
        payload = {
            "name": self.name,
            "seed": self.seed,
            "tables": self.tables(),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def rows_equal(left: Sequence[Mapping[str, object]], right: Sequence[Mapping[str, object]]) -> bool:
    return json.dumps(list(left), sort_keys=True, default=str) == json.dumps(list(right), sort_keys=True, default=str)
