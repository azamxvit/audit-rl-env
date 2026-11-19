"""Metrics and terminal reward (case section 05)."""

from __future__ import annotations

STEP_COST = 0.002


def prf(tp: int, fp: int, fn: int, n_truth: int, n_findings: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if n_truth == 0 and n_findings == 0:
        f1 = 1.0
    elif n_truth == 0:
        f1 = 0.0
    else:
        denom = 2 * tp + fp + fn
        f1 = (2 * tp / denom) if denom else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def terminal_reward(f1: float, inspection_steps: int) -> float:
    """Shared reward: clip(2*F1 - 1 - 0.002*inspection_steps, -1, 1)."""
    return clip(2.0 * f1 - 1.0 - STEP_COST * inspection_steps)


INVALID_SUBMISSION_REWARD = -1.0
