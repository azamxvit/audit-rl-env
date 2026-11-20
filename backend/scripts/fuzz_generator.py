"""Fuzz the generator with unseen seeds and random parameter combinations (the hidden-evaluation setting).

Each case draws a config inside the documented ranges (DESIGN.md §13), generates an
episode and requires: no crash, the independent checker accepts it (invariants
before/after injection, full audit == truth, every evidence set sufficient), the
paired permutation + ID-renaming check holds, and the oracle answer scores 1.0.

    PYTHONPATH=src python3 scripts/fuzz_generator.py [--cases 300] [--seed 2026]
Exit code 1 on any failure; failures are grouped by kind with a reproducing config.
"""

import argparse
import json
import random
import sys
import time
import traceback
from collections import Counter

from _common import RUNS  # noqa: F401  (puts src/ on sys.path)
from audit_env.checker import verify_episode
from audit_env.generator import generate_episode
from audit_env.grader import Grader
from audit_env.money import CURRENCY_EXPONENTS
from audit_env.transform import map_findings, transform_episode

CURRENCIES = ["USD", "EUR", "GBP", "CHF", "JPY", "KZT"]
ERROR_TYPES = ["duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"]
SCENARIOS = ["fx_partial_boundary", "cutoff_fx"]


def oracle(truth: dict) -> dict:
    return {
        "episode_id": truth["episode_id"],
        "findings": [
            {
                "type": i["type"],
                "affected_ids": i["affected_ids"],
                "claimed_amount_minor": i["expected_amount_minor"],
                "currency": i["currency"],
                "evidence_ids": i["evidence_sets"][0],
                "explanation": "",
            }
            for i in truth["issues"]
        ],
    }


def random_config(r: random.Random, i: int) -> dict:
    def span(lo, hi, width):
        a = r.randint(lo, hi)
        return [a, a + r.randint(0, width)]

    rows_lo = r.randint(200, 1800)
    cfg = {
        "config_id": f"fuzz-{i}",
        "period": r.choice(["month", "quarter"]),
        "base_currencies": r.sample(CURRENCIES, r.randint(1, 3)),
        "foreign_currencies": r.sample(CURRENCIES, r.randint(1, 6)),
        "foreign_customer_share": r.choice([0.0, 0.2, 0.5, 0.9, 1.0]),
        "n_customers": span(3, 15, 6),
        "n_invoices": span(15, 60, 15),
        "ledger_rows": [rows_lo, min(2000, rows_lo + r.randint(0, 300))],
        "errors": {t: {"count": span(0, 3, 2)} for t in ERROR_TYPES},
        "scenarios": {s: {"count": [0, r.randint(0, 2)]} for s in SCENARIOS},
    }
    if r.random() < 0.15:  # clean company
        cfg["errors"] = {t: {"count": 0} for t in ERROR_TYPES}
        cfg["scenarios"] = {s: {"count": 0} for s in SCENARIOS}
    return cfg


def check(seed: int, cfg: dict, i: int) -> list:
    try:
        ep = generate_episode(seed, cfg)
    except Exception as e:  # noqa: BLE001 - every crash is a finding
        frame = traceback.extract_tb(e.__traceback__)[-1]
        return [f"crash {type(e).__name__} at {frame.filename.rsplit('/', 1)[-1]}:{frame.lineno}"]
    p = verify_episode(ep.public, ep.truth, ep.clean_public)
    pub2, tr2, mapping = transform_episode(ep.public, ep.truth, seed=("fuzz", i))
    p += [f"paired: {x}" for x in verify_episode(pub2, tr2)]
    sub = oracle(ep.truth)
    r1 = Grader(ep.public, ep.truth).grade(sub, 0, "submit")["reward"]
    r2 = Grader(pub2, tr2).grade(map_findings(sub, mapping), 0, "submit")["reward"]
    if not (r1 == r2 == 1.0):
        p.append(f"oracle reward {r1} / paired {r2}")
    n_rows, n_issues = len(ep.public["ledger"]), len(ep.truth["issues"])
    if not 200 <= n_rows <= 2000:
        p.append(f"ledger rows {n_rows} outside 200..2000")
    if n_issues > 12:
        p.append(f"{n_issues} issues > 12")
    if any(i["currency"] not in CURRENCY_EXPONENTS for i in ep.truth["issues"]):
        p.append("unknown currency in truth")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=300)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    r = random.Random(a.seed)
    kinds, example = Counter(), {}
    t0 = time.perf_counter()
    for i in range(a.cases):
        cfg = random_config(r, i)
        seed = r.randint(0, 10**9)
        for problem in check(seed, cfg, i):
            key = problem.split(":")[0][:80] if not problem.startswith("crash") else problem
            kinds[key] += 1
            example.setdefault(key, {"seed": seed, "config": cfg, "problem": problem[:400]})
    bad = sum(kinds.values())
    print(
        f"fuzz: {a.cases} random configs, {len(kinds)} failure kinds, {bad} problems ({time.perf_counter() - t0:.1f}s)"
    )
    for key, n in kinds.most_common():
        print(f"  {n:4d}  {key}")
        print(f"        repro: {json.dumps(example[key], sort_keys=True)[:600]}")
    return 1 if kinds else 0


if __name__ == "__main__":
    sys.exit(main())
