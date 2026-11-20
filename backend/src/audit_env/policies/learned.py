"""Learned auditor (ours, trained): pages through the open tables, scores candidates with a trained detector.

Unlike the four reference baselines this one is *learned*: the decision "is this
candidate an issue of type T?" comes from ``audit_env/learning/learned_auditor.json``,
fitted by ``scripts/train_learned.py`` on generated train-config episodes (labels from
the open train truth) with its decision threshold chosen by the environment's own
terminal reward. At run time it sees only tool observations - no truth, no seed.
"""

from __future__ import annotations

from ..learning import Detector, extract
from .base import Policy, TableReader, finding, submit_action

READ_ORDER = ("payments", "invoices", "fx", "ledger")


class LearnedAuditorPolicy(Policy):
    name = "learned_auditor"

    def __init__(self, detector: Detector | None = None, threshold: float | None = None):
        self.detector = detector or Detector.load()
        self.threshold = self.detector.threshold if threshold is None else threshold

    def reset(self, observation: dict) -> None:
        self.manifest = observation["manifest"]
        self.policy = observation["policy"]
        self.max_steps = observation["max_steps"]
        self.reader = TableReader()
        self.steps = 0

    def act(self, observation: dict) -> dict:
        self.reader.absorb(observation)
        self.steps += 1
        if self.steps < self.max_steps:  # the last step is always kept for submit
            for table in READ_ORDER:
                if table not in self.reader.complete:
                    return self.reader.request(table)
        return submit_action(self.manifest["episode_id"], self.findings())

    def public_view(self) -> dict:
        data = self.reader.data
        view = {"manifest": self.manifest, "policy": self.policy}
        for table in READ_ORDER:
            view[table] = data.get(table, [])
        return view

    def findings(self) -> list:
        return decide(self.detector, extract(self.public_view()), self.threshold, self.manifest["base_currency"])


def decide(detector: Detector, candidates: list, threshold: float, base_currency: str) -> list:
    """Flag every (candidate, head) whose score reaches ``threshold``; strongest first, at most 30."""
    best: dict = {}
    for c in candidates:
        for head, score in detector.scores(c).items():
            tmpl = c.findings.get(head)
            if tmpl is None or score < threshold:
                continue
            ids, amount, evidence = tmpl
            key = (head, tuple(sorted(ids)))
            if key not in best or score > best[key][0]:
                best[key] = (score, head, ids, amount, evidence)
    ranked = sorted(best.values(), key=lambda t: (-t[0], t[1], t[2]))[:30]
    return [
        finding(head, ids, amount, base_currency, evidence, f"learned detector, score {score:.3f}")
        for score, head, ids, amount, evidence in ranked
    ]
