"""Local CI: the whole pipeline on this machine, with a committed report instead of a hosted badge.

    python3 ci/ci.py            # full run  (make ci)
    python3 ci/ci.py --fast     # lint + backend tests only (make ci-fast; the pre-push hook)
    python3 ci/ci.py --skip docker,e2e

Steps run in order; each is PASS, FAIL or SKIP (with the reason, e.g. Docker not running).
Every step runs even after a failure, so one report shows everything. Writes ci/last-run.md and
ci/last-run.json (fast runs: ci/last-fast-run.*, not committed) with the commit, whether the tree was clean, tool versions and timings; exit code
1 if any step failed. Nothing is uploaded anywhere.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ci"


def sh(cmd: str, cwd: Path = ROOT, timeout: int = 1800) -> tuple:
    p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)


def version(cmd: str) -> str:
    try:
        rc, out = sh(cmd, timeout=30)
        return out.strip().splitlines()[0] if rc == 0 and out.strip() else "n/a"
    except Exception:  # noqa: BLE001
        return "n/a"


def docker_ready() -> str | None:
    if not shutil.which("docker"):
        return "docker not installed"
    return None if sh("docker info", timeout=30)[0] == 0 else "Docker daemon not running"


def chromium_ready() -> str | None:
    if not (ROOT / "frontend" / "node_modules" / "@playwright" / "test").exists():
        return "frontend dependencies not installed (cd frontend && npm ci)"
    caches = [Path.home() / "Library/Caches/ms-playwright", Path.home() / ".cache/ms-playwright"]
    if not any(c.exists() and any(c.glob("chromium*")) for c in caches):
        return "Playwright Chromium not installed (cd frontend && npx playwright install chromium)"
    return None


STEPS = [
    # name, command, cwd, fast?, precondition
    ("lint: ruff + prettier", "make lint", ROOT, True, None),
    ("backend tests", "make test", ROOT, True, None),
    ("make verify (episodes, tests, data, fuzz 150, baselines, learned eval)", "make verify", ROOT, False, None),
    ("published episodes byte-identical after regeneration", "git diff --quiet -- backend/episodes", ROOT, False, None),
    ("learned auditor weights reproducible", "make -s train-learned-check", ROOT, False, None),
    ("generator fuzz, 600 random configs", "make -s fuzz CASES=600", ROOT, False, None),
    ("frontend unit tests (Vitest)", "make -s frontend-test", ROOT, False, None),
    (
        "frontend/dist matches sources",
        "cd frontend && npm run -s build >/dev/null && git diff --quiet -- dist",
        ROOT,
        False,
        None,
    ),
    ("frontend e2e + axe (Playwright)", "make -s e2e", ROOT, False, chromium_ready),
    (
        "Docker: build + verify offline, --cpus 2 --memory 4g",
        "docker build -q -t audit-env:ci . >/dev/null && "
        "docker run --rm --network none --cpus 2 --memory 4g audit-env:ci | tail -1 | grep -q 'verify: OK'",
        ROOT,
        False,
        docker_ready,
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="lint + backend tests only")
    ap.add_argument("--skip", default="", help="comma-separated keywords of steps to skip (e.g. docker,e2e)")
    a = ap.parse_args()
    skip_words = [w.strip().lower() for w in a.skip.split(",") if w.strip()]

    commit = sh("git rev-parse HEAD")[1].strip()
    dirty = bool(sh("git status --porcelain --untracked-files=no")[1].strip())
    started = datetime.now(timezone.utc)
    results = []
    for name, cmd, cwd, fast, pre in STEPS:
        if a.fast and not fast:
            continue
        reason = next((f"--skip {w}" for w in skip_words if w in name.lower()), None) or (pre() if pre else None)
        if reason:
            results.append({"step": name, "status": "SKIP", "seconds": 0.0, "note": reason})
            print(f"SKIP  {name}  ({reason})", flush=True)
            continue
        print(f"....  {name}", flush=True)
        t0 = time.perf_counter()
        try:
            rc, out = sh(cmd, cwd)
        except subprocess.TimeoutExpired:
            rc, out = 124, "timeout"
        dt = time.perf_counter() - t0
        status = "PASS" if rc == 0 else "FAIL"
        tail = "" if rc == 0 else "\n".join(out.strip().splitlines()[-15:])
        results.append({"step": name, "status": status, "seconds": round(dt, 1), "note": tail})
        print(f"{status}  {name}  ({dt:.1f}s)", flush=True)
        if tail:
            print("      " + tail.replace("\n", "\n      "), flush=True)

    ok = all(r["status"] != "FAIL" for r in results)
    report = {
        "result": "PASS" if ok else "FAIL",
        "mode": "fast" if a.fast else "full",
        "commit": commit,
        "tree_clean": not dirty,
        "started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
        "platform": f"{platform.system()} {platform.machine()}",
        "tools": {
            "python": platform.python_version(),
            "node": version("node --version"),
            "docker": version("docker version --format '{{.Server.Version}}'"),
            "ruff": version(f"{shutil.which('ruff') or ROOT / '.venv/bin/ruff'} --version"),
        },
        "steps": results,
    }
    OUT.mkdir(exist_ok=True)
    # the committed report is the full run; fast runs (the pre-push hook) go to an ignored file
    stem = "last-fast-run" if a.fast else "last-run"
    (OUT / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Local CI - last run",
        "",
        f"**{report['result']}** ({report['mode']}) for commit `{commit[:12]}`"
        + ("" if report["tree_clean"] else " **with uncommitted changes**")
        + f", {report['started_utc']}, {report['duration_s']} s, {report['platform']}.",
        "",
        "Tools: " + ", ".join(f"{k} {v}" for k, v in report["tools"].items()) + ".",
        "",
        "| step | result | time, s | note |",
        "|---|---|---|---|",
    ]
    for r in results:
        note = r["note"].splitlines()[-1] if r["note"] else ""
        lines.append(f"| {r['step']} | {r['status']} | {r['seconds']} | {note.replace('|', '/')} |")
    lines += ["", "Produced by `make ci` (ci/ci.py). Reproduce on your machine with the same command."]
    (OUT / f"{stem}.md").write_text("\n".join(lines) + "\n")
    print(
        f"\n{report['result']}: {sum(r['status'] == 'PASS' for r in results)} passed, "
        f"{sum(r['status'] == 'FAIL' for r in results)} failed, {sum(r['status'] == 'SKIP' for r in results)} skipped "
        f"-> ci/{stem}.md"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
