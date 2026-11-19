"""Error injection: one module per error type, plus interacting scenarios and distractors."""
from __future__ import annotations

from . import duplicate_invoice, fx_error, payment_allocation, period_cutoff
from .base import ISSUE_TYPES, InjectionContext, IssueSpec
from .scenarios import SCENARIOS

INJECTORS = {
    "duplicate_invoice": duplicate_invoice.inject,
    "payment_allocation": payment_allocation.inject,
    "fx_error": fx_error.inject,
    "period_cutoff": period_cutoff.inject,
}

MAX_ISSUES = 12


def _count(rng, spec) -> int:
    if spec is None:
        return 0
    c = spec.get("count", [0, 0]) if isinstance(spec, dict) else spec
    if isinstance(c, int):
        return c
    return rng.randint(int(c[0]), int(c[1]))


def plan_and_inject(ctx: InjectionContext, cfg: dict) -> list:
    """Draw how many errors of each kind to inject (from config) and inject them."""
    rng = ctx.rng
    specs: list = []
    scenario_counts = [(name, _count(rng, cfg.get("scenarios", {}).get(name))) for name in SCENARIOS]
    type_counts = [(t, _count(rng, cfg.get("errors", {}).get(t))) for t in ISSUE_TYPES]
    for name, n in scenario_counts:
        for _ in range(n):
            if len(specs) + 2 > MAX_ISSUES:
                break
            specs.extend(SCENARIOS[name](ctx))
    queue = []
    for t, n in type_counts:
        variants = (cfg.get("errors", {}).get(t) or {}).get("variants") if isinstance(cfg.get("errors", {}).get(t), dict) else None
        for _ in range(n):
            queue.append((t, rng.choice(variants) if variants else None))
    for t, variant in queue:
        if len(specs) >= MAX_ISSUES:
            break
        specs.extend(INJECTORS[t](ctx, variant))
    return specs


__all__ = ["ISSUE_TYPES", "INJECTORS", "SCENARIOS", "InjectionContext", "IssueSpec", "plan_and_inject", "MAX_ISSUES"]
