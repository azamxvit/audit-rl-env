"""Episode runner and trajectories.jsonl writer.

One JSON line per transition: episode_id, step, action, observation, reward, terminated, truncated.
Step 0 is the reset observation (action = null). Observations are exactly what the policy saw, so they
never contain truth/provenance (eval-mode rewards are 0 in the file; scores live in the grader log).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


class TrajectoryWriter:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8")

    def write(self, record: dict) -> None:
        self._fh.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")

    def close(self) -> None:
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def run_episode(
    env,
    policy,
    seed=None,
    config: Optional[dict] = None,
    writer: Optional[TrajectoryWriter] = None,
    max_actions: int = 10_000,
) -> dict:
    t0 = time.perf_counter()
    obs, info = env.reset(seed=seed, config=config)
    episode_id = obs["manifest"]["episode_id"]
    policy.reset(obs)
    if writer:
        writer.write(
            {
                "episode_id": episode_id,
                "step": 0,
                "action": None,
                "observation": obs,
                "reward": 0.0,
                "terminated": False,
                "truncated": False,
            }
        )
    total, step = 0.0, 0
    terminated = truncated = False
    last_info: dict = {}
    while not (terminated or truncated) and step < max_actions:
        action = policy.act(obs)
        obs, reward, terminated, truncated, last_info = env.step(action)
        step += 1
        total += reward
        if writer:
            writer.write(
                {
                    "episode_id": episode_id,
                    "step": step,
                    "action": action,
                    "observation": obs,
                    "reward": reward,
                    "terminated": terminated,
                    "truncated": truncated,
                }
            )
    return {
        "episode_id": episode_id,
        "policy": getattr(policy, "name", type(policy).__name__),
        "steps": step,
        "return": total,
        "terminated": terminated,
        "truncated": truncated,
        "info": last_info,
        "seconds": time.perf_counter() - t0,
    }
