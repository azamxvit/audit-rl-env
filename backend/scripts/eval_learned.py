"""Held-out evaluation of the learned auditor through the real environment (diagnostic).

Episodes the detector never saw, generated from the *dev* configs (different
parameter mixes from the train configs) on fresh seeds 6_000_000+. Every policy
runs through ``AuditEnv`` exactly like the baselines: tools, 100-step budget,
grader. Writes runs/learned_eval.json and runs/learned_eval.md.
"""

import argparse
import json
import statistics
import sys
from collections import Counter

from _common import CONFIGS, RUNS
from audit_env.env import AuditEnv
from audit_env.generator import load_config
from audit_env.learning import Detector
from audit_env.policies import SimpleReconcilerPolicy
from audit_env.policies.learned import LearnedAuditorPolicy
from audit_env.reward import prf
from audit_env.trajectories import run_episode
from train_learned import build

CURVE = [1, 2, 5, 10, 30]  # training episodes per train config (6 configs)

SEED0 = 6_000_000
TYPES = ["duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"]


def run(policy_factory, configs, per_config):
    env = AuditEnv("train")
    rows = []
    try:
        for path in configs:
            cfg = load_config(path)
            for k in range(per_config):
                res = run_episode(env, policy_factory(), seed=SEED0 + k, config=cfg)
                g = env._grader.result
                rows.append({"config": f"{path.parent.name}/{path.name}", "steps": res["steps"], "grade": g})
    finally:
        env.close()
    return rows


def summary(rows):
    g = [r["grade"] for r in rows]
    tp, fp, fn = (sum(x[k] for x in g) for k in ("tp", "fp", "fn"))
    missed, fps = Counter(), Counter()
    for x in g:
        missed.update(x.get("missed_types") or [])
        fps.update(x.get("fp_types") or [])
    micro = prf(tp, fp, fn, sum(x["n_truth"] for x in g), sum(x["n_findings"] for x in g))
    return {
        "episodes": len(rows),
        "return": statistics.mean(x["reward"] for x in g),
        "return_clean": statistics.mean([x["reward"] for x in g if x["n_truth"] == 0] or [0.0]),
        "micro": micro,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "steps": statistics.mean(r["steps"] for r in rows),
        "invalid": sum(1 for x in g if not x["valid"]),
        "missed_by_type": {t: missed[t] for t in TYPES},
        "fp_by_type": {t: fps[t] for t in TYPES},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-config", type=int, default=20)
    a = ap.parse_args()
    configs = sorted((CONFIGS / "dev").glob("*.json"))
    report = {
        "seeds": [SEED0, SEED0 + a.per_config - 1],
        "configs": [f"dev/{p.name}" for p in configs],
        "policies": {
            "simple_reconciler": summary(run(SimpleReconcilerPolicy, configs, a.per_config)),
            "learned_auditor": summary(run(LearnedAuditorPolicy, configs, a.per_config)),
        },
        "learning_curve": [],
    }
    for n in CURVE:  # retrain from scratch on n episodes per config (threshold validated on n more)
        det = Detector(build(n, n))
        s = summary(run(lambda det=det: LearnedAuditorPolicy(det), configs, a.per_config))
        report["learning_curve"].append({"train_episodes": 6 * n, "threshold": det.threshold, **s})
    RUNS.mkdir(exist_ok=True)
    (RUNS / "learned_eval.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Learned auditor - held-out evaluation",
        "",
        f"{len(configs)} dev configs x {a.per_config} fresh seeds ({SEED0}+), never used in training; "
        "every policy runs through AuditEnv (tools, 100-step budget, grader).",
        "",
        "| policy | micro P | micro R | micro F1 | mean return | return (clean) | TP/FP/FN | steps | invalid |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, s in report["policies"].items():
        m = s["micro"]
        lines.append(
            f"| {name} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {s['return']:.3f} | "
            f"{s['return_clean']:.3f} | {s['tp']}/{s['fp']}/{s['fn']} | {s['steps']:.1f} | {s['invalid']} |"
        )
    lines += ["", "Missed / false positives by type:", "", "| policy | " + " | ".join(TYPES) + " |", "|---" * 5 + "|"]
    for name, s in report["policies"].items():
        cells = [f"{s['missed_by_type'][t]} / {s['fp_by_type'][t]}" for t in TYPES]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Learning curve: the detector retrained from scratch on N generated train-config episodes",
        "(threshold picked by mean terminal reward on N more), evaluated on the same held-out episodes:",
        "",
        "| train episodes | threshold | micro P | micro R | micro F1 | mean return | TP/FP/FN |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in report["learning_curve"]:
        m = c["micro"]
        lines.append(
            f"| {c['train_episodes']} | {c['threshold']} | {m['precision']:.3f} | {m['recall']:.3f} | "
            f"{m['f1']:.3f} | {c['return']:.3f} | {c['tp']}/{c['fp']}/{c['fn']} |"
        )
    (RUNS / "learned_eval.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
