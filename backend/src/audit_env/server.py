"""Auditor Playground server: JSON API over AuditEnv (train mode) + static host for frontend/dist.

Stdlib only. Run: ``PYTHONPATH=src python -m audit_env.server`` (from backend/) -> http://127.0.0.1:8000
The API is a thin wrapper: /api/step returns exactly what AuditEnv.step returns. Truth is only read
by /api/review, and only after the episode has ended; it is used for open train/dev episodes only.

Local-only hardening (security review, DESIGN §15): requests must name a local Host (blocks DNS
rebinding), a cross-site Origin is refused, POST bodies must be JSON with a valid Content-Length
(<= 1 MB; a cross-site "simple" text/plain POST cannot create or evict sessions), slow clients
time out, and the banner does not disclose the Python version.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import secrets
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse, urlsplit

from .env import AuditEnv
from .generator import load_private

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_EPISODES = BACKEND_ROOT / "episodes"
DEFAULT_STATIC = REPO_ROOT / "frontend" / "dist"
MAX_BODY = 1_000_000
MAX_SESSIONS = 32
SOCKET_TIMEOUT_S = 15
LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}
METRIC_KEYS = ("tp", "fp", "fn", "precision", "recall", "f1", "reward", "inspection_steps", "valid", "termination")


class ApiError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


class Session:
    def __init__(self, key: str, path: Path):
        self.key = key
        self.path = path
        self.env = AuditEnv("train")
        self.done = False
        self.lock = threading.Lock()


class PlaygroundApp:
    def __init__(self, episodes_dir: Path = DEFAULT_EPISODES, static_dir: Path = DEFAULT_STATIC):
        self.episodes_dir = Path(episodes_dir)
        self.static_dir = Path(static_dir)
        index = json.loads((self.episodes_dir / "index.json").read_text(encoding="utf-8"))
        self.catalog: "OrderedDict[str, Path]" = OrderedDict()
        counters: dict = {}
        for e in index["episodes"]:
            n = counters.get(e["split"], 0)
            counters[e["split"]] = n + 1
            self.catalog[f"{e['split']}/{n:02d}"] = self.episodes_dir / e["path"]
        self.sessions: "OrderedDict[str, Session]" = OrderedDict()
        self.lock = threading.Lock()

    def episodes(self) -> list:
        out = []
        for key, path in self.catalog.items():
            m = json.loads((path / "public" / "manifest.json").read_text(encoding="utf-8"))
            out.append(
                {
                    "key": key,
                    "split": key.split("/")[0],
                    "episode_id": m["episode_id"],
                    "company_name": m["company_name"],
                    "period_start": m["period_start"],
                    "period_end": m["period_end"],
                    "base_currency": m["base_currency"],
                    "timezone": m["timezone"],
                    "counts": m["counts"],
                }
            )
        return out

    def reset(self, body) -> dict:
        key = body.get("episode") if isinstance(body, dict) else None
        if not isinstance(key, str) or key not in self.catalog:
            raise ApiError(400, "unknown_episode")
        session = Session(key, self.catalog[key])
        obs, _ = session.env.reset(config={"episode_dir": str(session.path)})
        token = secrets.token_hex(16)
        with self.lock:
            self.sessions[token] = session
            while len(self.sessions) > MAX_SESSIONS:
                self.sessions.popitem(last=False)
        return {"session": token, "observation": obs}

    def _session(self, token) -> Session:
        with self.lock:
            s = self.sessions.get(token) if isinstance(token, str) else None
        if s is None:
            raise ApiError(404, "unknown_session")
        return s

    def step(self, body) -> dict:
        if not isinstance(body, dict) or "action" not in body:
            raise ApiError(400, "bad_request")
        s = self._session(body.get("session"))
        with s.lock:
            obs, reward, terminated, truncated, info = s.env.step(body["action"])
            if terminated or truncated:
                s.done = True
        return {"observation": obs, "reward": reward, "terminated": terminated, "truncated": truncated, "info": info}

    def review(self, token) -> dict:
        s = self._session(token)
        if not s.done:
            raise ApiError(403, "episode_not_finished")
        truth, _ = load_private(s.path)
        g = s.env._grader.result
        matched = {issue_id: idx for idx, issue_id in g["matches"]}
        issues = [
            {
                "type": i["type"],
                "affected_ids": i["affected_ids"],
                "expected_amount_minor": i["expected_amount_minor"],
                "currency": i["currency"],
                "evidence_sets": i["evidence_sets"],
                "status": "found" if i["issue_id"] in matched else "missed",
                "matched_finding": matched.get(i["issue_id"]),
            }
            for i in truth["issues"]
        ]
        used = set(matched.values())
        return {
            "metrics": {k: g[k] for k in METRIC_KEYS},
            "issues": issues,
            "false_positives": [i for i in range(g["n_findings"]) if i not in used],
        }


def _hostname(value: str) -> Optional[str]:
    try:
        return urlsplit("//" + value).hostname
    except ValueError:
        return None


def make_handler(app: PlaygroundApp, allowed_hosts: frozenset = frozenset()):
    allowed = LOCAL_HOSTNAMES | set(allowed_hosts)

    class Handler(BaseHTTPRequestHandler):
        server_version = "AuditDesk/0.1"
        sys_version = ""  # no Python version in the Server header
        timeout = SOCKET_TIMEOUT_S  # slow clients cannot hold a thread forever

        def log_message(self, fmt, *args):  # quiet
            pass

        def _send(self, status: int, data: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, status: int, obj) -> None:
            self._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

        def _guard(self, method: str) -> None:
            raw_host = self.headers.get("Host")  # browsers always send it; bare HTTP/1.0 tools may not
            if raw_host is not None and _hostname(raw_host) not in allowed:
                raise ApiError(403, "forbidden_host")  # DNS rebinding: a foreign name pointing at us
            origin = self.headers.get("Origin")
            if origin is not None and _hostname(urlsplit(origin).netloc) not in allowed:
                raise ApiError(403, "forbidden_origin")  # cross-site page
            if method == "POST":
                ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if ctype != "application/json":  # forces a CORS preflight, which we never grant
                    raise ApiError(415, "json_required")

        def _body(self):
            raw_len = (self.headers.get("Content-Length") or "0").strip()
            if not raw_len.isdigit():
                raise ApiError(400, "bad_length")  # negative or garbage: would read to EOF unbounded
            n = int(raw_len)
            if n > MAX_BODY:
                raise ApiError(413, "too_large")
            raw = self.rfile.read(n) if n else b"null"
            try:
                return json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise ApiError(400, "bad_json") from None

        def _static(self, path: str) -> None:
            root = app.static_dir.resolve()
            try:
                target = (root / unquote(path).lstrip("/")).resolve()
            except (ValueError, OSError):  # e.g. an embedded NUL byte
                target = root / "index.html"
            if not target.is_relative_to(root) or not target.is_file():
                target = root / "index.html"
            if not target.is_file():
                raise ApiError(404, "frontend_not_built")
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype == "application/javascript":
                ctype += "; charset=utf-8"
            self._send(200, target.read_bytes(), ctype)

        def _dispatch(self, method: str) -> None:
            url = urlparse(self.path)
            try:
                self._guard(method)
                if method == "GET" and url.path == "/api/episodes":
                    return self._json(200, app.episodes())
                if method == "GET" and url.path == "/api/review":
                    return self._json(200, app.review(parse_qs(url.query).get("session", [None])[0]))
                if method == "POST" and url.path == "/api/reset":
                    return self._json(200, app.reset(self._body()))
                if method == "POST" and url.path == "/api/step":
                    return self._json(200, app.step(self._body()))
                if url.path.startswith("/api/") or method != "GET":
                    raise ApiError(404, "not_found")
                return self._static(url.path)
            except ApiError as exc:
                self._json(exc.status, {"error": exc.code})
            except Exception:
                self._json(500, {"error": "internal"})

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

    return Handler


def make_server(app: PlaygroundApp, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    extra = frozenset() if host in ("", "0.0.0.0", "::") else frozenset({host})
    server = ThreadingHTTPServer((host, port), make_handler(app, extra))
    server.daemon_threads = True
    return server


def main(argv: Optional[list] = None) -> None:
    ap = argparse.ArgumentParser(description="AuditDesk — play the audit environment in a browser")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--episodes", default=str(DEFAULT_EPISODES))
    ap.add_argument("--static", default=str(DEFAULT_STATIC))
    a = ap.parse_args(argv)
    server = make_server(PlaygroundApp(Path(a.episodes), Path(a.static)), a.host, a.port)
    print(f"AuditDesk: http://{a.host}:{server.server_address[1]}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
