"""Simple reconciliation baseline (scripted, no truth access).

Reads payments, invoices and the ledger page by page (stops reading the ledger if
the budget gets tight), then applies two textbook checks:

* receipt fully referenced to one invoice but cash parked in 2200 -> payment_allocation
* two booked invoices with identical entity/currency/total/line items -> duplicate_invoice

It deliberately does NOT re-convert FX or test period cut-off, so its recall is
bounded; that gap is what the environment is meant to train.
"""
from __future__ import annotations

import json
from datetime import datetime

from .base import Policy, TableReader, finding, submit_action


class SimpleReconcilerPolicy(Policy):
    name = "simple_reconciler"

    def reset(self, observation: dict) -> None:
        m = observation["manifest"]
        self.episode_id = m["episode_id"]
        self.base = m["base_currency"]
        self.max_steps = observation["max_steps"]
        self.reader = TableReader()
        self.order = ["payments", "invoices", "ledger"]
        self.steps = 0

    def act(self, observation: dict) -> dict:
        self.reader.absorb(observation)
        self.steps += 1
        if self.steps < self.max_steps - 2:
            for table in self.order:
                if table not in self.reader.complete:
                    return self.reader.request(table)
        return submit_action(self.episode_id, self._findings())

    def _findings(self) -> list:
        data = self.reader.data
        payments = data.get("payments", [])
        invoices = data.get("invoices", [])
        ledger = data.get("ledger", [])
        out = []
        by_pay: dict = {}
        booking: dict = {}
        for r in ledger:
            if r["payment_id"]:
                by_pay.setdefault(r["payment_id"], []).append(r)
            if r["account"] == "1100" and r["debit_minor"] > 0 and r["invoice_id"] and not r["payment_id"]:
                booking[r["invoice_id"]] = r
        for p in payments:
            refs = p["invoice_refs"] or []
            if p["kind"] != "receipt" or len(refs) != 1 or refs[0]["amount_minor"] != p["amount_minor"]:
                continue
            for r in by_pay.get(p["payment_id"], []):
                if r["account"] == "2200" and r["credit_minor"] > 0:
                    out.append(finding("payment_allocation", [p["payment_id"], refs[0]["invoice_id"]],
                                       r["credit_minor"], self.base, [p["doc_id"], r["row_id"]],
                                       "fully referenced receipt left in unapplied cash"))
        groups: dict = {}
        for inv in invoices:
            if inv["invoice_id"] not in booking:
                continue
            key = json.dumps([inv["entity_id"], inv["currency"], inv["total_minor"],
                              sorted(json.dumps(li, sort_keys=True) for li in inv["line_items"])])
            groups.setdefault(key, []).append(inv)
        for invs in groups.values():
            if len(invs) < 2:
                continue
            invs.sort(key=lambda i: datetime.fromisoformat(i["issued_at"]))
            a, b = invs[0], invs[1]
            ra, rb = booking[a["invoice_id"]], booking[b["invoice_id"]]
            out.append(finding("duplicate_invoice", [a["invoice_id"], b["invoice_id"]], rb["debit_minor"], self.base,
                               [a["doc_id"], b["doc_id"], ra["row_id"], rb["row_id"]], "identical invoice booked twice"))
        return out[:30]
