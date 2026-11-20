"""Generator robustness on unseen seeds and parameter combinations (the hidden-evaluation setting).

Regression cases are configs the fuzzer (scripts/fuzz_generator.py) once broke; each must now
generate a valid episode. A small random sweep guards against new failures.
"""

import json
import random
from pathlib import Path

import pytest

from audit_env.checker import verify_episode
from audit_env.generator import generate_episode
from conftest import ROOT, cfg

REGRESSIONS = json.loads((Path(__file__).with_name("generator_regressions.json")).read_text())


def _problems(seed, config):
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import fuzz_generator

    return fuzz_generator.check(seed, config, 0)


@pytest.mark.parametrize("name", sorted(REGRESSIONS))
def test_former_generator_failures_now_produce_valid_episodes(name):
    case = REGRESSIONS[name]
    assert _problems(case["seed"], case["config"]) == []


def test_coincidental_identical_invoices_are_not_generated():
    # dev/interacting seed 6_000_014 used to contain two same-customer invoices with identical
    # line items in the CLEAN books, which an auditor (and the checker) rightly flags as a duplicate
    ep = generate_episode(6_000_014, cfg("dev/interacting.json"))
    assert verify_episode(ep.public, ep.truth, ep.clean_public) == []


def test_single_currency_company_when_pool_has_only_the_base():
    ep = generate_episode(5, {"base_currencies": ["CHF"], "foreign_currencies": ["CHF"]})
    assert {i["currency"] for i in ep.public["invoices"]} == {"CHF"}
    assert ep.public["fx"] == [] and all(i["type"] != "fx_error" for i in ep.truth["issues"])


def test_random_parameter_sweep():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import fuzz_generator

    r = random.Random(20261120)
    for i in range(25):
        config, seed = fuzz_generator.random_config(r, i), r.randint(0, 10**9)
        assert fuzz_generator.check(seed, config, i) == [], (seed, config)
