"""Oracle — GRADER-SIDE ONLY. Reads truth and submits it with a minimal evidence set at step 1.

It measures the reward ceiling (1.0) and sanity of matcher/evidence, not agent ability.
It must never be given to an agent process in eval mode.
"""
from __future__ import annotations

from .base import Policy, finding, submit_action


class OraclePolicy(Policy):
    name = "oracle"

    def __init__(self, truth: dict):
        self.truth = truth

    def reset(self, observation: dict) -> None:
        self.episode_id = observation["manifest"]["episode_id"]

    def act(self, observation: dict) -> dict:
        findings = [finding(i["type"], i["affected_ids"], i["expected_amount_minor"], i["currency"],
                            i["evidence_sets"][0], "oracle") for i in self.truth["issues"]]
        return submit_action(self.episode_id, findings)
