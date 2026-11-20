"""Single verification command (used by `make verify` and the Docker image). Offline, stdlib + pytest.

1. generate the open episodes from versioned configs   (scripts/generate_episodes.py)
2. run the test-suite                                    (pytest)
3. independent data verification + paired checks         (scripts/verify.py)
4. run the 4 baseline policies (+ the learned auditor), write trajectories+report (scripts/run_baselines.py)
5. held-out evaluation and learning curve of the learned auditor (scripts/eval_learned.py)
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("generate episodes", [sys.executable, "scripts/generate_episodes.py"]),
    ("tests", [sys.executable, "-m", "pytest", "-q"]),
    ("data verification", [sys.executable, "scripts/verify.py"]),
    ("baselines", [sys.executable, "scripts/run_baselines.py"]),
    ("learned auditor eval", [sys.executable, "scripts/eval_learned.py"]),
]


def main() -> int:
    for name, cmd in STEPS:
        t0 = time.perf_counter()
        print(f"==> {name}", flush=True)
        rc = subprocess.call(cmd, cwd=ROOT)
        print(f"<== {name}: {'OK' if rc == 0 else 'FAILED'} ({time.perf_counter() - t0:.1f}s)", flush=True)
        if rc != 0:
            return rc
    print("verify: OK — trajectories in runs/<split>/<policy>/trajectories.jsonl, report in runs/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
