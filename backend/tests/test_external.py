"""Plugging in outside policies: Python classes by spec, and processes speaking JSON lines."""

import json
import subprocess
import sys

from audit_env.env import AuditEnv
from audit_env.external import ProcessPolicy, load_policy_class
from audit_env.schema import Registry
from audit_env.trajectories import TrajectoryWriter, run_episode
from conftest import ROOT

DEV0 = {
    "episode_dir": str(
        ROOT / "episodes" / json.loads((ROOT / "episodes/index.json").read_text())["episodes"][10]["path"]
    )
}
REG = Registry()


def _script(tmp_path, body: str) -> list:
    p = tmp_path / "policy.py"
    p.write_text(body)
    return [sys.executable, str(p)]


def test_plain_class_from_file_and_module():
    cls = load_policy_class(str(ROOT / "examples" / "python_policy.py") + ":UnappliedCashPolicy")
    res = run_episode(AuditEnv("train"), cls(), config=DEV0)
    assert res["terminated"] and res["policy"] == "UnappliedCashPolicy"
    assert load_policy_class("audit_env.policies:SimpleReconcilerPolicy").name == "simple_reconciler"


def test_process_policy_runs_episodes_and_trajectories_conform(tmp_path):
    proc = ProcessPolicy([sys.executable, str(ROOT / "examples" / "jsonl_policy.py")], reply_timeout_s=10)
    env = AuditEnv("train")
    try:
        with TrajectoryWriter(tmp_path / "t.jsonl") as w:
            for _ in range(2):  # one process serves several episodes
                res = run_episode(env, proc, config=DEV0, writer=w)
                assert res["terminated"] and res["steps"] == 2
    finally:
        proc.close()
    assert proc.proc.returncode == 0
    for line in (tmp_path / "t.jsonl").read_text().splitlines():
        assert REG.errors(json.loads(line), "trajectory.schema.json") == []


def test_garbage_crash_and_silence_cost_steps_but_never_break_the_env(tmp_path):
    cases = {
        "garbage": "import sys\nfor line in sys.stdin:\n    print('not json', flush=True)\n",
        "crash": "import sys\nsys.stdin.readline()\nraise SystemExit(3)\n",
        "silent": "import sys, time\nfor line in sys.stdin:\n    time.sleep(5)\n",
    }
    for name, body in cases.items():
        proc = ProcessPolicy(_script(tmp_path, body), reply_timeout_s=0.2)
        env = AuditEnv("train", max_steps=3)
        try:
            res = run_episode(env, proc, config=DEV0)
        finally:
            proc.close()
        assert res["truncated"] and res["steps"] == 3, name
        assert env._grader.result["termination"] == "step_limit" and env._grader.result["reward"] <= 1.0


def test_run_policy_script_in_eval_mode(tmp_path):
    out = subprocess.run(
        [
            sys.executable,
            "scripts/run_policy.py",
            "--cmd",
            f"{sys.executable} examples/jsonl_policy.py",
            "--split",
            "dev",
            "--mode",
            "eval",
            "--out",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    ).stdout
    assert "10 episodes, mode eval" in out
    grades = [json.loads(x) for x in (tmp_path / "grades.jsonl").read_text().splitlines()]
    assert len(grades) == 10 and all(REG.errors(g, "grader_result.schema.json") == [] for g in grades)
    clean = [g for g in grades if g["n_truth"] == 0]
    assert clean and all(g["f1"] == 1.0 for g in clean)  # an empty answer is right on clean books
