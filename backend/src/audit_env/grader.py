"""Grader: holds the private truth, validates and scores submissions, keeps the log.

Two deployments with the same scoring code:

* ``Grader`` (in-process) — used by ``AuditEnv(mode="train")``: open training mode,
  the terminal reward is returned to the policy.
* ``GraderServer`` / ``SubprocessGrader`` — used by ``AuditEnv(mode="eval")``: the
  episode is generated/loaded and scored in a *separate OS process*. The agent
  process only ever receives public records; truth, provenance, seeds, per-issue
  diagnostics and rewards stay in the grader process and its log file until the
  run is over. Protocol: one JSON object per line on stdin/stdout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .generator import Episode, generate_episode, load_private, load_public
from .matcher import Aliases, SubmissionError, match, normalize, validate_submission
from .reward import INVALID_SUBMISSION_REWARD, prf, terminal_reward
from .util import dumps


def load_episode(seed, config: Optional[dict]) -> Episode:
    """Resolve an episode source: a pre-generated directory or (seed, generator config)."""
    if isinstance(config, dict) and "episode_dir" in config:
        d = Path(config["episode_dir"])
        public = load_public(d)
        truth, provenance = load_private(d)
        return Episode(public, truth, provenance, clean_public={})
    return generate_episode(seed, config)


class Grader:
    def __init__(self, public: dict, truth: dict, log_path: Optional[Path] = None):
        self.episode_id = public["manifest"]["episode_id"]
        self.truth = truth
        self.aliases = Aliases(public)
        self.log_path = Path(log_path) if log_path else None
        self.result: Optional[dict] = None

    def grade(self, submission, inspection_steps: int, termination: str) -> dict:
        if self.result is not None:  # one score per episode; repeated submits cannot rescore
            return self.result
        issues = self.truth["issues"]
        tol = self.truth.get("tolerance_minor", 0)
        result = {
            "episode_id": self.episode_id,
            "termination": termination,
            "inspection_steps": inspection_steps,
            "n_truth": len(issues),
        }
        try:
            raw = validate_submission(submission, self.episode_id)
        except SubmissionError as exc:
            result.update(
                {
                    "valid": False,
                    "error": str(exc),
                    "n_findings": 0,
                    **prf(0, 0, len(issues), len(issues), 0),
                    "reward": INVALID_SUBMISSION_REWARD,
                    "matches": [],
                }
            )
            self._finish(result)
            return result
        findings = [normalize(f, self.aliases) for f in raw]
        pairs = match(findings, issues, tol)
        tp = len(pairs)
        metrics = prf(tp, len(findings) - tp, len(issues) - tp, len(issues), len(findings))
        result.update(
            {
                "valid": True,
                "error": None,
                "n_findings": len(findings),
                **metrics,
                "reward": terminal_reward(metrics["f1"], inspection_steps),
                "matches": [[i, issues[j]["issue_id"]] for i, j in pairs],
                "missed_types": sorted(
                    issues[j]["type"] for j in range(len(issues)) if j not in {jj for _, jj in pairs}
                ),
                "fp_types": sorted(findings[i].type for i in range(len(findings)) if i not in {ii for ii, _ in pairs}),
            }
        )
        self._finish(result)
        return result

    def _finish(self, result: dict) -> None:
        self.result = result
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(dumps(result) + "\n")


# --------------------------------------------------------------------------- eval: separate process


class GraderServer:
    """Runs inside the grader process. Never sends truth back."""

    def __init__(self, log_path: Path, plan: Optional[dict] = None):
        self.log_path = Path(log_path)
        self.plan = plan or {}
        self.grader: Optional[Grader] = None

    def handle(self, msg: dict) -> dict:
        cmd = msg.get("cmd")
        if cmd == "load":
            seed, config = msg.get("seed"), msg.get("config")
            if isinstance(config, dict) and "plan_slot" in config:
                slot = self.plan[config["plan_slot"]]
                seed, config = slot.get("seed"), slot.get("config")
            ep = load_episode(seed, config)
            self.grader = Grader(ep.public, ep.truth, self.log_path)
            return {"ok": True, "public": ep.public}
        if cmd == "submit":
            if self.grader is None:
                return {"ok": False}
            self.grader.grade(msg.get("submission"), int(msg.get("inspection_steps", 0)), msg.get("termination", ""))
            return {"ok": True}
        if cmd == "close":
            return {"ok": True, "bye": True}
        return {"ok": False}

    def serve(self, fin=sys.stdin, fout=sys.stdout) -> None:
        for line in fin:
            try:
                reply = self.handle(json.loads(line))
            except Exception:  # never echo internals to the agent side
                reply = {"ok": False}
            fout.write(json.dumps(reply, separators=(",", ":")) + "\n")
            fout.flush()
            if reply.get("bye"):
                break


class SubprocessGrader:
    """Agent-side handle to a grader process. Exposes load/submit only — no results."""

    def __init__(self, log_path: Path, plan_path: Optional[Path] = None):
        src = str(Path(__file__).resolve().parents[1])
        env = dict(os.environ)
        env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        cmd = [sys.executable, "-m", "audit_env.grader", "--log", str(log_path)]
        if plan_path:
            cmd += ["--plan", str(plan_path)]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)

    def _call(self, msg: dict) -> dict:
        self._proc.stdin.write(json.dumps(msg, separators=(",", ":")) + "\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline()
        if not line:
            raise RuntimeError("grader process unavailable")
        return json.loads(line)

    def load(self, seed, config) -> dict:
        reply = self._call({"cmd": "load", "seed": seed, "config": config})
        if not reply.get("ok"):
            raise RuntimeError("grader could not load episode")
        return reply["public"]

    def submit(self, submission, inspection_steps: int, termination: str) -> None:
        self._call(
            {
                "cmd": "submit",
                "submission": submission,
                "inspection_steps": inspection_steps,
                "termination": termination,
            }
        )

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self._call({"cmd": "close"})
            except Exception:
                pass
            self._proc.wait(timeout=10)


def main(argv: Optional[list] = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="audit_env grader process (eval mode)")
    ap.add_argument("--log", required=True)
    ap.add_argument("--plan", default=None, help="private JSON {slot: {seed, config}}")
    args = ap.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text()) if args.plan else None
    GraderServer(Path(args.log), plan).serve()


if __name__ == "__main__":
    main()
