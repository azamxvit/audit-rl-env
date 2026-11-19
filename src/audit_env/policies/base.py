"""Policy adapter interface: ``reset(observation)`` then ``act(observation) -> action`` until done."""
from __future__ import annotations


class Policy:
    name = "policy"

    def reset(self, observation: dict) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def act(self, observation: dict) -> dict:  # pragma: no cover - interface
        raise NotImplementedError


def submit_action(episode_id: str, findings: list) -> dict:
    return {"tool": "submit", "args": {"episode_id": episode_id, "findings": findings}}


def finding(type_: str, affected: list, amount: int, currency: str, evidence: list, explanation: str = "") -> dict:
    return {"type": type_, "affected_ids": list(affected), "claimed_amount_minor": int(amount),
            "currency": currency, "evidence_ids": list(evidence)[:10], "explanation": explanation[:1000]}


class TableReader:
    """Helper that pages through tables, one list_records call per step."""

    def __init__(self):
        self.data: dict = {}
        self.cursor: dict = {}
        self.complete: set = set()
        self.pending = None

    def request(self, table: str) -> dict:
        self.pending = table
        args = {"table": table, "limit": 50}
        if self.cursor.get(table):
            args["cursor"] = self.cursor[table]
        return {"tool": "list_records", "args": args}

    def absorb(self, observation: dict) -> None:
        if self.pending is None or observation.get("tool") != "list_records":
            return
        table = self.pending
        self.pending = None
        if not observation.get("ok"):
            self.complete.add(table)
            return
        res = observation["result"]
        self.data.setdefault(table, []).extend(res["records"])
        self.cursor[table] = res["next_cursor"]
        if res["next_cursor"] is None:
            self.complete.add(table)
