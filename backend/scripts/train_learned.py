"""Train the learned auditor's detector (offline, CPU, stdlib only, deterministic).

Data: episodes generated from the *train* configs only, on seeds that no published
or evaluation episode uses (train: 5_000_000+, threshold validation: 5_100_000+).
Labels come from the open train truth - this is the environment's training signal.
The decision threshold is picked by the environment's own terminal reward
(mean ``clip(2F1 - 1 - 0.002 * steps)`` over the validation episodes, graded by
``Grader``), so the shipped model optimises what the env rewards.

Writes src/audit_env/learning/learned_auditor.json. Usage:
    PYTHONPATH=src python3 scripts/train_learned.py [--per-config 30] [--check]
--check retrains and fails if the result differs from the committed model.
"""

import argparse
import math
import statistics
import sys

from _common import CONFIGS
from audit_env import ENV_VERSION
from audit_env.generator import generate_episode, load_config
from audit_env.grader import Grader
from audit_env.learning import DEFAULT_PATH, FORMAT, Detector, coverage, extract, fit, labels
from audit_env.policies.learned import decide

TRAIN_SEED, VALID_SEED = 5_000_000, 5_100_000
THRESHOLDS = [round(0.1 + 0.05 * i, 2) for i in range(17)]  # 0.10 .. 0.90


def train_configs() -> list:
    return sorted(p for p in (CONFIGS / "train").glob("*.json"))


def episodes(seed0: int, per_config: int):
    for path in train_configs():
        cfg = load_config(path)
        for k in range(per_config):
            yield path, generate_episode(seed0 + k, cfg)


def read_steps(public: dict) -> int:
    """Steps the policy spends: one page of <=50 per table, plus submit."""
    return sum(math.ceil(len(public[t]) / 50) or 1 for t in ("payments", "invoices", "fx", "ledger")) + 1


def build(per_config: int, valid_per_config: int) -> dict:
    samples: dict = {}
    covers = []
    n_train = 0
    for _path, ep in episodes(TRAIN_SEED, per_config):
        n_train += 1
        cands = extract(ep.public)
        covers.append(coverage(cands, ep.truth))
        for c, y in zip(cands, labels(cands, ep.truth), strict=True):
            samples.setdefault(c.kind, []).append((c.x, y))
    kinds = fit(samples, seed=0)
    params = {"format": FORMAT, "env_version": ENV_VERSION, "threshold": 0.5, "kinds": kinds}
    det = Detector(params)

    valid = [(ep, extract(ep.public)) for _p, ep in episodes(VALID_SEED, valid_per_config)]
    curve = {}
    for t in THRESHOLDS:
        rewards = []
        for ep, cands in valid:
            sub = {
                "episode_id": ep.episode_id,
                "findings": decide(det, cands, t, ep.public["manifest"]["base_currency"]),
            }
            rewards.append(Grader(ep.public, ep.truth).grade(sub, read_steps(ep.public) - 1, "submit")["reward"])
        curve[t] = round(statistics.mean(rewards), 4)
    best = max(THRESHOLDS, key=lambda t: (curve[t], -abs(t - 0.5)))
    params["threshold"] = best
    positives = {
        f"{kind}.{head}": int(sum(y[head] for _x, y in rows))
        for kind, rows in sorted(samples.items())
        for head in rows[0][1]
    }
    params["training"] = {
        "script": "scripts/train_learned.py",
        "configs": [f"train/{p.name}:{load_config(p)['config_id']}" for p in train_configs()],
        "train_seeds": [TRAIN_SEED, TRAIN_SEED + per_config - 1],
        "validation_seeds": [VALID_SEED, VALID_SEED + valid_per_config - 1],
        "train_episodes": n_train,
        "validation_episodes": len(valid),
        "candidates": {k: len(v) for k, v in sorted(samples.items())},
        "positives": positives,
        "candidate_coverage_of_truth": round(statistics.mean(covers), 4),
        "optimizer": "SGD, lr 0.3/(1+epoch), 25 epochs, L2 1e-4, shuffle random.Random(0)",
        "threshold_by_mean_terminal_reward": {str(t): r for t, r in curve.items()},
    }
    return params


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-config", type=int, default=30)
    ap.add_argument("--valid-per-config", type=int, default=10)
    ap.add_argument("--check", action="store_true", help="retrain and compare with the committed model")
    a = ap.parse_args()
    det = Detector(build(a.per_config, a.valid_per_config))
    text = det.dumps()
    if a.check:
        same = DEFAULT_PATH.exists() and DEFAULT_PATH.read_text() == text
        print("learned model reproducible:", "OK" if same else "DIFFERS")
        return 0 if same else 1
    DEFAULT_PATH.write_text(text)
    tr = det.params["training"]
    print(f"wrote {DEFAULT_PATH.name}: {tr['train_episodes']} train episodes, candidates {tr['candidates']}")
    print(f"coverage of truth by candidates: {tr['candidate_coverage_of_truth']}")
    print(
        f"threshold {det.threshold} (mean validation reward {tr['threshold_by_mean_terminal_reward'][str(det.threshold)]})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
