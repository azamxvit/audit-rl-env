"""Paired checks: permuting order and renaming IDs preserves oracle answer, audit result and rewards."""

import pytest

from audit_env.checker import audit, verify_episode
from audit_env.env import AuditEnv
from audit_env.generator import Episode, write_episode
from audit_env.grader import Grader
from audit_env.policies import LearnedAuditorPolicy, OraclePolicy, SimpleReconcilerPolicy
from audit_env.trajectories import run_episode
from audit_env.transform import map_findings, transform_episode
from conftest import episode

PAIRS = [(s, None) for s in range(6)] + [
    (1005, "train/interacting.json"),
    (1003, "train/clean.json"),
    (2007, "dev/alloc_cutoff.json"),
    (2005, "dev/interacting.json"),
]


def _submission(truth):
    return {
        "episode_id": truth["episode_id"],
        "findings": [
            {
                "type": i["type"],
                "affected_ids": i["affected_ids"],
                "claimed_amount_minor": i["expected_amount_minor"],
                "currency": i["currency"],
                "evidence_ids": i["evidence_sets"][0],
                "explanation": "",
            }
            for i in truth["issues"]
        ],
    }


@pytest.mark.parametrize("seed,name", PAIRS)
def test_transformed_episode_is_valid_and_equivalent(seed, name):
    ep = episode(seed, name)
    pub2, tr2, mapping = transform_episode(ep.public, ep.truth, seed=("pair", seed))
    assert set(mapping.values()).isdisjoint(mapping.keys()) or not mapping
    assert verify_episode(pub2, tr2) == []
    # audit result maps 1:1
    a1 = sorted((f["type"], sorted(mapping[x] for x in f["affected_ids"]), f["amount_minor"]) for f in audit(ep.public))
    a2 = sorted((f["type"], f["affected_ids"], f["amount_minor"]) for f in audit(pub2))
    assert a1 == a2
    # the original oracle answer, renamed, gets the same reward on the transformed episode
    sub = _submission(ep.truth)
    r1 = Grader(ep.public, ep.truth).grade(sub, 0, "submit")
    r2 = Grader(pub2, tr2).grade(map_findings(sub, mapping), 0, "submit")
    assert r1["reward"] == r2["reward"] == 1.0
    # a partial answer too (rewards are a function of the answer up to renaming)
    half = {"episode_id": sub["episode_id"], "findings": sub["findings"][: len(sub["findings"]) // 2]}
    assert (
        Grader(ep.public, ep.truth).grade(half, 7, "submit")["reward"]
        == Grader(pub2, tr2).grade(map_findings(half, mapping), 7, "submit")["reward"]
    )


@pytest.mark.parametrize("seed,name", PAIRS[:4])
def test_policies_through_env_on_transformed_files(tmp_path, seed, name):
    ep = episode(seed, name)
    pub2, tr2, mapping = transform_episode(ep.public, ep.truth, seed=("pair", seed))
    write_episode(ep, tmp_path / "a")
    write_episode(Episode(pub2, tr2, ep.provenance, {}), tmp_path / "b")
    env = AuditEnv("train")
    ra = run_episode(env, OraclePolicy(ep.truth), config={"episode_dir": str(tmp_path / "a")})
    rb = run_episode(env, OraclePolicy(tr2), config={"episode_dir": str(tmp_path / "b")})
    assert ra["return"] == rb["return"] == 1.0
    sa = run_episode(env, SimpleReconcilerPolicy(), config={"episode_dir": str(tmp_path / "a")})
    sb = run_episode(env, SimpleReconcilerPolicy(), config={"episode_dir": str(tmp_path / "b")})
    assert sa["return"] == sb["return"] and sa["info"]["metrics"] == sb["info"]["metrics"]
    la = run_episode(env, LearnedAuditorPolicy(), config={"episode_dir": str(tmp_path / "a")})
    lb = run_episode(env, LearnedAuditorPolicy(), config={"episode_dir": str(tmp_path / "b")})
    assert la["return"] == lb["return"] and la["info"]["metrics"] == lb["info"]["metrics"]


def test_permutation_changes_first_page():
    ep = episode(0)
    pub2, _, _ = transform_episode(ep.public, ep.truth, seed="p", rename=False)
    assert [r["row_id"] for r in pub2["ledger"][:50]] != [r["row_id"] for r in ep.public["ledger"][:50]]
    assert sorted(r["row_id"] for r in pub2["ledger"]) == sorted(r["row_id"] for r in ep.public["ledger"])


def _opaque(public, truth, style):
    """Rename every id into a foreign format with no prefix, the way an outside evaluator might."""
    import hashlib

    from audit_env.transform import _collect_ids

    def new(i):
        h = hashlib.sha256(i.encode()).hexdigest()
        return {
            "hex": h[:20],
            "num": str(int(h[:12], 16)),
            "uuid": f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}",
        }[style]

    mapping = {i: new(i) for i in _collect_ids(public)}
    assert len(set(mapping.values())) == len(mapping)

    def walk(x):
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return mapping.get(x, x) if isinstance(x, str) else x

    return walk(public), walk(truth)


@pytest.mark.parametrize("style", ["hex", "num", "uuid"])
@pytest.mark.parametrize("seed,name", [(9_000_001, "dev/mixed.json"), (9_000_002, "dev/interacting.json")])
def test_foreign_id_formats_and_permutation_keep_validity_and_rewards(tmp_path, seed, name, style):
    ep = episode(seed, name)
    pub2, tr2 = _opaque(ep.public, ep.truth, style)
    pub2, tr2, _ = transform_episode(pub2, tr2, seed=("opaque", seed), rename=False)  # and shuffle rows
    assert verify_episode(pub2, tr2) == []
    write_episode(ep, tmp_path / "a")
    write_episode(Episode(pub2, tr2, ep.provenance, {}), tmp_path / "b")
    env = AuditEnv("train")
    for make in (lambda t: OraclePolicy(t), lambda t: SimpleReconcilerPolicy(), lambda t: LearnedAuditorPolicy()):
        ra = run_episode(env, make(ep.truth), config={"episode_dir": str(tmp_path / "a")})
        rb = run_episode(env, make(tr2), config={"episode_dir": str(tmp_path / "b")})
        assert ra["return"] == rb["return"] and ra["info"]["metrics"] == rb["info"]["metrics"]
