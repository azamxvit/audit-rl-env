"""Generator: determinism, accounting invariants, truth == independent audit, evidence sufficiency."""

import collections

import pytest

from audit_env.checker import audit, check_invariants, verify_episode
from audit_env.generator import load_private, load_public, public_files, write_episode
from audit_env.util import sha256_text
from conftest import cfg, episode

CONFIG_NAMES = [
    None,
    "train/clean.json",
    "train/interacting.json",
    "train/fx_heavy.json",
    "train/small_month.json",
    "dev/mixed.json",
    "dev/interacting.json",
    "dev/alloc_cutoff.json",
]


def _hashes(ep):
    files = public_files(ep.public)
    return {k: sha256_text(v) for k, v in files.items()}


def test_same_seed_same_bytes():
    from audit_env.generator import generate_episode

    a = generate_episode(42, cfg("train/interacting.json"))
    b = generate_episode(42, cfg("train/interacting.json"))
    assert _hashes(a) == _hashes(b)
    assert a.truth == b.truth and a.provenance == b.provenance


def test_different_seeds_differ():
    assert _hashes(episode(1)) != _hashes(episode(2))


@pytest.mark.parametrize("name", CONFIG_NAMES)
def test_episodes_verify_independently(name):
    """Invariants before/after injection, clean books audit clean, audit == truth, every evidence set sufficient."""
    for seed in range(12):
        ep = episode(seed, name)
        assert verify_episode(ep.public, ep.truth, ep.clean_public) == [], (name, seed)


def test_pre_injection_invariants_hold():
    for seed in range(20):
        ep = episode(seed)
        assert check_invariants(ep.clean_public) == []
        assert audit(ep.clean_public) == []


def test_declared_discrepancy_present_after_injection():
    ep = episode(5)
    assert ep.truth["issues"]
    for issue in ep.truth["issues"]:
        assert issue["expected_amount_minor"] > ep.truth["tolerance_minor"]
        assert all(len(s) <= 10 for s in issue["evidence_sets"])


def test_clean_config_has_no_issues_but_has_distractors():
    for seed in range(10):
        ep = episode(seed, "train/clean.json")
        assert ep.truth["issues"] == []
        d = ep.provenance["distractors"]
        assert d["overpayments"] + d["unidentified_receipts"] >= 1
        assert d["next_period_documents"] >= 1


def test_all_types_and_scenarios_occur():
    types, scenarios = collections.Counter(), collections.Counter()
    for seed in range(30):
        for i in episode(seed).truth["issues"]:
            types[i["type"]] += 1
            scenarios[i["scenario"]] += 1
    assert set(types) == {"duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"}
    assert scenarios["fx_partial_boundary"] > 0 and scenarios["cutoff_fx"] > 0


def test_error_types_independently_configurable():
    zero = {t: {"count": 0} for t in ["duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"]}
    for t in zero:
        conf = {
            "errors": {**zero, t: {"count": 2}},
            "scenarios": {"fx_partial_boundary": {"count": 0}, "cutoff_fx": {"count": 0}},
        }
        from audit_env.generator import generate_episode

        ep = generate_episode(3, conf)
        assert {i["type"] for i in ep.truth["issues"]} == {t}


def test_interacting_scenarios_share_documents():
    ep = episode(1005, "train/interacting.json")
    by_scen = collections.defaultdict(list)
    for i in ep.truth["issues"]:
        if i["scenario"]:
            by_scen[i["scenario"]].append(i)
    assert set(by_scen) == {"fx_partial_boundary", "cutoff_fx"}
    fxp = by_scen["fx_partial_boundary"]
    assert {i["type"] for i in fxp} == {"fx_error", "payment_allocation"}
    pay_ids = [set(i["affected_ids"]) for i in fxp]
    assert pay_ids[0] & pay_ids[1]
    cut = by_scen["cutoff_fx"]
    assert {i["type"] for i in cut} == {"fx_error", "period_cutoff"}
    assert cut[0]["affected_ids"] == cut[1]["affected_ids"]


def test_size_ranges(splits):
    from audit_env.generator import generate_episode

    for split in ("train", "dev"):
        for e in splits[split]:
            ep = generate_episode(e["seed"], cfg(e["config"]))
            c = ep.public["manifest"]["counts"]
            assert 200 <= c["ledger_rows"] <= 2000
            assert 20 <= c["documents"] <= 210
            assert 0 <= len(ep.truth["issues"]) <= 12


def test_money_types_and_timestamps():
    ep = episode(7)
    for r in ep.public["ledger"]:
        assert isinstance(r["debit_minor"], int) and isinstance(r["credit_minor"], int)
        assert r["timestamp"][-6] in "+-"
    for f in ep.public["fx"]:
        assert isinstance(f["rate"], str)
    for p in ep.public["payments"]:
        assert "invoice_refs" in p  # explicit null when absent


def test_write_and_reload_roundtrip(tmp_path):
    ep = episode(9)
    write_episode(ep, tmp_path / "ep")
    assert load_public(tmp_path / "ep") == ep.public
    truth, prov = load_private(tmp_path / "ep")
    assert truth == ep.truth and prov["changes"]
    assert not any((tmp_path / "ep" / "public").glob("truth*"))


def test_provenance_records_causal_changes():
    ep = episode(4)
    issue_ids = {i["issue_id"] for i in ep.truth["issues"]}
    covered = {iid for c in ep.provenance["changes"] for iid in c["issue_ids"]}
    assert covered == issue_ids
    for c in ep.provenance["changes"]:
        assert c["ledger_after"] is not None
        assert c["booking_before"] != c["booking_after"] or c["op"] == "add_document_and_booking"
