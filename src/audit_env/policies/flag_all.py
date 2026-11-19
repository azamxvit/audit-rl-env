"""Attack "flag everything": reads one page of invoices/payments/ledger and submits the max of 30
findings covering every type for every id seen, each stuffed with 10 evidence ids."""
from __future__ import annotations

from .base import Policy, TableReader, finding, submit_action

TYPES = ["duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"]


class FlagAllPolicy(Policy):
    name = "flag_all"

    def reset(self, observation: dict) -> None:
        self.episode_id = observation["manifest"]["episode_id"]
        self.base = observation["manifest"]["base_currency"]
        self.reader = TableReader()
        self.plan = ["invoices", "payments", "ledger"]

    def act(self, observation: dict) -> dict:
        self.reader.absorb(observation)
        if self.plan:
            return self.reader.request(self.plan.pop(0))
        inv = self.reader.data.get("invoices", [])
        pay = self.reader.data.get("payments", [])
        rows = self.reader.data.get("ledger", [])
        evidence_pool = [r["row_id"] for r in rows]
        findings = []
        targets = [(i["invoice_id"], i["doc_id"], i["total_minor"]) for i in inv] + \
                  [(p["payment_id"], p["doc_id"], p["amount_minor"]) for p in pay]
        k = 0
        while len(findings) < 30 and targets:
            bid, doc, amount = targets[k % len(targets)]
            t = TYPES[k % len(TYPES)]
            ev = [doc] + evidence_pool[(k * 9) % max(1, len(evidence_pool)):][:9]
            findings.append(finding(t, [bid], amount, self.base, ev, "flag everything"))
            k += 1
        return submit_action(self.episode_id, findings)
