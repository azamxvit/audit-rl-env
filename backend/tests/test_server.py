"""Auditor Playground HTTP API: thin wrapper over AuditEnv, no truth before the episode ends."""

import http.client
import json
import threading
from pathlib import Path

import pytest

from audit_env.env import AuditEnv
from audit_env.server import PlaygroundApp, make_server

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    static = tmp_path_factory.mktemp("dist")
    (static / "index.html").write_text("<!doctype html><title>AuditDesk</title>")
    (static / "app.js").write_text("console.log(1)")
    app = PlaygroundApp(BACKEND / "episodes", static)
    srv = make_server(app, "127.0.0.1", 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv.server_address[1], app
    srv.shutdown()


def req(port, method, path, body=None, raw=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    c.request(method, path, body=data, headers={"Content-Type": "application/json"})
    r = c.getresponse()
    payload = r.read()
    c.close()
    ctype = r.getheader("Content-Type") or ""
    return r.status, (json.loads(payload) if ctype.startswith("application/json") else payload.decode())


def test_episode_list_has_no_truth(server):
    port, _ = server
    status, eps = req(port, "GET", "/api/episodes")
    assert status == 200 and len(eps) == 20
    assert eps[0]["key"] == "train/00" and {e["split"] for e in eps} == {"train", "dev"}
    blob = json.dumps(eps)
    for leaked in ("n_issues", "issue_types", "scenarios", "seed", "truth"):
        assert leaked not in blob


def test_reset_and_step_match_direct_env(server):
    port, app = server
    status, out = req(port, "POST", "/api/reset", {"episode": "dev/04"})
    assert status == 200 and len(out["session"]) == 32
    env = AuditEnv("train")
    obs, _ = env.reset(config={"episode_dir": str(app.catalog["dev/04"])})
    assert out["observation"] == json.loads(json.dumps(obs))
    action = {"tool": "list_records", "args": {"table": "ledger", "limit": 5}}
    status, step = req(port, "POST", "/api/step", {"session": out["session"], "action": action})
    direct = env.step(action)
    assert status == 200
    assert [step["observation"], step["reward"], step["terminated"], step["truncated"], step["info"]] == json.loads(
        json.dumps(list(direct))
    )


def test_review_only_after_end_and_reports_issues(server):
    port, app = server
    _, out = req(port, "POST", "/api/reset", {"episode": "dev/04"})
    sid = out["session"]
    status, body = req(port, "GET", f"/api/review?session={sid}")
    assert status == 403 and body == {"error": "episode_not_finished"}
    from audit_env.generator import load_private

    truth, _ = load_private(app.catalog["dev/04"])
    first = truth["issues"][0]
    finding = {
        "type": first["type"],
        "affected_ids": first["affected_ids"],
        "claimed_amount_minor": first["expected_amount_minor"],
        "currency": first["currency"],
        "evidence_ids": first["evidence_sets"][0],
        "explanation": "ui",
    }
    eid = out["observation"]["manifest"]["episode_id"]
    _, step = req(
        port,
        "POST",
        "/api/step",
        {"session": sid, "action": {"tool": "submit", "args": {"episode_id": eid, "findings": [finding, finding]}}},
    )
    assert step["terminated"]
    status, review = req(port, "GET", f"/api/review?session={sid}")
    assert status == 200
    assert review["metrics"]["tp"] == 1 and review["metrics"]["fp"] == 1
    assert len(review["issues"]) == len(truth["issues"])
    found = [i for i in review["issues"] if i["status"] == "found"]
    assert len(found) == 1 and found[0]["matched_finding"] == 0
    assert review["false_positives"] == [1]


def test_no_truth_fields_before_submit(server):
    port, _ = server
    _, out = req(port, "POST", "/api/reset", {"episode": "train/00"})
    _, step = req(
        port,
        "POST",
        "/api/step",
        {"session": out["session"], "action": {"tool": "list_records", "args": {"table": "invoices"}}},
    )
    blob = json.dumps([out, step])
    for leaked in ("expected_amount_minor", "evidence_sets", "issue_id", "ISS-"):
        assert leaked not in blob


@pytest.mark.parametrize(
    "method,path,body,raw,status,code",
    [
        ("POST", "/api/reset", {"episode": "../../etc"}, None, 400, "unknown_episode"),
        ("POST", "/api/reset", {"episode": "train/99"}, None, 400, "unknown_episode"),
        ("POST", "/api/step", {"session": "nope", "action": {}}, None, 404, "unknown_session"),
        ("POST", "/api/step", {"session": "nope"}, None, 400, "bad_request"),
        ("POST", "/api/step", None, b"{not json", 400, "bad_json"),
        ("GET", "/api/review?session=nope", None, None, 404, "unknown_session"),
        ("GET", "/api/nothing", None, None, 404, "not_found"),
        ("POST", "/api/nothing", {}, None, 404, "not_found"),
    ],
)
def test_api_errors(server, method, path, body, raw, status, code):
    port, _ = server
    got_status, got = req(port, method, path, body, raw)
    assert got_status == status and got == {"error": code}


def test_body_too_large(server):
    import socket

    port, _ = server
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    s.sendall(
        b"POST /api/step HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\n"
        b"Content-Length: 2000000\r\n\r\n"
    )  # body never sent: the server must refuse before reading it
    data = b""
    while b"too_large" not in data:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
    s.close()
    assert b" 413 " in data.split(b"\r\n")[0] and b'"too_large"' in data


def test_static_files_and_traversal(server):
    port, _ = server
    assert req(port, "GET", "/app.js") == (200, "console.log(1)")
    status, html = req(port, "GET", "/")
    assert status == 200 and "AuditDesk" in html
    status, html = req(port, "GET", "/records/ledger")  # SPA fallback
    assert status == 200 and "AuditDesk" in html
    status, html = req(port, "GET", "/../../pyproject.toml")
    assert status == 200 and "AuditDesk" in html and "setuptools" not in html
    status, html = req(port, "GET", "/%2e%2e/%2e%2e/pyproject.toml")
    assert "setuptools" not in html


def test_session_eviction(server):
    port, app = server
    first = req(port, "POST", "/api/reset", {"episode": "train/01"})[1]["session"]
    for _ in range(33):
        req(port, "POST", "/api/reset", {"episode": "train/01"})
    status, got = req(
        port, "POST", "/api/step", {"session": first, "action": {"tool": "calculator", "args": {"expression": "1"}}}
    )
    assert status == 404 and len(app.sessions) == 32


# --------------------------------------------------------------------------- security review (DESIGN §15)


def raw_request(port, head: bytes, body: bytes = b"", timeout=10) -> bytes:
    import socket

    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.sendall(head)
    try:  # the server may answer and close before the whole body is sent - that is the point
        s.sendall(body)
        s.shutdown(socket.SHUT_WR)
    except OSError:  # BrokenPipe/ECONNRESET on macOS, ENOTCONN on Linux
        pass
    data = b""
    try:
        while chunk := s.recv(65536):
            data += chunk
    except OSError:
        pass
    s.close()
    return data


def _post(port, path, body: dict, headers: dict):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("POST", path, body=json.dumps(body).encode(), headers=headers)
    r = c.getresponse()
    out = (r.status, json.loads(r.read()))
    c.close()
    return out


def test_cross_site_simple_post_cannot_create_or_evict_sessions(server):
    port, _ = server
    status, body = req(port, "POST", "/api/reset", {"episode": "train/00"})
    victim = body["session"]
    for _ in range(40):  # what a malicious page could fire without a CORS preflight
        st, b = _post(port, "/api/reset", {"episode": "dev/00"}, {"Content-Type": "text/plain"})
        assert (st, b["error"]) == (415, "json_required")
    st, b = _post(
        port, "/api/reset", {"episode": "dev/00"}, {"Content-Type": "application/json", "Origin": "http://evil.example"}
    )
    assert (st, b["error"]) == (403, "forbidden_origin")
    st, _ = req(
        port, "POST", "/api/step", {"session": victim, "action": {"tool": "calculator", "args": {"expression": "1"}}}
    )
    assert st == 200  # the victim's game survived
    st, b = _post(
        port,
        "/api/reset",
        {"episode": "dev/00"},
        {"Content-Type": "application/json", "Origin": f"http://localhost:{port}"},
    )
    assert st == 200 and b["session"]


def test_foreign_host_header_is_refused(server):
    port, _ = server
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", "/api/episodes", headers={"Host": "attacker.example"})
    r = c.getresponse()
    assert r.status == 403 and json.loads(r.read())["error"] == "forbidden_host"
    c.close()
    for host in (f"localhost:{port}", f"127.0.0.1:{port}", f"[::1]:{port}"):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("GET", "/api/episodes", headers={"Host": host})
        assert c.getresponse().status == 200, host
        c.close()


def test_negative_or_garbage_content_length_is_rejected(server):
    port, _ = server
    big = b'{"episode":"train/00","pad":"' + b"A" * 2_000_000 + b'"}'
    for length in (b"-1", b"abc", b"1e9"):
        head = (
            b"POST /api/reset HTTP/1.0\r\nHost: 127.0.0.1\r\nContent-Type: application/json\r\nContent-Length: "
            + length
            + b"\r\n\r\n"
        )
        reply = raw_request(port, head, big)
        assert reply.startswith(b"HTTP/1.0 400") and b"bad_length" in reply


def test_banner_and_nul_byte(server):
    port, _ = server
    reply = raw_request(port, b"GET /%00 HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
    assert reply.startswith(b"HTTP/1.0 200")  # served the app shell, no 500
    assert b"Python" not in reply.split(b"\r\n\r\n")[0]


def test_slow_client_times_out(server, monkeypatch):
    import socket
    import time

    import audit_env.server as srv_mod

    _, app = server
    monkeypatch.setattr(srv_mod, "SOCKET_TIMEOUT_S", 1)
    srv = make_server(app, "127.0.0.1", 0)  # handler class picks up the 1 s timeout
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        s = socket.create_connection(("127.0.0.1", srv.server_address[1]), timeout=10)
        s.sendall(b"GET /api/episodes HTTP/1.0\r\n")  # never finishes the request
        t = time.time()
        data = s.recv(100)  # the server gives up and closes instead of holding a thread forever
        assert time.time() - t < 5 and (data == b"" or data.startswith(b"HTTP/1.0 408"))
        s.close()
    finally:
        srv.shutdown()
