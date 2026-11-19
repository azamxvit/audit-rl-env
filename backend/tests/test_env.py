"""Contract: reset/step, schemas, limits, termination, invalid input, eval isolation."""

import json

import pytest

from audit_env.env import MAX_STEPS, AuditEnv
from audit_env.grader import load_episode
from audit_env.policies import OraclePolicy
from audit_env.trajectories import run_episode

OBS_KEYS = {"tool", "ok", "result", "error", "steps_remaining"}


def env_with(seed=11, config=None, **kw):
    env = AuditEnv("train", **kw)
    obs, info = env.reset(seed=seed, config=config)
    return env, obs, info


def test_reset_observation_contents():
    env, obs, info = env_with()
    assert set(obs) == {"task", "manifest", "policy", "tables", "tools", "max_steps", "steps_remaining"}
    assert obs["steps_remaining"] == MAX_STEPS == 100
    m = obs["manifest"]
    for k in (
        "schema_version",
        "episode_id",
        "base_currency",
        "period_start",
        "period_end",
        "timezone",
        "counts",
        "rounding",
    ):
        assert k in m
    assert "seed" not in json.dumps(obs).lower()
    json.dumps(obs)  # JSON-compatible
    assert set(info) == {"env_version", "schema_version", "mode"}


def test_step_returns_five_tuple_json_compatible():
    env, obs, _ = env_with()
    out = env.step({"tool": "list_records", "args": {"table": "ledger"}})
    assert len(out) == 5
    obs, reward, term, trunc, info = out
    assert set(obs) == OBS_KEYS and obs["ok"] and reward == 0.0 and not term and not trunc and info == {}
    json.dumps(obs)
    assert obs["steps_remaining"] == 99


def test_pagination_limit_and_stable_opaque_cursors():
    env, obs, _ = env_with()
    n = obs["tables"]["ledger"]["count"]
    seen, cursor, pages = [], None, 0
    while True:
        args = {"table": "ledger"} if cursor is None else {"table": "ledger", "cursor": cursor}
        o = env.step({"tool": "list_records", "args": args})[0]
        assert len(o["result"]["records"]) <= 50
        seen += [r["row_id"] for r in o["result"]["records"]]
        cursor = o["result"]["next_cursor"]
        pages += 1
        if cursor is None:
            break
        assert cursor.startswith("c_") and "ledger" not in cursor and not cursor[2:].isdigit()
    assert len(seen) == n == len(set(seen))
    # same position -> same cursor (stable); re-reading gives same page
    env2, _, _ = env_with()
    a = env2.step({"tool": "list_records", "args": {"table": "ledger"}})[0]["result"]
    b = env2.step({"tool": "list_records", "args": {"table": "ledger"}})[0]["result"]
    assert a == b
    o = env2.step({"tool": "list_records", "args": {"table": "ledger", "cursor": a["next_cursor"]}})[0]
    assert o["result"]["records"][0]["row_id"] == seen[50]


@pytest.mark.parametrize(
    "action,code",
    [
        ({"tool": "rm -rf"}, "unknown_tool"),
        ({"tool": "shell", "args": {"cmd": "ls"}}, "unknown_tool"),
        ("not a dict", "invalid_action"),
        ({"tool": "list_records", "args": "x"}, "invalid_action"),
        ({"tool": "list_records", "args": {"table": "truth"}}, "unknown_table"),
        ({"tool": "list_records", "args": {"table": "ledger", "limit": 51}}, "invalid_limit"),
        ({"tool": "list_records", "args": {"table": "ledger", "limit": 0}}, "invalid_limit"),
        ({"tool": "list_records", "args": {"table": "ledger", "cursor": "c_forged"}}, "invalid_cursor"),
        ({"tool": "list_records", "args": {"table": "ledger", "extra": 1}}, "invalid_args"),
        ({"tool": "get_record", "args": {"table": "ledger", "id": "LR-NOPE0000"}}, "unknown_id"),
        ({"tool": "get_record", "args": {"table": "ledger"}}, "invalid_args"),
        ({"tool": "get_document", "args": {"doc_id": "../private/truth.json"}}, "unknown_id"),
        ({"tool": "calculator", "args": {"expression": "__import__('os')"}}, "calculator_error"),
    ],
)
def test_bounded_errors_consume_step(action, code):
    env, obs, _ = env_with()
    o, r, term, trunc, info = env.step(action)
    assert not o["ok"] and o["error"]["code"] == code and o["result"] is None
    assert len(o["error"]["message"]) < 120
    assert o["steps_remaining"] == 99 and r == 0.0 and not term and not trunc


def test_cursor_from_other_table_rejected():
    env, _, _ = env_with()
    c = env.step({"tool": "list_records", "args": {"table": "invoices"}})[0]["result"]["next_cursor"]
    o = env.step({"tool": "list_records", "args": {"table": "ledger", "cursor": c}})[0]
    assert o["error"]["code"] == "invalid_cursor"


def test_get_record_and_document():
    env, obs, _ = env_with()
    page = env.step({"tool": "list_records", "args": {"table": "invoices", "limit": 1}})[0]["result"]["records"][0]
    o = env.step({"tool": "get_record", "args": {"table": "invoices", "id": page["invoice_id"]}})[0]
    assert o["result"] == page
    o = env.step({"tool": "get_record", "args": {"table": "invoices", "id": page["doc_id"]}})[0]
    assert o["result"] == page
    o = env.step({"tool": "get_document", "args": {"doc_id": page["doc_id"]}})[0]
    assert o["result"] == {"doc_type": "invoice", "document": page}
    o = env.step({"tool": "calculator", "args": {"expression": "1.1 + 2.2"}})[0]
    assert o["result"] == {"value": "3.3"}


def test_returned_records_cannot_mutate_store():
    env, _, _ = env_with()
    a = env.step({"tool": "list_records", "args": {"table": "invoices", "limit": 1}})[0]["result"]["records"][0]
    a["total_minor"] = -1
    b = env.step({"tool": "list_records", "args": {"table": "invoices", "limit": 1}})[0]["result"]["records"][0]
    assert b["total_minor"] != -1


def test_submit_terminates_and_repeat_submit_is_inert():
    env, obs, _ = env_with()
    eid = obs["manifest"]["episode_id"]
    o, r, term, trunc, info = env.step({"tool": "submit", "args": {"episode_id": eid, "findings": []}})
    assert term and not trunc and info["termination"] == "submit"
    first = r
    o, r2, term2, trunc2, info2 = env.step({"tool": "submit", "args": {"episode_id": eid, "findings": []}})
    assert o["error"]["code"] == "episode_finished" and r2 == 0.0 and term2 and info2 == {}
    assert env._grader.result["reward"] == first


def test_submit_findings_json_wrapper_accepted():
    env, obs, _ = env_with()
    sub = {"episode_id": obs["manifest"]["episode_id"], "findings": []}
    _, r, term, _, info = env.step({"tool": "submit", "args": {"findings": sub}})
    assert term and info["valid"]


def test_step_limit_truncates_with_empty_answer():
    env, obs, _ = env_with(seed=11)
    n_truth = len(load_episode(11, None).truth["issues"])
    for _ in range(MAX_STEPS - 1):
        o, r, term, trunc, info = env.step({"tool": "calculator", "args": {"expression": "1+1"}})
        assert not trunc and not term
    o, r, term, trunc, info = env.step({"tool": "calculator", "args": {"expression": "1+1"}})
    assert trunc and not term and o["steps_remaining"] == 0
    assert info["termination"] == "step_limit" and info["metrics"]["fn"] == n_truth and info["metrics"]["fp"] == 0
    assert r == -1.0  # empty answer on erroneous books, clipped
    o, r, term, trunc, _ = env.step({"tool": "calculator", "args": {"expression": "1+1"}})
    assert o["error"]["code"] == "episode_finished" and trunc


def test_submit_on_last_step_allowed():
    env, obs, _ = env_with()
    for _ in range(MAX_STEPS - 1):
        env.step({"tool": "calculator", "args": {"expression": "1"}})
    o, r, term, trunc, info = env.step(
        {"tool": "submit", "args": {"episode_id": obs["manifest"]["episode_id"], "findings": []}}
    )
    assert term and not trunc and info["inspection_steps"] == 99


def test_time_limit_truncates():
    t = [0.0]
    env, obs, _ = env_with(clock=lambda: t[0])
    env.step({"tool": "calculator", "args": {"expression": "1"}})
    t[0] = 61.0
    o, r, term, trunc, info = env.step({"tool": "list_records", "args": {"table": "ledger"}})
    assert trunc and not term and o["error"]["code"] == "time_limit" and o["result"] is None
    assert info["termination"] == "time_limit"


def test_reset_isolates_state():
    env, obs, _ = env_with(seed=1)
    c = env.step({"tool": "list_records", "args": {"table": "ledger"}})[0]["result"]["next_cursor"]
    env.step({"tool": "submit", "args": {"episode_id": obs["manifest"]["episode_id"], "findings": []}})
    obs2, _ = env.reset(seed=2)
    assert obs2["steps_remaining"] == 100
    o = env.step({"tool": "list_records", "args": {"table": "ledger", "cursor": c}})[0]
    assert o["error"]["code"] == "invalid_cursor"  # cursors of a previous episode are dead
    o, r, term, *_ = env.step({"tool": "submit", "args": {"episode_id": obs["manifest"]["episode_id"], "findings": []}})
    assert term and r == -1.0  # old episode_id -> invalid submission


def test_step_before_reset_raises():
    with pytest.raises(RuntimeError):
        AuditEnv("train").step({"tool": "calculator", "args": {"expression": "1"}})


def test_eval_mode_hides_reward_and_info(tmp_path):
    log = tmp_path / "grader.jsonl"
    env = AuditEnv("eval", grader_log=log)
    try:
        truth = load_episode(3, None).truth
        res = run_episode(env, OraclePolicy(truth), seed=3)
        assert res["return"] == 0.0 and res["info"] == {}
        assert env._grader is None  # no truth object in the agent process
        rec = [json.loads(x) for x in log.read_text().splitlines()]
        assert rec[-1]["reward"] == 1.0 and rec[-1]["valid"]
    finally:
        env.close()


def test_eval_plan_slots_hide_seed(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"slot-a": {"seed": 1234, "config": None}}))
    env = AuditEnv("eval", grader_log=tmp_path / "g.jsonl", eval_plan=plan)
    try:
        obs, _ = env.reset(seed=None, config={"plan_slot": "slot-a"})
        assert obs["manifest"]["episode_id"] == load_episode(1234, None).episode_id
    finally:
        env.close()
