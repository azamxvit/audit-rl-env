"""Anti-leak: truth/provenance never reach observations, errors, info, IDs, order or record schemas."""
import json
import re
import statistics

from audit_env.env import AuditEnv
from audit_env.grader import load_episode
from audit_env.policies import FlagAllPolicy, RandomExplorerPolicy, SimpleReconcilerPolicy
from audit_env.trajectories import run_episode

from conftest import episode

PRIVATE_KEYS = ["expected_amount_minor", "evidence_sets", "issue_id", "variant",
                "scenario", "provenance", "truth", "booking_before", "rate_override", "applied_override",
                "period_class", "CHG-", "ISS-", "inject"]


class Spy:
    def __init__(self, env):
        self.env, self.dump = env, []

    def reset(self, seed=None, config=None):
        obs, info = self.env.reset(seed=seed, config=config)
        self.dump.append(json.dumps([obs, info]))
        return obs, info

    def step(self, action):
        out = self.env.step(action)
        o, r, te, tr, info = out
        self.dump.append(json.dumps([o, info]))
        return out


def test_no_private_strings_in_observations_errors_or_info():
    for seed in range(8):
        ep = load_episode(seed, None)
        private_values = {i["issue_id"] for i in ep.truth["issues"]}
        for pol in (RandomExplorerPolicy(seed), SimpleReconcilerPolicy(), FlagAllPolicy()):
            spy = Spy(AuditEnv("train"))
            run_episode(spy, pol, seed=seed)
            blob = "\n".join(spy.dump)
            leaked = [k for k in PRIVATE_KEYS if k in blob] + [v for v in private_values if v in blob]
            assert leaked == []


def test_seed_never_observed():
    spy = Spy(AuditEnv("train"))
    run_episode(spy, SimpleReconcilerPolicy(), seed=987654321)
    found = "987654321" in "\n".join(spy.dump)
    assert not found


def test_errors_do_not_echo_inputs_or_paths():
    env = AuditEnv("train")
    env.reset(seed=1)
    marker = "ZZ_MARKER_/private/truth.json"
    for action in [{"tool": marker}, {"tool": "get_record", "args": {"table": "ledger", "id": marker}},
                   {"tool": "get_document", "args": {"doc_id": marker}},
                   {"tool": "calculator", "args": {"expression": marker}},
                   {"tool": "list_records", "args": {"table": marker}}]:
        o = env.step(action)[0]
        assert marker not in json.dumps(o) and "Traceback" not in json.dumps(o)
        assert "/" not in o["error"]["message"]


def test_record_schemas_identical_for_affected_and_clean_records():
    for seed in range(10):
        ep = episode(seed)
        for table in ("ledger", "invoices", "payments", "fx"):
            assert len({tuple(r.keys()) for r in ep.public[table]}) == 1, table


def test_id_formats_do_not_reveal_errors():
    pattern = {"invoices": r"^INV-[0-9A-Z]{8}$", "payments": r"^PAY-[0-9A-Z]{8}$", "ledger": r"^LR-[0-9A-Z]{8}$"}
    pct_id, pct_pos = [], []
    for seed in range(40):
        ep = episode(seed)
        affected = {x for i in ep.truth["issues"] for x in i["affected_ids"]}
        invs = ep.public["invoices"]
        for r in invs:
            assert re.match(pattern["invoices"], r["invoice_id"])
        ids_sorted = sorted(r["invoice_id"] for r in invs)
        for k, r in enumerate(invs):
            if r["invoice_id"] in affected:
                pct_id.append(ids_sorted.index(r["invoice_id"]) / len(invs))
                pct_pos.append(k / len(invs))
        for r in ep.public["ledger"]:
            assert re.match(pattern["ledger"], r["row_id"])
    # affected invoices sit at uniform-looking ranks by ID and by file position (not appended at the end)
    assert 0.35 < statistics.mean(pct_id) < 0.65
    assert 0.3 < statistics.mean(pct_pos) < 0.7


def test_eval_trajectory_rewards_hidden(tmp_path):
    from audit_env.trajectories import TrajectoryWriter
    env = AuditEnv("eval", grader_log=tmp_path / "g.jsonl")
    try:
        with TrajectoryWriter(tmp_path / "t.jsonl") as w:
            run_episode(env, SimpleReconcilerPolicy(), seed=4, writer=w)
        lines = [json.loads(x) for x in (tmp_path / "t.jsonl").read_text().splitlines()]
        assert all(l["reward"] == 0.0 for l in lines)
        assert set(lines[1]) == {"episode_id", "step", "action", "observation", "reward", "terminated", "truncated"}
        blob = json.dumps([l["observation"] for l in lines])  # actions are the agent's own words
        leaked = [k for k in PRIVATE_KEYS if k in blob]
        assert leaked == []
    finally:
        env.close()
