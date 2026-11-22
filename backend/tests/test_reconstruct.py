"""Block 2, condition 1: the pre-injection books follow from the files alone (public + provenance)."""

import random
import sys

import pytest

from audit_env.checker import audit, check_invariants
from audit_env.generator import generate_episode, load_config
from audit_env.reconstruct import clean_books
from audit_env.util import dumps
from conftest import ROOT

CONFIGS = sorted(p for p in (ROOT / "configs").glob("*/*.json") if p.name != "splits.json")


def _same(a, b) -> bool:
    return sorted(map(dumps, a)) == sorted(map(dumps, b))


@pytest.mark.parametrize("path", CONFIGS, ids=[f"{p.parent.name}/{p.stem}" for p in CONFIGS])
def test_undoing_recorded_changes_restores_the_clean_books(path):
    for seed in (1, 2):
        ep = generate_episode(seed, load_config(path))
        rebuilt = clean_books(ep.public, ep.provenance)
        assert _same(rebuilt["ledger"], ep.clean_public["ledger"])
        for t in ("invoices", "payments", "fx"):
            assert _same(rebuilt[t], ep.clean_public[t])
        assert check_invariants(rebuilt) == [] and audit(rebuilt) == []


def test_random_parameter_combinations():
    sys.path.insert(0, str(ROOT / "scripts"))
    import fuzz_generator

    r = random.Random(77)
    for i in range(30):
        ep = generate_episode(r.randint(0, 10**9), fuzz_generator.random_config(r, i))
        assert _same(clean_books(ep.public, ep.provenance)["ledger"], ep.clean_public["ledger"])
