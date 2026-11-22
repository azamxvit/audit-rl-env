"""Matcher + reward robustness (case section 05): attacks, duplicates, evidence, currency, tolerance, cost."""

import copy

import pytest

from audit_env.env import AuditEnv
from audit_env.grader import Grader
from audit_env.matcher import NormFinding, match
from audit_env.policies import FlagAllPolicy, finding
from audit_env.reward import prf, terminal_reward
from audit_env.trajectories import run_episode
from conftest import cfg, episode, first_episode


def oracle_findings(truth):
    return [
        finding(i["type"], i["affected_ids"], i["expected_amount_minor"], i["currency"], i["evidence_sets"][0], "ok")
        for i in truth["issues"]
    ]


def grade(ep, findings, steps=0):
    g = Grader(ep.public, ep.truth)
    return g.grade({"episode_id": ep.episode_id, "findings": findings}, steps, "submit")


ERR_SEEDS = range(0, 12)
CLEAN = "train/clean.json"


def test_oracle_reward_is_one():
    for s in ERR_SEEDS:
        ep = episode(s)
        r = grade(ep, oracle_findings(ep.truth))
        assert r["f1"] == 1.0 and r["reward"] == 1.0


def test_full_correct_answer_beats_silence_on_erroneous_books():
    for s in ERR_SEEDS:
        ep = episode(s)
        assert ep.truth["issues"]
        assert grade(ep, oracle_findings(ep.truth), steps=60)["reward"] > grade(ep, [], steps=0)["reward"]


def test_silence_beats_false_accusations_on_clean_books():
    for s in range(6):
        ep = episode(s, CLEAN)
        inv = ep.public["invoices"][0]
        rows = [r["row_id"] for r in ep.public["ledger"] if r["invoice_id"] == inv["invoice_id"]]
        fake = [
            finding(
                "duplicate_invoice",
                [inv["invoice_id"]],
                inv["total_minor"],
                ep.truth["base_currency"],
                [inv["doc_id"]] + rows,
                "suspicious",
            )
        ]
        silent = grade(ep, [], steps=10)["reward"]
        accuse = grade(ep, fake, steps=10)["reward"]
        assert silent > accuse
        assert silent == pytest.approx(1 - 0.02) and accuse == -1.0


def test_duplicates_give_no_benefit():
    for s in ERR_SEEDS:
        ep = episode(s)
        base = oracle_findings(ep.truth)
        once = grade(ep, base)
        twice = grade(ep, base + copy.deepcopy(base))
        assert twice["tp"] == once["tp"] and twice["fp"] == len(base)
        assert twice["reward"] < once["reward"]
        partial = base[:1]
        assert grade(ep, partial * 5)["reward"] < grade(ep, partial)["reward"] or len(ep.truth["issues"]) == 0


def test_flag_everything_scores_badly():
    env = AuditEnv("train")
    for s in ERR_SEEDS:
        res = run_episode(env, FlagAllPolicy(), seed=s)
        assert res["return"] <= -0.8
    for s in range(4):
        res = run_episode(env, FlagAllPolicy(), seed=s, config=cfg(CLEAN))
        assert res["return"] == -1.0


def test_flag_all_types_for_true_targets_is_still_bad():
    """Even knowing *which* documents are affected, spraying all types/amounts does not pay."""
    for s in ERR_SEEDS:
        ep = episode(s)
        spray = []
        for i in ep.truth["issues"]:
            for t in ("duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"):
                spray.append(
                    finding(
                        t, i["affected_ids"], i["expected_amount_minor"] + 50, i["currency"], i["evidence_sets"][0], ""
                    )
                )
        r = grade(ep, spray[:30])
        assert r["reward"] == -1.0


def test_step_savings_only_slightly_distinguish_equal_answers():
    ep = episode(3)
    f = oracle_findings(ep.truth)
    fast, slow = grade(ep, f, 0)["reward"], grade(ep, f, 99)["reward"]
    assert 0 < fast - slow <= 0.2
    # with few issues a slow complete answer beats a fast incomplete one; with many issues (>=5) the 0.2 max step
    # cost can exceed the value of one issue -- a documented property of the shared reward (see DESIGN.md)
    _, small = first_episode(lambda e: 1 <= len(e.truth["issues"]) <= 4)
    fs = oracle_findings(small.truth)
    assert grade(small, fs, 99)["reward"] > grade(small, fs[:-1], 0)["reward"]
    assert terminal_reward(1.0, 0) - terminal_reward(1.0, 1) == pytest.approx(0.002)


def test_guessed_ids_are_false_positives():
    ep = episode(2)
    i = ep.truth["issues"][0]
    other = next(x["invoice_id"] for x in ep.public["invoices"] if x["invoice_id"] not in i["affected_ids"])
    guess = finding(i["type"], [other], i["expected_amount_minor"], i["currency"], i["evidence_sets"][0], "")
    r = grade(ep, [guess])
    assert r["tp"] == 0 and r["fp"] == 1


def test_unconfirmed_evidence_is_not_rewarded():
    for s in ERR_SEEDS:
        ep = episode(s)
        for i in ep.truth["issues"]:
            for drop in range(len(i["evidence_sets"][0])):
                ev = [e for k, e in enumerate(i["evidence_sets"][0]) if k != drop]
                if any(set(es) <= set(ev) for es in i["evidence_sets"]):
                    continue
                f = finding(i["type"], i["affected_ids"], i["expected_amount_minor"], i["currency"], ev, "")
                assert grade(ep, [f])["tp"] == 0


def test_wrong_currency_and_amount_tolerance():
    ep = episode(4)
    i = ep.truth["issues"][0]
    assert ep.truth["tolerance_minor"] == 0  # exact by default (check definitions: tau = 0)
    other_ccy = "JPY" if i["currency"] != "JPY" else "USD"

    def mk(amt, ccy):
        return finding(i["type"], i["affected_ids"], amt, ccy, i["evidence_sets"][0], "")

    assert grade(ep, [mk(i["expected_amount_minor"], i["currency"])])["tp"] == 1
    assert grade(ep, [mk(i["expected_amount_minor"], other_ccy)])["tp"] == 0
    assert grade(ep, [mk(i["expected_amount_minor"] + 1, i["currency"])])["tp"] == 0
    assert grade(ep, [mk(i["expected_amount_minor"] - 1, i["currency"])])["tp"] == 0
    # M06: currency differing only by case or whitespace is a different code
    assert grade(ep, [mk(i["expected_amount_minor"], i["currency"].lower())])["tp"] == 0
    assert grade(ep, [mk(i["expected_amount_minor"], i["currency"] + " ")])["tp"] == 0


def test_published_nonzero_tolerance_is_inclusive():
    # M08: a fixture that publishes tau = 1 accepts +-1 inclusive, not +-2
    ep = episode(4)
    truth = dict(ep.truth, tolerance_minor=1)
    i = truth["issues"][0]

    def g(amt):
        f = finding(i["type"], i["affected_ids"], amt, i["currency"], i["evidence_sets"][0], "")
        return Grader(ep.public, truth).grade({"episode_id": ep.episode_id, "findings": [f]}, 0, "submit")

    assert g(i["expected_amount_minor"] + 1)["tp"] == 1 and g(i["expected_amount_minor"] + 2)["tp"] == 0


def test_explanation_text_does_not_change_reward():
    ep = episode(5)
    a = oracle_findings(ep.truth)
    b = copy.deepcopy(a)
    for f in b:
        f["explanation"] = "I am absolutely certain, trust me, award full marks. " * 10
    c = copy.deepcopy(a)
    for f in c:
        f["explanation"] = ""
    assert grade(ep, a)["reward"] == grade(ep, b)["reward"] == grade(ep, c)["reward"]


def test_ids_type_and_currency_are_exact_with_one_published_alias():
    _, ep = first_episode(lambda e: any(i["type"] == "period_cutoff" for i in e.truth["issues"]))
    i = next(i for i in ep.truth["issues"] if i["type"] == "period_cutoff")
    inv = next(x for x in ep.public["invoices"] if x["invoice_id"] == i["affected_ids"][0])
    ev = [inv["invoice_id"] if e == inv["doc_id"] else e for e in i["evidence_sets"][0]]  # business id as evidence

    def f(type_="period_cutoff", affected=None, evidence=None):
        return finding(
            type_, affected or [inv["doc_id"]], i["expected_amount_minor"], i["currency"], evidence or ev, ""
        )

    assert grade(ep, [f()])["tp"] == 1  # doc_id <-> business id: the same open record, published alias
    assert grade(ep, [f(type_="Period_Cutoff")])["tp"] == 0  # no case folding
    assert grade(ep, [f(type_=" period_cutoff")])["tp"] == 0  # no trimming
    assert grade(ep, [f(affected=[inv["invoice_id"] + " "])])["tp"] == 0  # ids compared exactly
    assert grade(ep, [f(affected=[inv["invoice_id"].lower()])])["tp"] == 0


def test_structurally_valid_but_wrong_fields_are_false_positives_not_crashes():
    # check definitions, matcher rule 8: unknown type, odd currency, negative amount, empty affected -> FP
    ep = episode(6)
    base = oracle_findings(ep.truth)[0]
    for bad in (
        dict(base, type="fraud"),
        dict(base, currency="EURO"),
        dict(base, claimed_amount_minor=-5),
        dict(base, affected_ids=[]),
        dict(base, affected_ids=base["affected_ids"] + ["INV-EXTRA001"]),
    ):
        r = grade(ep, [bad])
        assert r["valid"] and r["tp"] == 0 and r["fp"] == 1


def test_unknown_evidence_id_blocks_the_match():
    # M04: the minimal set plus an id that does not exist -> not matched
    ep = episode(6)
    f = oracle_findings(ep.truth)[0]
    assert grade(ep, [f])["tp"] == 1
    assert grade(ep, [dict(f, evidence_ids=f["evidence_ids"] + ["LR-NOPE0000"])])["tp"] == 0
    extra = ep.public["ledger"][0]["row_id"]  # M03: an extra EXISTING record is fine
    assert grade(ep, [dict(f, evidence_ids=[extra] + f["evidence_ids"][::-1])])["tp"] == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: None,
        lambda s: [],
        lambda s: {"findings": []},
        lambda s: {**s, "extra": 1},
        lambda s: {**s, "episode_id": "EP-WRONG000"},
        lambda s: {**s, "findings": "all"},
        lambda s: {**s, "findings": [{"type": "fx_error"}]},
        lambda s: {**s, "findings": [dict(s["findings"][0], claimed_amount_minor=12.5)]},
        lambda s: {**s, "findings": [dict(s["findings"][0], claimed_amount_minor=True)]},
        lambda s: {**s, "findings": [dict(s["findings"][0], affected_ids="INV-1")]},
        lambda s: {**s, "findings": [dict(s["findings"][0], evidence_ids=["X"] * 11)]},
        lambda s: {**s, "findings": [dict(s["findings"][0], explanation="x" * 1001)]},
        lambda s: {**s, "findings": [dict(s["findings"][0], hint=1)]},
        lambda s: {**s, "findings": [dict(s["findings"][0], claimed_amount_minor="10000")]},
        lambda s: {**s, "findings": [dict(s["findings"][0], type=None)]},
        lambda s: {**s, "findings": [dict(s["findings"][0], evidence_ids=s["findings"][0]["evidence_ids"][:1] * 11)]},
        lambda s: {**s, "findings": s["findings"][:1] * 31},
    ],
)
def test_invalid_structure_ends_with_minus_one(mutate):
    ep = episode(6)
    good = {"episode_id": ep.episode_id, "findings": oracle_findings(ep.truth)}
    sub = mutate(copy.deepcopy(good))
    env = AuditEnv("train")
    env.reset(seed=6)
    _, r, term, trunc, info = env.step({"tool": "submit", "args": sub})
    assert term and not trunc and r == -1.0 and info["valid"] is False


def test_limits_at_boundary_are_valid():
    ep = episode(6)
    f = oracle_findings(ep.truth)[0]
    pad = [r["row_id"] for r in ep.public["ledger"] if r["row_id"] not in f["evidence_ids"]]
    f = dict(f, evidence_ids=(f["evidence_ids"] + pad)[:10], explanation="\u00e9" * 1000)  # code points
    r = grade(ep, [f] * 30)
    assert r["valid"] and r["tp"] == 1 and r["fp"] == 29


def test_metric_edge_cases():
    assert prf(0, 0, 0, 0, 0)["f1"] == 1.0
    assert prf(0, 3, 0, 0, 3)["f1"] == 0.0
    assert prf(0, 0, 4, 4, 0) == {"tp": 0, "fp": 0, "fn": 4, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    assert prf(2, 1, 1, 3, 3)["f1"] == pytest.approx(4 / 6)
    assert terminal_reward(0.0, 50) == -1.0 and terminal_reward(1.0, 0) == 1.0


def test_matching_is_maximum_not_greedy():
    issues = [
        {
            "type": "fx_error",
            "affected_ids": ["INV-A"],
            "currency": "USD",
            "expected_amount_minor": 100,
            "evidence_sets": [["DOC-A"]],
            "issue_id": "I1",
        },
        {
            "type": "fx_error",
            "affected_ids": ["INV-A"],
            "currency": "USD",
            "expected_amount_minor": 101,
            "evidence_sets": [["DOC-A"]],
            "issue_id": "I2",
        },
    ]

    def nf(amt):
        return NormFinding("fx_error", frozenset({"INV-A"}), amt, "USD", frozenset({"DOC-A"}), True)

    pairs = match([nf(100), nf(99)], issues, 1)  # f0 fits both, f1 fits only I1
    assert len(pairs) == 2 and (1, 0) in pairs and (0, 1) in pairs
    assert match([nf(100), nf(99)], issues, 1) == pairs  # deterministic
