"""Run YOUR policy on the environment: open episodes, your own seeds/configs, or episode directories.

    # a Python class (reset/act), fresh instance per episode
    PYTHONPATH=src python3 scripts/run_policy.py --policy examples/python_policy.py:FirstPagePolicy --split dev

    # any language: a process speaking JSON lines on stdin/stdout (see audit_env/external.py)
    PYTHONPATH=src python3 scripts/run_policy.py --cmd "python3 examples/jsonl_policy.py" --split dev --mode eval

    # your own seeds and generator config, or pre-generated episode directories
    PYTHONPATH=src python3 scripts/run_policy.py --policy audit_env.policies:SimpleReconcilerPolicy \\
        --config configs/dev/mixed.json --seeds 100-119
    PYTHONPATH=src python3 scripts/run_policy.py --policy ... --episode-dir path/to/ep1 path/to/ep2

Writes <out>/trajectories.jsonl (one line per step, schemas/trajectory.schema.json) and
<out>/grades.jsonl (schemas/grader_result.schema.json). In --mode eval the grader runs in its own
process, the policy sees reward 0 and empty info, and grades are read from the grader log after the run.
"""

import argparse
import json
import shlex
import statistics
import sys
from pathlib import Path

from _common import ROOT, episode_dirs
from audit_env.env import AuditEnv
from audit_env.external import ProcessPolicy, load_policy_class
from audit_env.generator import load_config
from audit_env.reward import prf
from audit_env.trajectories import TrajectoryWriter, run_episode


def sources(a) -> list:
    """(label, seed, config) triples for env.reset."""
    if a.episode_dir:
        return [(str(d), None, {"episode_dir": str(Path(d).resolve())}) for d in a.episode_dir]
    if a.config:
        lo, _, hi = a.seeds.partition("-")
        cfg = load_config(Path(a.config))
        return [(f"{a.config}#{s}", s, cfg) for s in range(int(lo), int(hi or lo) + 1)]
    return [(meta["path"], None, {"episode_dir": str(path)}) for path, meta in episode_dirs(a.split)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--policy", help="module:Class or file.py:Class (reset/act)")
    who.add_argument("--cmd", help="command of a JSON-lines policy process, e.g. 'node agent.js'")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--split", choices=["train", "dev"], default="dev", help="open episodes (default dev)")
    src.add_argument("--config", help="generator config JSON (use with --seeds)")
    src.add_argument("--episode-dir", nargs="+", help="episode directories (public/ + private/)")
    ap.add_argument("--seeds", default="0-9", help="inclusive range for --config, e.g. 100-119")
    ap.add_argument("--mode", choices=["train", "eval"], default="train")
    ap.add_argument("--out", default=None, help="output directory (default runs/custom/<name>)")
    ap.add_argument("--reply-timeout", type=float, default=60.0, help="seconds to wait for a process reply")
    a = ap.parse_args()

    name = (a.policy or a.cmd).replace("/", "_").replace(" ", "_").replace(":", "_")[:60]
    out = Path(a.out) if a.out else ROOT / "runs" / "custom" / name
    out.mkdir(parents=True, exist_ok=True)
    log = out / "grades.jsonl"
    for f in (log, out / "trajectories.jsonl"):
        f.unlink(missing_ok=True)

    proc = ProcessPolicy(shlex.split(a.cmd), a.reply_timeout, cwd=str(ROOT)) if a.cmd else None
    cls = load_policy_class(a.policy) if a.policy else None
    env = AuditEnv(a.mode, grader_log=log) if a.mode == "eval" else AuditEnv("train", grader_log=log)
    results = []
    try:
        with TrajectoryWriter(out / "trajectories.jsonl") as w:
            for label, seed, cfg in sources(a):
                policy = proc or cls()
                res = run_episode(env, policy, seed=seed, config=cfg, writer=w)
                results.append((label, res))
    finally:
        env.close()
        if proc:
            proc.close()

    grades = [json.loads(x) for x in log.read_text().splitlines()]
    print(f"{'episode':<40} {'steps':>5} {'TP/FP/FN':>9} {'F1':>6} {'reward':>7}  termination")
    for (label, res), g in zip(results, grades, strict=True):
        tpfpfn = f"{g['tp']}/{g['fp']}/{g['fn']}"
        valid = "" if g["valid"] else f"  INVALID: {g['error']}"
        print(
            f"{label[-40:]:<40} {res['steps']:>5} {tpfpfn:>9} {g['f1']:>6.3f} {g['reward']:>+7.3f}  {g['termination']}{valid}"
        )
    tp, fp, fn = (sum(g[k] for g in grades) for k in ("tp", "fp", "fn"))
    micro = prf(tp, fp, fn, sum(g["n_truth"] for g in grades), sum(g["n_findings"] for g in grades))
    print(
        f"\n{len(grades)} episodes, mode {a.mode}: micro P/R/F1 {micro['precision']:.3f}/{micro['recall']:.3f}/"
        f"{micro['f1']:.3f}, mean return {statistics.mean(g['reward'] for g in grades):+.3f}, "
        f"mean steps {statistics.mean(r['steps'] for _, r in results):.1f}"
    )
    print(f"trajectories: {out / 'trajectories.jsonl'}\ngrades:       {log}")
    if a.mode == "eval":
        print("(eval mode: the policy saw reward 0 and empty info; grades come from the grader's own log)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
