import json
from functools import lru_cache
from pathlib import Path

import pytest

from audit_env.generator import generate_episode, load_config

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "configs"


def cfg(name: str) -> dict:
    return load_config(CONFIGS / name)


@lru_cache(maxsize=None)
def _episode(seed, name):
    return generate_episode(seed, cfg(name) if name else None)


def episode(seed, name=None):
    return _episode(seed, name)


def first_episode(pred, name=None, seeds=None):
    for s in range(500) if seeds is None else seeds:
        ep = episode(s, name)
        if pred(ep):
            return s, ep
    raise AssertionError("no episode satisfies predicate")


@pytest.fixture(scope="session")
def splits():
    return json.loads((CONFIGS / "splits.json").read_text())
