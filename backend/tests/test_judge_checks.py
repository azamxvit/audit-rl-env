"""The organisers' published check definitions, run literally through judge_adapter.py.

Block 1  C01-C20  contract and isolation (closed and train mode)
Block 2  D01-D20  closed-episode matrix from configs/judge (independent checker + composition)
Block 3  1-20     matcher and reward on the shared fixture (one error A, 10000 KZT, evidence {D1, D2}, tau 0)
         M01-M12  open matcher examples
Block 4  P01-P20  paired checks: the jury copies an episode, permutes and/or renames ids itself
"""

import copy
import json
import random
from pathlib import Path

import judge_adapter as ja
import pytest

from audit_env.checker import verify_episode
from audit_env.generator import Episode, load_config, load_private, load_public, write_episode
from conftest import ROOT

JUDGE = ROOT / "configs" / "judge"
D_CONFIGS = sorted(JUDGE.glob("d*.json"))
TYPES = ["duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"]


@pytest.fixture(autouse=True)
def _grader_log(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_ENV_GRADER_LOG", str(tmp_path / "grader_log.jsonl"))


def gen(tmp_path, config: dict, seed: int, name: str) -> Path:
    d = tmp_path / name
    ja.generate_episode(seed, config, str(d))
    return d


@pytest.fixture
def fixtures(tmp_path):
    clean = gen(tmp_path, load_config(JUDGE / "d01_clean_reconciliation.json"), 11, "C")
    one = load_config(JUDGE / "d12_fx_wrong_rate_date.json")
    one["errors"]["fx_error"]["count"] = 1
    err = gen(tmp_path, one, 12, "E")
    assert len(load_private(err)[0]["issues"]) == 1 and not load_private(clean)[0]["issues"]
    assert len(load_public(clean)["ledger"]) >= 101  # fixture L: three pages of 50
    return clean, err


def closed(d: Path) -> dict:
    return {"mode": "closed", "episode_dir": str(d), "team_config": {}}


def roundtrip(x):
    return json.loads(json.dumps(x))


def walk_ids(d: Path) -> set:
    pub = load_public(d)
    ids = {r["row_id"] for r in pub["ledger"]} | {r["rate_id"] for r in pub["fx"]}
    for t in ("invoices", "payments"):
        for r in pub[t]:
            ids |= {r["doc_id"], r["invoice_id" if t == "invoices" else "payment_id"]}
    return ids


def unknown_id(d: Path) -> str:
    known, k = walk_ids(d), 0
    while f"U-{k:08d}" in known:  # chosen after reading the data, not by its look
        k += 1
    return f"U-{k:08d}"


# ============================================================================ Block 1: C01-C20


def test_c01_to_c04_reset_manifest_and_step_shape(fixtures):
    c, _ = fixtures
    env = ja.make_env()
    try:
        obs, info = env.reset(seed=None, config=closed(c))
        assert roundtrip(obs) == obs and roundtrip(info) == info  # C01
        assert set(obs) == {"task", "manifest", "policy", "remaining_steps"} and obs["remaining_steps"] == 100  # C02
        assert "seed" not in json.dumps(obs) and "truth" not in json.dumps(obs)
        m, pub = obs["manifest"], load_public(c)  # C03
        for k in (
            "schema_version",
            "episode_id",
            "base_currency",
            "period_start",
            "period_end",
            "timezone",
            "rounding",
        ):
            assert m[k]
        assert m["counts"]["ledger_rows"] == len(pub["ledger"]) and m["counts"]["invoices"] == len(pub["invoices"])
        assert m["counts"]["payments"] == len(pub["payments"]) and m["counts"]["fx_rates"] == len(pub["fx"])
        assert m["counts"]["documents"] == len(pub["invoices"]) + len(pub["payments"])
        out = env.step({"name": "list_records", "args": {"table": "ledger", "cursor": None, "limit": 10}})  # C04
        assert len(out) == 5 and isinstance(out[2], bool) and isinstance(out[3], bool)
        assert roundtrip(list(out)) == list(out) and set(out[0]) == {"result", "error", "remaining_steps"}
    finally:
        env.close()


def test_c05_c06_pagination_complete_and_stable(fixtures):
    c, _ = fixtures
    env = ja.make_env()
    try:
        env.reset(config=closed(c))
        seen, cursor, first_cursor_page = [], None, None
        while True:
            obs = env.step({"name": "list_records", "args": {"table": "ledger", "cursor": cursor, "limit": 50}})[0]
            recs = obs["result"]["records"]
            assert len(recs) <= 50
            seen += [r["row_id"] for r in recs]
            if cursor and first_cursor_page is None:
                first_cursor_page = (cursor, recs)
            cursor = obs["result"]["next_cursor"]
            if cursor is None:
                break
        assert seen == [r["row_id"] for r in load_public(c)["ledger"]] and len(set(seen)) == len(seen)  # C05
        again = env.step(
            {"name": "list_records", "args": {"table": "ledger", "cursor": first_cursor_page[0], "limit": 50}}
        )
        assert again[0]["result"]["records"] == first_cursor_page[1]  # C06
    finally:
        env.close()


def test_c07_to_c14_records_documents_calculator_and_errors(fixtures):
    c, _ = fixtures
    pub, u = load_public(c), unknown_id(c)
    r1, d1 = pub["ledger"][0], pub["invoices"][0]
    env = ja.make_env()
    try:
        env.reset(config=closed(c))
        assert (
            env.step({"name": "get_record", "args": {"table": "ledger", "id": r1["row_id"]}})[0]["result"] == r1
        )  # C07
        assert env.step({"name": "get_document", "args": {"doc_id": d1["doc_id"]}})[0]["result"] == d1  # C08
        assert env.step({"name": "calculator", "args": {"expression": "0.1+0.2"}})[0]["result"] == "0.3"  # C09
        o = env.step({"name": "calculator", "args": {"expression": "open('/etc/passwd').read()"}})[0]  # C10
        assert o["result"] is None and o["error"]["code"] == "calculator_error" and "root" not in json.dumps(o)
        for action in (  # C11, C12, C13
            {"name": "get_record", "args": {"table": "ledger", "id": u}},
            {"name": "get_document", "args": {"doc_id": u}},
            {"name": "drop_table", "args": {}},
        ):
            before = env.step({"name": "calculator", "args": {"expression": "1"}})[0]["remaining_steps"]
            o = env.step(action)[0]
            assert o["result"] is None and o["error"]["code"] and o["remaining_steps"] == before - 1
        r = [
            env.step(a)[0]
            for a in (  # C14
                {"name": "get_record", "args": {"table": "ledger", "id": r1["row_id"]}},
                {"name": "get_record", "args": {"table": "ledger", "id": u}},
                {"name": "get_record", "args": {"table": "ledger", "id": r1["row_id"]}},
            )
        ]
        assert [x["remaining_steps"] for x in r] == [
            r[0]["remaining_steps"],
            r[0]["remaining_steps"] - 1,
            r[0]["remaining_steps"] - 2,
        ]
        assert r[2]["result"] == r1
    finally:
        env.close()


def _oracle(d: Path) -> dict:
    truth, _ = load_private(d)
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


def test_c15_c16_c17_submit_limits_and_finality(fixtures):
    _, e = fixtures
    env = ja.make_env()
    try:
        env.reset(config={"mode": "train", "episode_dir": str(e)})
        obs, r, term, trunc, info = env.step({"name": "submit", "args": {"findings": _oracle(e)}})  # C15
        assert term and not trunc and obs["result"] == {"accepted": True} and info["metrics"]["tp"] == 1
        after = env.step(
            {"name": "submit", "args": {"findings": {"episode_id": _oracle(e)["episode_id"], "findings": []}}}
        )
        assert after[0]["error"]["code"] == "episode_finished" and after[1] == 0.0
        assert env._envs["train"]._grader.result["tp"] == 1  # fixed once
        env.reset(config={"mode": "train", "episode_dir": str(e)})  # C16: 99 inspections, submit as action 100
        for _ in range(99):
            assert not env.step({"name": "calculator", "args": {"expression": "1"}})[3]
        obs, r, term, trunc, info = env.step({"name": "submit", "args": {"findings": _oracle(e)}})
        assert term and not trunc and obs["result"] == {"accepted": True} and info["inspection_steps"] == 99
        env.reset(config={"mode": "train", "episode_dir": str(e)})  # C17: 100 inspections, no submit
        for _ in range(100):
            out = env.step({"name": "calculator", "args": {"expression": "1"}})
        assert out[3] and not out[2] and out[4]["termination"] == "step_limit" and out[4]["metrics"]["tp"] == 0
        late = env.step({"name": "submit", "args": {"findings": _oracle(e)}})
        assert late[0]["error"]["code"] == "episode_finished" and env._envs["train"]._grader.result["fn"] == 1
    finally:
        env.close()


def test_c18_time_limit_truncates_with_empty_findings(fixtures):
    _, e = fixtures
    env = ja.make_env()
    try:
        t = [0.0]
        env._inner("train")._clock = lambda: t[0]
        env.reset(config={"mode": "train", "episode_dir": str(e)})
        env.step({"name": "calculator", "args": {"expression": "1"}})
        t[0] = 60.5  # the policy took too long
        obs, r, term, trunc, info = env.step({"name": "submit", "args": {"findings": _oracle(e)}})
        assert trunc and not term and obs["error"]["code"] == "time_limit" and info["termination"] == "time_limit"
        assert env._envs["train"]._grader.result["n_findings"] == 0
    finally:
        env.close()


def test_c19_closed_mode_hides_reward_and_diagnostics(fixtures, tmp_path):
    _, e = fixtures
    env = ja.make_env()
    try:
        env.reset(config=closed(e))
        for a in (
            {"name": "list_records", "args": {"table": "payments", "cursor": None, "limit": 5}},
            {"name": "calculator", "args": {"expression": "2*3"}},
        ):
            _, r, _, _, info = env.step(a)
            assert r == 0 and isinstance(r, float) and info == {}
        obs, r, term, _, info = env.step({"name": "submit", "args": {"findings": _oracle(e)}})
        assert (
            term
            and r == 0
            and info == {}
            and obs == {"result": {"accepted": True}, "error": None, "remaining_steps": 97}
        )
    finally:
        env.close()
    graded = json.loads((tmp_path / "grader_log.jsonl").read_text().splitlines()[-1])
    assert graded["tp"] == 1 and graded["reward"] > 0.9 and graded["inspection_steps"] == 2


def test_c20_no_leak_through_any_channel(fixtures):
    for d in fixtures:
        truth, prov = load_private(d)
        secrets = {i["issue_id"] for i in truth["issues"]} | {c["change_id"] for c in prov["changes"]}
        secrets |= {prov["config_sha256"], "private", "truth", "provenance", str(d)}
        env = ja.make_env()
        stream = []
        try:
            stream.append(env.reset(config=closed(d)))
            for t in ("ledger", "invoices", "payments", "fx"):
                cursor = None
                while True:
                    out = env.step({"name": "list_records", "args": {"table": t, "cursor": cursor, "limit": 50}})
                    stream.append(out)
                    cursor = out[0]["result"]["next_cursor"]
                    if cursor is None:
                        break
            for doc in load_public(d)["invoices"][:5]:
                stream.append(env.step({"name": "get_document", "args": {"doc_id": doc["doc_id"]}}))
            for bad in (
                {"name": "shell", "args": {"cmd": "cat private/truth.json"}},
                {"name": "sql", "args": {"q": "select * from truth"}},
                {"name": "get_document", "args": {"doc_id": "../private/truth.json"}},
                {"name": "calculator", "args": {"expression": "__import__('os').listdir('.')"}},
            ):
                out = env.step(bad)
                assert out[0]["result"] is None and out[0]["error"]
                stream.append(out)
        finally:
            env.close()
        blob = json.dumps(stream)
        assert not [s for s in secrets if s and s in blob]


# ============================================================================ Block 2: D01-D20


@pytest.mark.parametrize("path", D_CONFIGS, ids=[p.stem[:3] for p in D_CONFIGS])
def test_closed_episode_matrix(tmp_path, path):
    cfg = load_config(path)
    want = {
        "d01": [], "d02": [], "d03": [], "d04": [], "d05": [],
        "d06": ["duplicate_invoice"], "d07": ["duplicate_invoice"], "d08": ["duplicate_invoice"],
        "d09": ["payment_allocation"], "d10": ["payment_allocation"], "d11": ["payment_allocation"],
        "d12": ["fx_error"], "d13": ["fx_error"], "d14": ["period_cutoff"], "d15": ["period_cutoff"],
        "d16": ["fx_error", "payment_allocation"], "d17": ["fx_error", "payment_allocation"],
        "d18": ["fx_error", "payment_allocation"], "d19": ["fx_error", "period_cutoff"], "d20": ["fx_error", "period_cutoff"],
    }[path.stem[:3]]  # fmt: skip
    for seed in (101, 202, 303):
        d = gen(tmp_path, cfg, seed, f"ep{seed}")
        pub, (truth, prov) = load_public(d), load_private(d)
        assert verify_episode(pub, truth) == []  # conditions 2-6, independently of the matcher
        assert sorted({i["type"] for i in truth["issues"]}) == want
        if not want:
            assert truth["issues"] == []
        dist = prov["distractors"]
        stem = path.stem[:3]
        assert stem != "d02" or dist["split_payment_invoices"] > 0
        assert stem != "d03" or dist["refunds"] > 0
        assert stem != "d04" or dist["subscription_customers"] > 0
        assert stem != "d09" or {i["variant"] for i in truth["issues"]} == {"missing"}
        assert stem != "d10" or {i["variant"] for i in truth["issues"]} == {"partial"}
        assert stem not in ("d16", "d17", "d18") or {i["scenario"] for i in truth["issues"]} == {"fx_partial_boundary"}
        assert stem not in ("d19", "d20") or {i["scenario"] for i in truth["issues"]} == {"cutoff_fx"}


# ============================================================================ Block 3: reward 1-20, M01-M12


@pytest.fixture
def shared(tmp_path):
    """One error A of type T on canonical record R1, 10000 KZT, admissible evidence {D1, D2}, tau = 0."""
    base = gen(tmp_path, {"base_currencies": ["KZT"]}, 7, "base")
    pub, (truth, prov) = load_public(base), load_private(base)
    inv = [i for i in pub["invoices"]][:6]
    rows = [r["row_id"] for r in pub["ledger"]]
    ids = {
        "R": [i["invoice_id"] for i in inv],
        "D1": inv[0]["doc_id"],
        "D2": rows[0],
        "D3": rows[1],
        "D4": rows[2],
        "U": unknown_id(base),
    }

    def write(issues, name, tolerance=0):
        t = dict(truth, issues=issues, tolerance_minor=tolerance)
        d = tmp_path / name
        write_episode(Episode(pub, t, prov, {}), d)
        return d

    def issue(iid, rec, evidence, type_="period_cutoff", amount=10000):
        return {"issue_id": iid, "type": type_, "variant": "next_period", "scenario": None, "affected_ids": sorted(rec),
                "expected_amount_minor": amount, "currency": "KZT", "evidence_sets": evidence}  # fmt: skip

    return ids, write, issue, truth["episode_id"]


def F(affected, evidence, type_="period_cutoff", amount=10000, currency="KZT", explanation="short"):
    return {"type": type_, "affected_ids": affected, "claimed_amount_minor": amount, "currency": currency,
            "evidence_ids": evidence, "explanation": explanation}  # fmt: skip


def score(d, eid, findings, steps=10):
    return ja.score_episode(str(d), {"episode_id": eid, "findings": findings}, steps)


def expect(res, tp, fp, fn, p, r, f1, ret):
    assert (res["tp"], res["fp"], res["fn"]) == (tp, fp, fn)
    for k, v in (("precision", p), ("recall", r), ("f1", f1), ("return", ret)):
        assert abs(res[k] - v) <= 1e-9, (k, res[k], v)


def test_block3_reward_vectors_1_to_20(shared):
    ids, write, issue, eid = shared
    R1, R2 = ids["R"][0], ids["R"][1]
    good = F([R1], [ids["D1"], ids["D2"]])
    A = write([issue("ISS-A", [R1], [[ids["D1"], ids["D2"]]])], "A")
    none = write([], "none")
    expect(score(A, eid, [good]), 1, 0, 0, 1, 1, 1, 0.98)  # 1
    expect(score(A, eid, []), 0, 0, 1, 0, 0, 0, -1)  # 2
    expect(score(none, eid, []), 0, 0, 0, 0, 0, 1, 0.98)  # 3
    expect(score(none, eid, [good]), 0, 1, 0, 0, 0, 0, -1)  # 4
    expect(score(A, eid, [good, good]), 1, 1, 0, 0.5, 1, 2 / 3, 47 / 150)  # 5
    expect(score(A, eid, [dict(good, type="fx_error")]), 0, 1, 1, 0, 0, 0, -1)  # 6
    expect(score(A, eid, [dict(good, affected_ids=[R2])]), 0, 1, 1, 0, 0, 0, -1)  # 7
    expect(score(A, eid, [dict(good, claimed_amount_minor=10001)]), 0, 1, 1, 0, 0, 0, -1)  # 8
    expect(score(A, eid, [dict(good, currency="USD")]), 0, 1, 1, 0, 0, 0, -1)  # 9
    expect(score(A, eid, [dict(good, evidence_ids=[ids["D1"]])]), 0, 1, 1, 0, 0, 0, -1)  # 10
    expect(score(A, eid, [dict(good, evidence_ids=[ids["D1"], ids["U"]])]), 0, 1, 1, 0, 0, 0, -1)  # 11
    flood = [F([r], [ids["D1"], ids["D2"]], type_=t) for r in ids["R"][:5] for t in TYPES]  # 12
    expect(score(A, eid, flood), 1, 19, 0, 1 / 20, 1, 2 / 21, -871 / 1050)
    AB = write([issue("ISS-A", [R1], [[ids["D1"], ids["D2"]]]), issue("ISS-B", [R2], [[ids["D3"], ids["D4"]]])], "AB")
    expect(score(AB, eid, [good]), 1, 0, 1, 1, 0.5, 2 / 3, 47 / 150)  # 13
    expect(score(AB, eid, [good, F([ids["R"][2]], [ids["D3"]])]), 1, 1, 1, 0.5, 0.5, 0.5, -0.02)  # 14
    for steps, ret in ((0, 1.0), (50, 0.90), (100, 0.80)):  # 15-17
        expect(score(A, eid, [good], steps), 1, 0, 0, 1, 1, 1, ret)
    bad = ja.score_episode(str(A), {"episode_id": eid, "findings": [good] * 31}, 10)  # 18
    eleven = [ids["D1"], ids["D2"], ids["D3"], ids["D4"]] + ids["R"][:6] + [ids["U"]]
    for res in (
        bad,
        score(A, eid, [dict(good, evidence_ids=eleven)]),
        score(A, eid, [dict(good, explanation="x" * 1001)]),
    ):
        assert res == {
            "tp": None,
            "fp": None,
            "fn": None,
            "precision": None,
            "recall": None,
            "f1": None,
            "return": -1.0,
        }  # 18-20


def test_block3_open_examples_m01_to_m12(shared, tmp_path):
    ids, write, issue, eid = shared
    R1, R2, R3 = ids["R"][:3]
    D1, D2, D3, U = ids["D1"], ids["D2"], ids["D3"], ids["U"]
    A = write([issue("ISS-A", [R1, R2], [[D1, D2]])], "M")
    ok = F([R1, R2], [D1, D2])
    assert score(A, eid, [dict(ok, affected_ids=[R2, R1, R1])])["tp"] == 1  # M01
    expect(score(A, eid, [dict(ok, affected_ids=[R1, R2, R3])]), 0, 1, 1, 0, 0, 0, -1)  # M02
    assert score(A, eid, [dict(ok, evidence_ids=[D2, D1, D3])])["tp"] == 1  # M03
    expect(score(A, eid, [dict(ok, evidence_ids=[D1, D2, U])]), 0, 1, 1, 0, 0, 0, -1)  # M04
    assert score(A, eid, [dict(ok, evidence_ids=[D2] + [D1] * 10)])["return"] == -1.0  # M05
    for ccy in ("kzt", " KZT", "KZT "):  # M06
        expect(score(A, eid, [dict(ok, currency=ccy)]), 0, 1, 1, 0, 0, 0, -1)
    expect(score(A, eid, [dict(ok, claimed_amount_minor=10001)]), 0, 1, 1, 0, 0, 0, -1)  # M07
    A1 = write([issue("ISS-A", [R1, R2], [[D1, D2]])], "M08", tolerance=1)  # M08
    assert score(A1, eid, [dict(ok, claimed_amount_minor=10001)])["tp"] == 1
    assert score(A1, eid, [dict(ok, claimed_amount_minor=10002)])["tp"] == 0
    for amt in ("10000", True):  # M09
        assert score(A, eid, [dict(ok, claimed_amount_minor=amt)])["return"] == -1.0
    AB = write([issue("ISS-A", [R1, R2], [[D1]]), issue("ISS-B", [R1, R2], [[D2]])], "M10")
    f0, f1 = F([R1, R2], [D1, D2]), F([R1, R2], [D1])  # M10: F0 fits A and B, F1 only A
    expect(score(AB, eid, [f0, f1]), 2, 0, 0, 1, 1, 1, 0.98)
    log = Path(ja.grader_log_path())
    assert json.loads(log.read_text().splitlines()[-1])["matches"] == [[0, "ISS-B"], [1, "ISS-A"]]
    expect(score(AB, eid, [f0, f0]), 2, 0, 0, 1, 1, 1, 0.98)  # M11: both fit both -> A->F0, B->F1
    assert json.loads(log.read_text().splitlines()[-1])["matches"] == [[0, "ISS-A"], [1, "ISS-B"]]
    expect(score(A, eid, [ok, ok]), 1, 1, 0, 0.5, 1, 2 / 3, 47 / 150)  # M12


# ============================================================================ Block 4: P01-P20


ID_FIELDS = {
    "ledger": ("row_id", "entity_id", "invoice_id", "payment_id"),
    "invoices": ("doc_id", "invoice_id", "entity_id"),
    "payments": ("doc_id", "payment_id", "entity_id"),
}


def jury_transform(src: Path, dst: Path, permute: bool, rename: bool, seed: int) -> dict:
    """What the jury does to a copy: shuffle records and/or rename ids consistently, truth/provenance included."""
    pub, (truth, prov) = load_public(src), load_private(src)
    rng = random.Random(seed)
    mapping = {}
    if rename:
        for table, fields in ID_FIELDS.items():
            for rec in pub[table]:
                for f in fields:
                    v = rec[f]
                    if v is not None and v not in mapping:
                        mapping[v] = f"J{rng.getrandbits(48):012x}"  # a foreign format with no prefix

    def walk(x):
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return mapping.get(x, x) if isinstance(x, str) else x

    pub2, truth2, prov2 = walk(pub), walk(truth), walk(prov)
    if permute:
        for t in ("ledger", "invoices", "payments", "fx"):
            rng.shuffle(pub2[t])  # whole records only; line_items keep their order
    write_episode(Episode(pub2, truth2, prov2, {}), dst)
    return mapping


def _replay(d: Path, actions: list) -> list:
    env = ja.make_env()
    try:
        out = [env.reset(config={"mode": "train", "episode_dir": str(d)})]
        out += [env.step(a) for a in actions]
        return roundtrip(out)
    finally:
        env.close()


PAIRS = [(f"P{k + 1:02d}", D_CONFIGS[k], k < 5 or k >= 10, k >= 5) for k in range(20)]


@pytest.mark.parametrize("pid,path,permute,rename", PAIRS, ids=[p[0] for p in PAIRS])
def test_paired_checks(tmp_path, pid, path, permute, rename):
    orig = gen(tmp_path, load_config(path), 4242, "orig")
    mapping = jury_transform(orig, tmp_path / "copy", permute, rename, seed=hash(pid) % 1000)
    copy_ = tmp_path / "copy"
    # 1. the original replays exactly (records, transitions, rewards)
    actions = [
        {"name": "list_records", "args": {"table": "ledger", "cursor": None, "limit": 50}},
        {"name": "get_document", "args": {"doc_id": load_public(orig)["invoices"][0]["doc_id"]}},
        {"name": "calculator", "args": {"expression": "1/3"}},
        {"name": "submit", "args": {"findings": _oracle(orig)}},
    ]
    assert _replay(orig, actions) == _replay(orig, copy.deepcopy(actions))
    # 2./3. the oracle on the copy, ids renamed, same inspection steps -> identical metrics and return
    a, b = _oracle(orig), _oracle(copy_)
    inverse = {v: k for k, v in mapping.items()}
    back = [
        (f["type"], sorted(inverse.get(x, x) for x in f["affected_ids"]), f["claimed_amount_minor"], f["currency"],
         sorted(inverse.get(x, x) for x in f["evidence_ids"]))
        for f in b["findings"]
    ]  # fmt: skip
    assert sorted(back) == sorted(
        (f["type"], sorted(f["affected_ids"]), f["claimed_amount_minor"], f["currency"], sorted(f["evidence_ids"]))
        for f in a["findings"]
    )
    ra, rb = ja.score_episode(str(orig), a, 7), ja.score_episode(str(copy_), b, 7)
    assert ra == rb and ra["tp"] == len(a["findings"]) and ra["fp"] == ra["fn"] == 0
    assert abs(ra["return"] - max(-1.0, min(1.0, 2 * ra["f1"] - 1 - 0.002 * 7))) <= 1e-9
    # 4. no broken evidence: the copy is still independently valid
    assert verify_episode(load_public(copy_), load_private(copy_)[0]) == []
