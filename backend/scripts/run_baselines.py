"""Run the four baseline policies (+ our learned auditor) on the open episodes; write trajectories and a report.

``learned_auditor`` is ours, trained by scripts/train_learned.py; it is reported as a separate, extra row
and is not one of the organisers' four reference policies.

* train split -> AuditEnv(mode="train"): terminal reward returned to the policy (training trajectories).
* dev split   -> AuditEnv(mode="eval"):  grader in a separate process; policies see reward 0 / empty info;
                 scores are read from the grader log only after the run (closed-evaluation protocol).
The oracle reads truth from private files: it is grader-side by construction.

Outputs: runs/<split>/<policy>/trajectories.jsonl, runs/<split>/grader_log.jsonl, runs/report.json, runs/report.md
"""

import json
import shutil
import statistics
from collections import Counter

from _common import RUNS, episode_dirs
from audit_env.env import AuditEnv
from audit_env.generator import load_private
from audit_env.policies import FlagAllPolicy, OraclePolicy, RandomExplorerPolicy, SimpleReconcilerPolicy
from audit_env.policies.learned import LearnedAuditorPolicy
from audit_env.reward import prf
from audit_env.trajectories import TrajectoryWriter, run_episode

POLICIES = ["random_explorer", "simple_reconciler", "flag_all", "oracle", "learned_auditor"]
TYPES = ["duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"]


def make_policy(name, truth):
    return {
        "random_explorer": lambda: RandomExplorerPolicy(seed=0),
        "simple_reconciler": SimpleReconcilerPolicy,
        "flag_all": FlagAllPolicy,
        "oracle": lambda: OraclePolicy(truth),
        "learned_auditor": LearnedAuditorPolicy,
    }[name]()


def run_split(split: str, mode: str) -> list:
    out_dir = RUNS / split
    log = out_dir / "grader_log.jsonl"
    results = []
    for pname in POLICIES:
        env = AuditEnv(mode, grader_log=log) if mode == "eval" else AuditEnv("train")
        try:
            with TrajectoryWriter(out_dir / pname / "trajectories.jsonl") as w:
                for path, _meta in episode_dirs(split):
                    truth, _ = load_private(path)
                    pol = make_policy(pname, truth)
                    res = run_episode(env, pol, config={"episode_dir": str(path)}, writer=w)
                    res["grade"] = env._grader.result if mode == "train" else None
                    res["truth_types"] = [i["type"] for i in truth["issues"]]
                    res["clean"] = not truth["issues"]
                    res["split"] = split
                    results.append(res)
        finally:
            env.close()
    if mode == "eval":  # only now, after the run, read the grader's private log
        graded = [json.loads(x) for x in log.read_text().splitlines()]
        for res, g in zip(results, graded, strict=False):
            assert res["episode_id"] == g["episode_id"]
            res["grade"] = g
    return results


def summarize(results: list) -> dict:
    out = {}
    for pname in POLICIES:
        rs = [r for r in results if r["policy"] == pname]
        g = [r["grade"] for r in rs]
        missed, fps, total = Counter(), Counter(), Counter()
        for r in rs:
            total.update(r["truth_types"])
            missed.update(r["grade"].get("missed_types") or (r["truth_types"] if not r["grade"]["valid"] else []))
            fps.update(r["grade"].get("fp_types") or [])
        out[pname] = {
            "episodes": len(rs),
            "precision": statistics.mean(x["precision"] for x in g),
            "recall": statistics.mean(x["recall"] for x in g),
            "f1": statistics.mean(x["f1"] for x in g),
            "return": statistics.mean(x["reward"] for x in g),
            "return_clean": statistics.mean([x["reward"] for x, r in zip(g, rs, strict=False) if r["clean"]] or [0.0]),
            "steps": statistics.mean(r["steps"] for r in rs),
            "seconds": statistics.mean(r["seconds"] for r in rs),
            "invalid": sum(1 for x in g if not x["valid"]),
            "truncated": sum(1 for r in rs if r["truncated"]),
            "tp": sum(x["tp"] for x in g),
            "fp": sum(x["fp"] for x in g),
            "fn": sum(x["fn"] for x in g),
            "micro": prf(
                sum(x["tp"] for x in g),
                sum(x["fp"] for x in g),
                sum(x["fn"] for x in g),
                sum(x["n_truth"] for x in g),
                sum(x["n_findings"] for x in g),
            ),
            "recall_by_type": {t: (1 - missed[t] / total[t]) if total[t] else None for t in TYPES},
            "fp_by_type": {t: fps[t] for t in TYPES},
        }
    return out


def fmt(x):
    return "n/a" if x is None else f"{x:.3f}"


def main() -> None:
    if RUNS.exists():
        for sub in ("train", "dev"):
            shutil.rmtree(RUNS / sub, ignore_errors=True)
    RUNS.mkdir(exist_ok=True)
    report = {}
    for split, mode in (("train", "train"), ("dev", "eval")):
        report[split] = {"mode": mode, "policies": summarize(run_split(split, mode))}
    (RUNS / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Baseline report",
        "",
        "Diagnostics only. P, R, F1, return: means over episodes (per the case, P = R = 0 when the denominator is 0,",
        "so clean episodes pull the mean P/R down even for a perfect answer); micro P/R/F1 pool TP/FP/FN over",
        "episodes. Time is wall-clock seconds per episode (not part of any deterministic artefact).",
        "`learned_auditor` is our trained policy (extra row, not one of the four reference baselines);",
        "its held-out evaluation and learning curve are in runs/learned_eval.md.",
        "",
    ]
    for split, rep in report.items():
        lines += [
            f"## {split} ({rep['mode']} mode, {next(iter(rep['policies'].values()))['episodes']} episodes)",
            "",
            "| policy | P | R | F1 | micro P/R/F1 | return | return (clean) | steps | time, s | TP/FP/FN | invalid |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for p, s in rep["policies"].items():
            lines.append(
                f"| {p} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} | "
                f"{s['micro']['precision']:.2f}/{s['micro']['recall']:.2f}/{s['micro']['f1']:.2f} | "
                f"{s['return']:.3f} | "
                f"{s['return_clean']:.3f} | {s['steps']:.1f} | {s['seconds']:.3f} | "
                f"{s['tp']}/{s['fp']}/{s['fn']} | {s['invalid']} |"
            )
        lines += [
            "",
            "Recall by issue type / false positives by claimed type:",
            "",
            "| policy | " + " | ".join(TYPES) + " | FP " + " / ".join(t.split("_")[0] for t in TYPES) + " |",
            "|---|" + "---|" * (len(TYPES) + 1),
        ]
        for p, s in rep["policies"].items():
            lines.append(
                f"| {p} | "
                + " | ".join(fmt(s["recall_by_type"][t]) for t in TYPES)
                + " | "
                + " / ".join(str(s["fp_by_type"][t]) for t in TYPES)
                + " |"
            )
        lines.append("")
    (RUNS / "report.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
