"""Published JSON Schemas (backend/schemas) describe what the environment actually emits and accepts.

Every artefact is checked against its schema: open and private episode files, configs, the
index, every observation/info the env returns (all tools, all error codes, submit, truncation,
train and eval mode), trajectories of all policies and grader-log lines. Schemas and runtime
validation must also agree: a schema-valid action/submission is accepted, a structurally
invalid one is rejected by both.
"""

import json

import pytest

from audit_env.env import AuditEnv
from audit_env.generator import load_private, load_public
from audit_env.matcher import SubmissionError, validate_submission
from audit_env.policies import (
    FlagAllPolicy,
    LearnedAuditorPolicy,
    OraclePolicy,
    RandomExplorerPolicy,
    SimpleReconcilerPolicy,
)
from audit_env.schema import Registry, SchemaError
from audit_env.store import ToolError
from audit_env.trajectories import TrajectoryWriter, run_episode
from conftest import ROOT, cfg, episode

REG = Registry()
INDEX = json.loads((ROOT / "episodes" / "index.json").read_text())
FIRST = ROOT / "episodes" / INDEX["episodes"][0]["path"]
EPISODE_ID = INDEX["episodes"][0]["episode_id"]


def ok(instance, schema_file, pointer=""):
    errs = REG.errors(instance, schema_file, pointer)
    assert errs == [], errs[:3]


# ----------------------------------------------------------------------------- the schemas themselves


def _refs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref":
                yield v
            else:
                yield from _refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _refs(v)


def test_every_ref_resolves_and_files_are_listed():
    expected = {
        "common",
        "records",
        "action",
        "submission",
        "observation",
        "trajectory",
        "truth",
        "provenance",
        "grader_result",
        "config",
        "episode_index",
    }
    assert {f.removesuffix(".schema.json") for f in REG.docs} == expected
    for name, doc in REG.docs.items():
        for ref in _refs(doc):
            REG.resolve(ref, name)


def test_validator_rejects_what_it_should():
    row = load_public(FIRST)["ledger"][0]
    ok(row, "records.schema.json", "/$defs/ledger_row")
    for broken in (
        {**row, "debit_minor": -1},
        {**row, "debit_minor": True},
        {**row, "debit_minor": 1.5},
        {**row, "currency": "usd"},
        {**row, "extra": 1},
        {k: v for k, v in row.items() if k != "entry_id"},
        {**row, "timestamp": "2025-01-01 10:00:00"},
    ):
        assert REG.errors(broken, "records.schema.json", "/$defs/ledger_row")
    with pytest.raises(SchemaError):
        REG.validate({"tool": "submit"}, "action.schema.json")


def test_unsupported_keyword_is_refused(tmp_path):
    (tmp_path / "x.schema.json").write_text(json.dumps({"$id": "x.schema.json", "format": "date"}))
    with pytest.raises(SchemaError):
        Registry(tmp_path)


# ----------------------------------------------------------------------------- files


def test_published_episode_files_configs_and_index():
    ok(INDEX, "episode_index.schema.json")
    for e in INDEX["episodes"]:
        d = ROOT / "episodes" / e["path"]
        pub = load_public(d)
        truth, prov = load_private(d)
        ok(pub["manifest"], "records.schema.json", "/$defs/manifest")
        ok(pub["policy"], "records.schema.json", "/$defs/policy")
        for table, ref in (
            ("ledger", "ledger_row"),
            ("invoices", "invoice"),
            ("payments", "payment"),
            ("fx", "fx_rate"),
        ):
            for rec in pub[table]:
                ok(rec, "records.schema.json", f"/$defs/{ref}")
        ok(truth, "truth.schema.json")
        ok(prov, "provenance.schema.json")
    for path in sorted((ROOT / "configs").glob("*/*.json")):
        ok(json.loads(path.read_text()), "config.schema.json")


def test_generated_episodes_on_unseen_seeds_conform():
    for seed, name in [(7_100_001, "train/fx_heavy.json"), (7_100_002, "dev/interacting.json"), (7_100_003, None)]:
        ep = episode(seed, name)
        ok(ep.truth, "truth.schema.json")
        ok(ep.provenance, "provenance.schema.json")
        for table, ref in (
            ("ledger", "ledger_row"),
            ("invoices", "invoice"),
            ("payments", "payment"),
            ("fx", "fx_rate"),
        ):
            for rec in ep.public[table]:
                ok(rec, "records.schema.json", f"/$defs/{ref}")


# ----------------------------------------------------------------------------- live contract


def _step(env, action):
    obs, reward, term, trunc, info = env.step(action)
    ok(obs, "observation.schema.json", "/$defs/step_observation")
    ok(reward, "observation.schema.json", "/$defs/reward")
    ok(info, "observation.schema.json", "/$defs/step_info")
    assert isinstance(term, bool) and isinstance(trunc, bool)
    return obs, reward, term, trunc, info


def test_every_tool_and_every_error_code_conforms():
    env = AuditEnv("train")
    obs, info = env.reset(config={"episode_dir": str(FIRST)})
    ok(obs, "observation.schema.json", "/$defs/reset_observation")
    ok(info, "observation.schema.json", "/$defs/reset_info")
    pub = load_public(FIRST)
    inv, pay, fx, row = pub["invoices"][0], pub["payments"][0], pub["fx"][0], pub["ledger"][0]
    page = _step(env, {"tool": "list_records", "args": {"table": "ledger", "limit": 50}})[0]
    seen = set()
    for action in [
        {"tool": "list_records", "args": {"table": "fx", "cursor": None, "limit": 3}},
        {"tool": "list_records", "args": {"table": "ledger", "cursor": page["result"]["next_cursor"]}},
        {"tool": "get_record", "args": {"table": "ledger", "id": row["row_id"]}},
        {"tool": "get_record", "args": {"table": "invoices", "id": inv["doc_id"]}},
        {"tool": "get_record", "args": {"table": "payments", "id": pay["payment_id"]}},
        {"tool": "get_record", "args": {"table": "fx", "id": fx["rate_id"]}},
        {"tool": "get_document", "args": {"doc_id": inv["doc_id"]}},
        {"tool": "get_document", "args": {"doc_id": pay["doc_id"]}},
        {"tool": "calculator", "args": {"expression": "(1234.5 * 3) / 7"}},
        {"tool": "calculator", "args": {"expression": "__import__('os')"}},
        {"tool": "calculator", "args": {"expression": "1/0"}},
        {"tool": "nope", "args": {}},
        "not an action",
        {"tool": "get_record"},
        {"tool": "get_record", "args": {"table": "ledger"}},
        {"tool": "list_records", "args": {"table": "secrets"}},
        {"tool": "list_records", "args": {"table": "ledger", "limit": 51}},
        {"tool": "list_records", "args": {"table": "ledger", "cursor": "forged"}},
        {"tool": "get_record", "args": {"table": "ledger", "id": "LR-NOPE0000"}},
        {"tool": "get_document", "args": {"doc_id": 5}},
    ]:
        obs = _step(env, action)[0]
        if not obs["ok"]:
            seen.add(obs["error"]["code"])
    _, _, term, _, info = _step(env, {"tool": "submit", "args": {"episode_id": EPISODE_ID, "findings": []}})
    assert term and info["termination"] == "submit"
    seen.add(_step(env, {"tool": "calculator", "args": {"expression": "1"}})[0]["error"]["code"])
    t = [0.0]
    env2 = AuditEnv("train", clock=lambda: t[0])
    env2.reset(config={"episode_dir": str(FIRST)})
    t[0] = 61.0
    seen.add(_step(env2, {"tool": "calculator", "args": {"expression": "1"}})[0]["error"]["code"])
    assert seen == set(ToolError.MESSAGES)  # every error code was produced and conformed


def test_step_limit_truncation_and_eval_mode(tmp_path):
    env = AuditEnv("train", max_steps=3)
    env.reset(config={"episode_dir": str(FIRST)})
    for _ in range(3):
        _, _, _, trunc, info = _step(env, {"tool": "calculator", "args": {"expression": "2"}})
    assert trunc and info["termination"] == "step_limit"
    ev = AuditEnv("eval", grader_log=tmp_path / "g.jsonl")
    try:
        obs, info = ev.reset(config={"episode_dir": str(FIRST)})
        ok(obs, "observation.schema.json", "/$defs/reset_observation")
        ok(info, "observation.schema.json", "/$defs/reset_info")
        _, reward, _, _, info = _step(ev, {"tool": "submit", "args": {"episode_id": EPISODE_ID, "findings": []}})
        assert reward == 0.0 and info == {}
    finally:
        ev.close()
    for line in (tmp_path / "g.jsonl").read_text().splitlines():
        ok(json.loads(line), "grader_result.schema.json")


@pytest.mark.parametrize(
    "make",
    [
        lambda t: RandomExplorerPolicy(seed=0),
        lambda t: SimpleReconcilerPolicy(),
        lambda t: FlagAllPolicy(),
        lambda t: OraclePolicy(t),
        lambda t: LearnedAuditorPolicy(),
    ],
    ids=["random", "reconciler", "flag_all", "oracle", "learned"],
)
def test_trajectories_of_every_policy_conform(tmp_path, make):
    truth, _ = load_private(FIRST)
    path = tmp_path / "t.jsonl"
    with TrajectoryWriter(path) as w:
        run_episode(AuditEnv("train"), make(truth), config={"episode_dir": str(FIRST)}, writer=w)
    for line in path.read_text().splitlines():
        ok(json.loads(line), "trajectory.schema.json")


# ----------------------------------------------------------------------------- schema <-> runtime agreement


def _finding(**over):
    f = {
        "type": "fx_error",
        "affected_ids": ["INV-AAAA0001"],
        "claimed_amount_minor": 1234,
        "currency": "USD",
        "evidence_ids": ["DOC-AAAA0001", "LR-AAAA0001", "FXR-AAAA0001"],
        "explanation": "",
    }
    f.update(over)
    return f


VALID_SUBMISSIONS = [
    {"episode_id": EPISODE_ID, "findings": []},
    {"episode_id": EPISODE_ID, "findings": [_finding()]},
    {"episode_id": EPISODE_ID, "findings": [_finding(evidence_ids=[], explanation="x" * 1000)] * 30},
    {"episode_id": EPISODE_ID, "findings": [_finding(currency=" usd ", affected_ids=["a"] * 10)]},
]
INVALID_SUBMISSIONS = [
    {"findings": []},
    {"episode_id": EPISODE_ID, "findings": [], "extra": 1},
    {"episode_id": EPISODE_ID, "findings": {}},
    {"episode_id": EPISODE_ID, "findings": [_finding()] * 31},
    {"episode_id": EPISODE_ID, "findings": [_finding(type="fraud")]},
    {"episode_id": EPISODE_ID, "findings": [_finding(affected_ids=[])]},
    {"episode_id": EPISODE_ID, "findings": [_finding(affected_ids=["a"] * 11)]},
    {"episode_id": EPISODE_ID, "findings": [_finding(affected_ids=["  "])]},
    {"episode_id": EPISODE_ID, "findings": [_finding(affected_ids=["x" * 65])]},
    {"episode_id": EPISODE_ID, "findings": [_finding(evidence_ids=["e"] * 11)]},
    {"episode_id": EPISODE_ID, "findings": [_finding(claimed_amount_minor=-1)]},
    {"episode_id": EPISODE_ID, "findings": [_finding(claimed_amount_minor=1.5)]},
    {"episode_id": EPISODE_ID, "findings": [_finding(claimed_amount_minor=True)]},
    {"episode_id": EPISODE_ID, "findings": [_finding(claimed_amount_minor=10**15)]},
    {"episode_id": EPISODE_ID, "findings": [_finding(currency="US")]},
    {"episode_id": EPISODE_ID, "findings": [_finding(currency="U5D")]},
    {"episode_id": EPISODE_ID, "findings": [_finding(explanation="x" * 1001)]},
    {"episode_id": EPISODE_ID, "findings": [{**_finding(), "confidence": 0.9}]},
    {"episode_id": EPISODE_ID, "findings": ["not an object"]},
]


@pytest.mark.parametrize("sub", VALID_SUBMISSIONS)
def test_schema_valid_submissions_are_accepted_by_the_matcher(sub):
    ok(sub, "submission.schema.json")
    validate_submission(sub, EPISODE_ID)


@pytest.mark.parametrize("sub", INVALID_SUBMISSIONS)
def test_structurally_invalid_submissions_are_rejected_by_both(sub):
    assert REG.errors(sub, "submission.schema.json")
    with pytest.raises(SubmissionError):
        validate_submission(sub, EPISODE_ID)


VALID_ACTIONS = [
    {"tool": "list_records", "args": {"table": "ledger"}},
    {"tool": "list_records", "args": {"table": "fx", "cursor": None, "limit": 1}},
    {"tool": "get_record", "args": {"table": "payments", "id": "PAY-NOPE0000"}},
    {"tool": "get_document", "args": {"doc_id": "DOC-NOPE0000"}},
    {"tool": "calculator", "args": {"expression": "1 + 2"}},
]
INVALID_ACTIONS = [
    ({"tool": "shell", "args": {"cmd": "ls"}}, "unknown_tool"),
    ({"tool": "list_records", "args": {"table": "ledger"}, "x": 1}, "invalid_action"),
    ({"tool": "list_records", "args": {}}, "invalid_args"),
    ({"tool": "list_records", "args": {"table": "ledger", "offset": 5}}, "invalid_args"),
    ({"tool": "list_records", "args": {"table": "users"}}, "unknown_table"),
    ({"tool": "list_records", "args": {"table": "ledger", "limit": 0}}, "invalid_limit"),
    ({"tool": "get_record", "args": {"table": "ledger", "id": 7}}, "invalid_args"),
    ({"tool": "get_document", "args": {"doc_id": "D", "table": "invoices"}}, "invalid_args"),
    ({"tool": "calculator", "args": {}}, "invalid_args"),
]


def test_actions_agree_with_the_env():
    env = AuditEnv("train")
    env.reset(config={"episode_dir": str(FIRST)})
    structural = {"unknown_tool", "invalid_action", "invalid_args", "unknown_table", "invalid_limit"}
    for action in VALID_ACTIONS:
        ok(action, "action.schema.json")
        obs = env.step(action)[0]
        assert obs["ok"] or obs["error"]["code"] not in structural, (action, obs["error"])
    for action, code in INVALID_ACTIONS:
        assert REG.errors(action, "action.schema.json"), action
        assert env.step(action)[0]["error"]["code"] == code
    ok({"tool": "submit", "args": {"episode_id": EPISODE_ID, "findings": []}}, "action.schema.json")
    ok({"tool": "submit", "args": {"findings": {"episode_id": EPISODE_ID, "findings": []}}}, "action.schema.json")


def test_config_schema_rejects_typos():
    good = json.loads((ROOT / "configs" / "dev" / "alloc_cutoff.json").read_text())
    assert REG.errors({**good, "ledger_row": [1, 2]}, "config.schema.json")
    assert REG.errors({**good, "errors": {"fx_eror": {"count": 1}}}, "config.schema.json")
    assert REG.errors({**good, "errors": {"fx_error": {"count": 1, "variants": ["typo"]}}}, "config.schema.json")
    ok(cfg("dev/alloc_cutoff.json") | {"config_id": "dev-alloc-cutoff-v1"}, "config.schema.json")
