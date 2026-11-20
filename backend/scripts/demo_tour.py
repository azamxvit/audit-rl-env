"""Demo tour: the environment in seven short scenes, offline, ~1 minute of output (see DEMO.md).

    PYTHONPATH=src python3 scripts/demo_tour.py [--pace 2.5]

--pace N pauses N seconds between scenes, for screen recording. Everything is computed live
from the open dev episodes and fresh seeds; nothing is pre-recorded.
"""

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from _common import CONFIGS, episode_dirs
from audit_env.env import AuditEnv
from audit_env.generator import generate_episode, load_config, load_private, public_files
from audit_env.grader import Grader
from audit_env.policies import (
    FlagAllPolicy,
    LearnedAuditorPolicy,
    OraclePolicy,
    RandomExplorerPolicy,
    SimpleReconcilerPolicy,
)
from audit_env.trajectories import TrajectoryWriter, run_episode
from audit_env.transform import map_findings, transform_episode
from audit_env.util import dumps, sha256_text

TTY = sys.stdout.isatty()
PACE = 0.0


def bold(s: str) -> str:
    return f"\033[1m{s}\033[0m" if TTY else s


def dim(s: str) -> str:
    return f"\033[2m{s}\033[0m" if TTY else s


def scene(n: int, title: str, note: str) -> None:
    if n > 1 and PACE:
        time.sleep(PACE)
    print()
    print(bold(f"[{n}/7] {title}"))
    print(dim("      " + note))


def short(action) -> str:
    if not isinstance(action, dict):
        return repr(action)[:60]
    if action.get("tool") == "submit":
        return f"submit({len(action['args']['findings'])} findings)"
    args = dict(action.get("args", {}))
    if isinstance(args.get("cursor"), str):
        args["cursor"] = args["cursor"][:10] + "..."
    return f"{action.get('tool')}({json.dumps(args)[:64]})"


def grade_line(g: dict) -> str:
    return f"TP={g['tp']} FP={g['fp']} FN={g['fn']}  F1={g['f1']:.3f}  reward={g['reward']:+.3f}"


def main() -> int:
    global PACE
    ap = argparse.ArgumentParser()
    ap.add_argument("--pace", type=float, default=0.0)
    PACE = ap.parse_args().pace

    dev = episode_dirs("dev")
    path, meta = dev[4]  # a books-with-errors episode
    clean_path = next(p for p, m in dev if m["n_issues"] == 0)
    truth, _ = load_private(path)
    env = AuditEnv("train")

    # 1 ------------------------------------------------------------------------------------------
    scene(
        1,
        "reset(): one fictional company, one period",
        "The agent sees the task, manifest, policy and table sizes - never the seed or the answer.",
    )
    obs, info = env.reset(config={"episode_dir": str(path)})
    m = obs["manifest"]
    print(
        f"  {m['episode_id']}  {m['company_name']}  {m['period_start']}..{m['period_end']}  tz {m['timezone']}  functional {m['base_currency']}"
    )
    print("  tables: " + ", ".join(f"{t}={v['count']}" for t, v in obs["tables"].items()))
    print(f"  tools : {', '.join(t['name'] for t in obs['tools'])}   budget: {obs['steps_remaining']} steps")
    print(f"  info  : {info}")

    # 2 ------------------------------------------------------------------------------------------
    scene(
        2,
        "step(): narrow tools, bounded errors, every call costs a step",
        "Pages hold <= 50 records; errors are fixed codes that never echo input or internals.",
    )
    page = env.step({"tool": "list_records", "args": {"table": "payments", "limit": 3}})[0]
    pay = page["result"]["records"][0]
    print(
        f"  list_records(payments, limit 3) -> {len(page['result']['records'])} records, next_cursor {page['result']['next_cursor'][:10]}..."
    )
    print(
        f"     first: {pay['payment_id']} {pay['kind']} {pay['amount_minor']} {pay['currency']} refs={pay['invoice_refs']}"
    )
    for action in (
        {"tool": "get_record", "args": {"table": "ledger", "id": "LR-NOTREAL1"}},
        {"tool": "calculator", "args": {"expression": "__import__('os').system('ls')"}},
        {"tool": "shell", "args": {"cmd": "cat private/truth.json"}},
    ):
        o = env.step(action)[0]
        print(f"  {short(action):<62} -> {o['error']['code']}: {o['error']['message']}  ({o['steps_remaining']} left)")
    o = env.step({"tool": "calculator", "args": {"expression": "1234.56 * 1.0845"}})[0]
    print(f"  {'calculator(1234.56 * 1.0845)':<62} -> {o['result']['value']}  (Decimal, no eval)")

    # 3 ------------------------------------------------------------------------------------------
    scene(
        3,
        "A scripted auditor works through the tools and submits",
        "simple_reconciler: reads payments, invoices and the ledger page by page, then applies two checks.",
    )
    pol = SimpleReconcilerPolicy()
    obs, _ = env.reset(config={"episode_dir": str(path)})
    pol.reset(obs)
    done = False
    while not done:
        action = pol.act(obs)
        obs, reward, term, trunc, info = env.step(action)
        if action["tool"] == "submit" or (100 - obs["steps_remaining"]) in (1, 2):
            print(f"  step {100 - obs['steps_remaining']:3d}  {short(action)}")
        elif (100 - obs["steps_remaining"]) == 3:
            print("  ...       (paging through the ledger)")
        done = term or trunc
    for f in action["args"]["findings"]:
        print(
            f"     -> {f['type']:<19} {','.join(f['affected_ids']):<28} {f['claimed_amount_minor']:>10} {f['currency']}  evidence {len(f['evidence_ids'])} ids"
        )
    print(f"  grader: {grade_line(env._grader.result)}   (truth: {len(truth['issues'])} issues)")

    # 4 ------------------------------------------------------------------------------------------
    scene(
        4,
        "The reward cannot be gamed",
        "Same episode, five policies. Flag-everything and random guessing lose; repeats and guessed ids earn nothing.",
    )
    print(f"  {'policy':<20} {'steps':>5}  result")
    for name, make in (
        ("random_explorer", lambda: RandomExplorerPolicy(seed=0)),
        ("flag_all (attack)", FlagAllPolicy),
        ("simple_reconciler", SimpleReconcilerPolicy),
        ("learned_auditor", LearnedAuditorPolicy),
        ("oracle (grader-side)", lambda: OraclePolicy(truth)),
    ):
        res = run_episode(env, make(), config={"episode_dir": str(path)})
        print(f"  {name:<20} {res['steps']:>5}  {grade_line(env._grader.result)}")
    sub = _oracle_submission(truth)
    doubled = {"episode_id": sub["episode_id"], "findings": sub["findings"] * 2}
    no_evidence = {"episode_id": sub["episode_id"], "findings": [{**f, "evidence_ids": []} for f in sub["findings"]]}
    print(
        f"  {'every right answer twice':<26} -> {grade_line(Grader(*_public_truth(path)).grade(doubled, 1, 'submit'))}"
    )
    print(
        f"  {'right answers, no evidence':<26} -> {grade_line(Grader(*_public_truth(path)).grade(no_evidence, 1, 'submit'))}"
    )

    # 5 ------------------------------------------------------------------------------------------
    scene(
        5,
        "Clean books: silence beats false accusations",
        "Some companies have no errors; an empty answer is the right one.",
    )
    for name, make in (
        ("simple_reconciler", SimpleReconcilerPolicy),
        ("learned_auditor", LearnedAuditorPolicy),
        ("flag_all (attack)", FlagAllPolicy),
    ):
        run_episode(env, make(), config={"episode_dir": str(clean_path)})
        print(f"  {name:<20} {grade_line(env._grader.result)}")

    # 6 ------------------------------------------------------------------------------------------
    scene(
        6,
        "Reproducible, and robust to harmless transformations",
        "Same seed + config + version + actions -> identical bytes. Shuffling rows and renaming every id keeps the answer.",
    )
    cfg = load_config(CONFIGS / "dev" / "interacting.json")
    h1 = sha256_text(dumps(public_files(generate_episode(424242, cfg).public)))
    h2 = sha256_text(dumps(public_files(generate_episode(424242, cfg).public)))
    print(f"  generate(seed 424242) twice: {h1[:16]}... == {h2[:16]}...  {h1 == h2}")
    with tempfile.TemporaryDirectory() as tmp:
        hashes = []
        for k in range(2):
            p = Path(tmp) / f"t{k}.jsonl"
            with TrajectoryWriter(p) as w:
                run_episode(env, SimpleReconcilerPolicy(), config={"episode_dir": str(path)}, writer=w)
            hashes.append(sha256_text(p.read_text()))
        print(f"  same policy, same episode, two runs -> trajectories identical: {hashes[0] == hashes[1]}")
    ep = generate_episode(424242, cfg)
    pub2, tr2, mapping = transform_episode(ep.public, ep.truth, seed="demo")
    sub = _oracle_submission(ep.truth)
    r1 = Grader(ep.public, ep.truth).grade(sub, 0, "submit")["reward"]
    r2 = Grader(pub2, tr2).grade(map_findings(sub, mapping), 0, "submit")["reward"]
    some = next(iter(mapping.items()))
    print(f"  rows permuted, {len(mapping)} ids renamed (e.g. {some[0]} -> {some[1]}): oracle reward {r1} -> {r2}")

    # 7 ------------------------------------------------------------------------------------------
    scene(
        7,
        "Closed evaluation: the grader lives in another process",
        "In eval mode the policy gets reward 0 and empty info; the score exists only in the grader's log.",
    )
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "grader_log.jsonl"
        ev = AuditEnv("eval", grader_log=log)
        try:
            res = run_episode(ev, LearnedAuditorPolicy(), config={"episode_dir": str(path)})
            print(f"  policy saw: return={res['return']}  info={res['info']}")
        finally:
            ev.close()
        g = json.loads(log.read_text().splitlines()[-1])
        print(f"  grader log: {grade_line(g)}")
    print()
    print(bold("Done.") + " Full check: make verify  |  report: backend/runs/report.md  |  play it yourself: make play")
    return 0


def _public_truth(path: Path):
    from audit_env.generator import load_public

    t, _ = load_private(path)
    return load_public(path), t


def _oracle_submission(truth: dict) -> dict:
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


if __name__ == "__main__":
    sys.exit(main())
