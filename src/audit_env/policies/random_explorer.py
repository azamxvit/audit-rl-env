"""Random explorer with a fixed seed: random tool calls, then a few random guesses built from what it saw."""
from __future__ import annotations

import random

from .base import Policy, finding, submit_action

TYPES = ["duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"]
TABLES = ["ledger", "invoices", "payments", "fx"]


class RandomExplorerPolicy(Policy):
    name = "random_explorer"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def reset(self, observation: dict) -> None:
        self.rng = random.Random(f"random-explorer|{self.seed}|{observation['manifest']['episode_id']}")
        self.episode_id = observation["manifest"]["episode_id"]
        self.base = observation["manifest"]["base_currency"]
        self.budget = self.rng.randint(5, 40)
        self.seen: list = []
        self.cursors: list = []
        self.steps = 0

    def _absorb(self, observation: dict) -> None:
        res = observation.get("result")
        if not observation.get("ok") or not isinstance(res, dict):
            return
        recs = res.get("records") or ([res["document"]] if "document" in res else [res] if "row_id" in res or "doc_id" in res else [])
        for r in recs:
            if isinstance(r, dict):
                self.seen.append(r)
        if res.get("next_cursor"):
            self.cursors.append((res["table"], res["next_cursor"]))

    def act(self, observation: dict) -> dict:
        self._absorb(observation)
        self.steps += 1
        rng = self.rng
        if self.steps > self.budget:
            return self._submit()
        choice = rng.random()
        if choice < 0.45 or not self.seen:
            table = rng.choice(TABLES)
            args = {"table": table, "limit": rng.randint(1, 50)}
            same = [c for t, c in self.cursors if t == table]
            if same and rng.random() < 0.5:
                args["cursor"] = rng.choice(same)
            return {"tool": "list_records", "args": args}
        rec = rng.choice(self.seen)
        if choice < 0.7 and "doc_id" in rec:
            return {"tool": "get_document", "args": {"doc_id": rec["doc_id"]}}
        if choice < 0.85:
            for table, key in (("ledger", "row_id"), ("invoices", "invoice_id"), ("payments", "payment_id"), ("fx", "rate_id")):
                if key in rec:
                    return {"tool": "get_record", "args": {"table": table, "id": rec[key]}}
        a, b = rng.randint(0, 10**6), rng.randint(1, 10**4)
        return {"tool": "calculator", "args": {"expression": f"{a} {rng.choice('+-*/')} {b}"}}

    def _submit(self) -> dict:
        rng = self.rng
        ids = []
        for r in self.seen:
            for key in ("invoice_id", "payment_id", "row_id", "doc_id", "rate_id"):
                if r.get(key):
                    ids.append(r[key])
        amounts = [r.get("total_minor") or r.get("amount_minor") or r.get("debit_minor") or r.get("credit_minor") or 0
                   for r in self.seen] or [0]
        findings = []
        for _ in range(rng.randint(0, 3) if ids else 0):
            findings.append(finding(rng.choice(TYPES), rng.sample(ids, min(len(ids), rng.randint(1, 2))),
                                    abs(int(rng.choice(amounts))), self.base,
                                    rng.sample(ids, min(len(ids), rng.randint(1, 10))), "random guess"))
        return submit_action(self.episode_id, findings)
