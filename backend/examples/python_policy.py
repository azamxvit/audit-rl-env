"""Minimal Python policy: page through payments, then submit the receipts parked in unapplied cash.

Run:  PYTHONPATH=src python3 scripts/run_policy.py --policy examples/python_policy.py:UnappliedCashPolicy --split dev

A policy is any class with reset(observation) and act(observation) -> action (a JSON-compatible dict).
It sees only what the tools return; submit ends the episode. Reading the ledger is left as an exercise.
"""


class UnappliedCashPolicy:
    def reset(self, observation):
        self.episode_id = observation["manifest"]["episode_id"]
        self.base = observation["manifest"]["base_currency"]
        self.payments, self.ledger = [], []
        self.pending = None  # (table, cursor) of the page requested last
        self.queue = ["payments", "ledger"]
        self.cursor = None

    def act(self, observation):
        if self.pending and observation.get("ok"):
            table = self.pending
            page = observation["result"]
            (self.payments if table == "payments" else self.ledger).extend(page["records"])
            self.cursor = page["next_cursor"]
            if self.cursor is None:
                self.queue.pop(0)
        if self.queue and observation.get("steps_remaining", 0) > 1:
            self.pending = self.queue[0]
            args = {"table": self.pending, "limit": 50}
            if self.cursor:
                args["cursor"] = self.cursor
            return {"tool": "list_records", "args": args}
        return {"tool": "submit", "args": {"episode_id": self.episode_id, "findings": self.findings()}}

    def findings(self):
        out = []
        unapplied = {r["payment_id"]: r for r in self.ledger if r["account"] == "2200" and r["credit_minor"] > 0}
        for p in self.payments:
            refs = p["invoice_refs"] or []
            row = unapplied.get(p["payment_id"])
            # fully referenced to one invoice, yet cash parked in 2200: payment_allocation
            if p["kind"] == "receipt" and row and len(refs) == 1 and refs[0]["amount_minor"] == p["amount_minor"]:
                out.append(
                    {
                        "type": "payment_allocation",
                        "affected_ids": [p["payment_id"], refs[0]["invoice_id"]],
                        "claimed_amount_minor": row["credit_minor"],
                        "currency": self.base,
                        "evidence_ids": [p["doc_id"], row["row_id"]],
                        "explanation": "fully referenced receipt left in unapplied cash",
                    }
                )
        return out[:30]
