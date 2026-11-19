"""Shared helpers for scripts (run from repo root; src/ is put on sys.path)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EPISODES = ROOT / "episodes"
CONFIGS = ROOT / "configs"
RUNS = ROOT / "runs"


def splits() -> dict:
    return json.loads((CONFIGS / "splits.json").read_text())


def episode_dirs(split: str) -> list:
    index = json.loads((EPISODES / "index.json").read_text())
    return [(EPISODES / e["path"], e) for e in index["episodes"] if e["split"] == split]
