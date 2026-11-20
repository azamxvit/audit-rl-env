"""Learned auditor: public-only features, budget, determinism of training, and a measured improvement."""

import ast
import json
from pathlib import Path

from audit_env.env import AuditEnv
from audit_env.grader import Grader
from audit_env.learning import DEFAULT_PATH, FORMAT, Detector, extract, fit, labels
from audit_env.learning.features import FEATURES, HEADS
from audit_env.policies import LearnedAuditorPolicy, SimpleReconcilerPolicy
from audit_env.policies.learned import decide
from audit_env.trajectories import run_episode
from conftest import ROOT, cfg, episode

LEARNING = ROOT / "src" / "audit_env" / "learning"
FORBIDDEN = {"grader", "truth", "provenance", "generator", "checker", "transform", "oracle"}


def _imports(path: Path) -> set:
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[-1])
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name.split(".")[-1] for a in node.names)
    return names


def test_inference_code_never_imports_grader_side_modules():
    for path in [*LEARNING.glob("*.py"), ROOT / "src" / "audit_env" / "policies" / "learned.py"]:
        assert not (_imports(path) & FORBIDDEN), path.name


def test_features_from_tool_reads_equal_features_from_files():
    ep = episode(1009, "train/large.json")  # ~1500-2000 ledger rows: the largest budget case
    env = AuditEnv("train")
    pol = LearnedAuditorPolicy()
    res = run_episode(env, pol, seed=1009, config=cfg("train/large.json"))
    assert res["terminated"] and not res["truncated"] and res["steps"] <= 100
    seen, direct = extract(pol.public_view()), extract(ep.public)
    assert [(c.key, c.x, c.findings) for c in seen] == [(c.key, c.x, c.findings) for c in direct]


def test_shipped_model_is_well_formed_and_trained_on_unpublished_seeds():
    det = Detector.load()
    p = json.loads(DEFAULT_PATH.read_text())
    assert p["format"] == FORMAT and 0 < det.threshold < 1
    for kind, heads in HEADS.items():
        assert p["kinds"][kind]["features"] == list(FEATURES[kind])
        assert set(p["kinds"][kind]["heads"]) == set(heads)
    lo, hi = p["training"]["train_seeds"]
    published = {
        e["seed"] for split in ("train", "dev") for e in json.loads((ROOT / "configs/splits.json").read_text())[split]
    }
    assert not any(lo <= s <= hi for s in published)
    assert all(c.startswith("train/") for c in p["training"]["configs"])


def test_training_is_deterministic():
    samples = {}
    for seed in (11, 12):
        ep = episode(seed, "train/mixed.json")
        cands = extract(ep.public)
        for c, y in zip(cands, labels(cands, ep.truth), strict=True):
            samples.setdefault(c.kind, []).append((c.x, y))
    assert fit(samples, seed=3, epochs=3) == fit(samples, seed=3, epochs=3)


def test_learned_beats_scripted_reconciler_on_held_out_seeds():
    total_learned = total_simple = 0.0
    env = AuditEnv("train")
    for seed in range(7_000_000, 7_000_006):
        for name in ("dev/mixed.json", "dev/interacting.json"):
            total_learned += run_episode(env, LearnedAuditorPolicy(), seed=seed, config=cfg(name))["return"]
            total_simple += run_episode(env, SimpleReconcilerPolicy(), seed=seed, config=cfg(name))["return"]
    assert total_learned / 12 > 0.85 and total_learned > total_simple + 3


def test_silent_on_clean_books_and_flag_all_style_threshold_is_punished():
    ep = episode(1003, "train/clean.json")
    det = Detector.load()
    base = ep.public["manifest"]["base_currency"]
    quiet = decide(det, extract(ep.public), det.threshold, base)
    assert quiet == []
    loud = decide(det, extract(ep.public), 0.0, base)  # threshold 0 = flag every candidate
    sub = {"episode_id": ep.episode_id, "findings": loud}
    assert loud and Grader(ep.public, ep.truth).grade(sub, 0, "submit")["reward"] == -1.0
