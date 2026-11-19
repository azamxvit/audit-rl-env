# Auditor Playground Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Веб-интерфейс «сыграть за аудитора» (React + TS + Vite, дизайн по образцу NovaPay) поверх существующей среды, с переносом Python-кода в `backend/` и фронта в `frontend/`.

**Architecture:** Stdlib-сервер `backend/src/audit_env/server.py` — тонкая обёртка над `AuditEnv("train")` (`/api/episodes|reset|step|review`) и хост статики `frontend/dist`. Фронт — SPA без роутера; один хук `useEpisode` владеет сессией, бюджетом шагов и кэшем загруженных записей; черновик выводов — хук `useDraft`. Собранный `dist/` коммитится, поэтому `make play`, `make verify` и Docker не требуют Node и сети.

**Tech Stack:** Python 3.11 stdlib (`http.server`), pytest 8.3.4; React 18.3.1, TypeScript 5.6.3, Vite 6.4.6, @vitejs/plugin-react 4.3.4, lucide-react 0.460.0, @fontsource/inter 5.1.0.

Спецификация: `docs/superpowers/specs/2026-11-19-auditor-playground-design.md`.

## Global Constraints

- Ядро среды (`audit_env/*` кроме нового `server.py`) не меняется по логике; `make verify` из корня зелёный после каждой задачи.
- Офлайн: никаких CDN; шрифт и иконки бандлятся; Node не нужен для `make verify`, `make play` и Docker.
- Версии npm точные (без `^`/`~`): react 18.3.1, react-dom 18.3.1, @types/react 18.3.12, @types/react-dom 18.3.1, vite 6.4.6, @vitejs/plugin-react 4.3.4, typescript 5.6.3, lucide-react 0.460.0, @fontsource/inter 5.1.0. `package-lock.json` коммитится.
- Сервер слушает `127.0.0.1:8000` по умолчанию; клиент выбирает эпизод только по ключу `"<split>/<NN>"` из индекса.
- `/api/episodes` не отдаёт число/типы ошибок; `/api/review` → 403 до конца эпизода.
- Название продукта в UI — «AuditDesk»; бренд/логотип NovaPay не используется. Иконки — Lucide.
- Тексты UI на русском. Минимальная ширина макета 1280 px.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## File Structure

```
backend/                                  (git mv из корня)
  pyproject.toml, requirements-dev.txt
  src/audit_env/server.py                 NEW  HTTP API + статика
  tests/test_server.py                    NEW
  scripts/, configs/, episodes/, runs/, tests/ (прочие без изменений)
frontend/                                 NEW
  package.json, package-lock.json, tsconfig.json, vite.config.ts, index.html
  src/main.tsx                            точка входа, шрифты, стили
  src/App.tsx                             каркас, навигация (View), связывание хуков
  src/types.ts                            типы API/наблюдений
  src/api.ts                              fetch-клиент
  src/lib/format.ts                       деньги, даты, метки, ID→таблица
  src/hooks/useEpisode.ts                 сессия, шаги, кэш записей, review
  src/hooks/useDraft.ts                   черновик выводов + форма
  src/styles.css                          токены и все стили
  src/components/Sidebar.tsx  TopBar.tsx  Badge.tsx  KeyValueCard.tsx
  src/components/Toasts.tsx  ActionBar.tsx  RecordDrawer.tsx  FindingForm.tsx  FindingList.tsx
  src/screens/EpisodePicker.tsx  Overview.tsx  Records.tsx  Findings.tsx
  src/screens/CalculatorScreen.tsx  PolicyScreen.tsx  Help.tsx  Review.tsx
  dist/                                   собранный бандл (коммитится)
корень: README.md, DESIGN.md, LICENSE, Makefile, Dockerfile, .dockerignore, .gitignore, docs/
```

---

### Task 1: Перенос Python-кода в `backend/`

**Files:**
- Move: `src/ tests/ scripts/ configs/ episodes/ runs/ pyproject.toml requirements-dev.txt` → `backend/`
- Modify: `backend/pyproject.toml` (убрать `readme`), `Makefile`, `Dockerfile`, `.dockerignore`, `.gitignore`, `README.md`, `DESIGN.md`

**Interfaces:**
- Produces: команды из корня `make verify | test | episodes | check-data | baselines | demo`; рабочий каталог Python — `backend/`, `PYTHONPATH=src` относительно него.

- [ ] **Step 1: Переместить файлы**

```bash
mkdir -p backend
git mv src tests scripts configs episodes runs pyproject.toml requirements-dev.txt backend/
```

- [ ] **Step 2: Убрать ссылку на README из pyproject** (setuptools не принимает путь вне проекта)

В `backend/pyproject.toml` удалить строку `readme = "README.md"`.

- [ ] **Step 3: Переписать корневой `Makefile`**

```make
PYTHON ?= python3
BACKEND := backend
RUN := cd $(BACKEND) && PYTHONPATH=src $(PYTHON)

.PHONY: verify test episodes check-data baselines demo play frontend clean

# One command: generate episodes -> tests -> independent data checks -> 4 baselines (trajectories + report)
verify:
	$(RUN) scripts/verify_all.py

episodes:
	$(RUN) scripts/generate_episodes.py

test:
	$(RUN) -m pytest -q

check-data:
	$(RUN) scripts/verify.py

baselines:
	$(RUN) scripts/run_baselines.py

demo:
	$(RUN) scripts/demo.py 4

# Auditor Playground: http://127.0.0.1:8000 (serves the committed frontend/dist)
play:
	$(RUN) -m audit_env.server

# Rebuild frontend/dist (needs Node + network for npm ci)
frontend:
	cd frontend && npm ci && npm run build

clean:
	rm -rf $(BACKEND)/.pytest_cache
```

- [ ] **Step 4: Обновить `Dockerfile`**

```dockerfile
# Offline verification image: docker build -t audit-env . && docker run --network none audit-env
FROM python:3.11.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src

WORKDIR /app
# test-only dependency, pinned; the environment core is stdlib-only
COPY backend/requirements-dev.txt backend/requirements-dev.txt
RUN pip install --no-cache-dir -r backend/requirements-dev.txt

COPY . .
RUN useradd --create-home auditor && chown -R auditor /app
USER auditor
WORKDIR /app/backend

CMD ["python", "scripts/verify_all.py"]
```

- [ ] **Step 5: Обновить `.dockerignore` и `.gitignore`**

`.dockerignore`:
```
.git
backend/runs
**/__pycache__
**/.pytest_cache
*.egg-info
frontend/node_modules
```

`.gitignore` — добавить строку `frontend/node_modules/`.

- [ ] **Step 6: Поправить пути в документации**

```bash
sed -i '' -e 's#(src/audit_env#(backend/src/audit_env#g' -e 's#`src/audit_env#`backend/src/audit_env#g' \
  -e 's#runs/report.md#backend/runs/report.md#g' -e 's#`configs/`#`backend/configs/`#g' \
  -e 's#`episodes/`#`backend/episodes/`#g' -e 's#PYTHONPATH=src python3 scripts/verify_all.py#cd backend \&\& PYTHONPATH=src python3 scripts/verify_all.py#g' \
  README.md DESIGN.md
```
Затем вручную заменить блок «Состав репозитория» в `README.md` на:
```
backend/            Python: src/audit_env (среда + HTTP-сервер), tests/, scripts/, configs/, episodes/, runs/
frontend/           React + TS + Vite (Auditor Playground); собранный dist/ в репозитории
docs/               case.pdf, спецификации и планы
```
и проверить `grep -n "src/\|runs/\|configs/\|episodes/" README.md DESIGN.md` — все пути указывают внутрь `backend/`.

- [ ] **Step 7: Прогнать полную проверку**

Run: `make verify`
Expected: все 4 шага `OK`, `data verification: 20/20 episodes OK`, `git status --short backend/episodes` пусто (эпизоды байт-в-байт те же).

- [ ] **Step 8: Commit**

```bash
git add -A Makefile Dockerfile .dockerignore .gitignore README.md DESIGN.md backend
git commit -m "Move Python environment into backend/

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: HTTP-сервер `audit_env.server`

**Files:**
- Create: `backend/src/audit_env/server.py`
- Test: `backend/tests/test_server.py`

**Interfaces:**
- Consumes: `AuditEnv` (`backend/src/audit_env/env.py`), `load_private(dir) -> (truth, provenance)` (`generator.py`), `Grader.result` dict с ключами `tp, fp, fn, precision, recall, f1, reward, inspection_steps, valid, termination, n_findings, matches: [[finding_index, issue_id], ...]`.
- Produces (HTTP, JSON):
  - `GET /api/episodes -> [{key, split, episode_id, company_name, period_start, period_end, base_currency, timezone, counts}]`
  - `POST /api/reset {episode} -> {session, observation}`
  - `POST /api/step {session, action} -> {observation, reward, terminated, truncated, info}`
  - `GET /api/review?session= -> {metrics: {tp, fp, fn, precision, recall, f1, reward, inspection_steps, valid, termination}, issues: [{type, affected_ids, expected_amount_minor, currency, evidence_sets, status: "found"|"missed", matched_finding: int|null}], false_positives: [int]}`
  - Ошибки: `{error: code}` со статусами 400 (`unknown_episode`, `bad_request`, `bad_json`), 403 (`episode_not_finished`), 404 (`unknown_session`, `not_found`, `frontend_not_built`), 413 (`too_large`), 500 (`internal`).
  - Python: `PlaygroundApp(episodes_dir: Path, static_dir: Path)`, `make_server(app, host, port) -> ThreadingHTTPServer`, `main(argv=None)`.

- [ ] **Step 1: Написать падающие тесты**

`backend/tests/test_server.py`:
```python
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
    assert [step["observation"], step["reward"], step["terminated"], step["truncated"], step["info"]] == \
        json.loads(json.dumps(list(direct)))


def test_review_only_after_end_and_reports_issues(server):
    port, app = server
    _, out = req(port, "POST", "/api/reset", {"episode": "dev/04"})
    sid = out["session"]
    status, body = req(port, "GET", f"/api/review?session={sid}")
    assert status == 403 and body == {"error": "episode_not_finished"}
    from audit_env.generator import load_private
    truth, _ = load_private(app.catalog["dev/04"])
    first = truth["issues"][0]
    finding = {"type": first["type"], "affected_ids": first["affected_ids"],
               "claimed_amount_minor": first["expected_amount_minor"], "currency": first["currency"],
               "evidence_ids": first["evidence_sets"][0], "explanation": "ui"}
    eid = out["observation"]["manifest"]["episode_id"]
    _, step = req(port, "POST", "/api/step", {"session": sid, "action": {
        "tool": "submit", "args": {"episode_id": eid, "findings": [finding, finding]}}})
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
    _, step = req(port, "POST", "/api/step", {"session": out["session"],
                                              "action": {"tool": "list_records", "args": {"table": "invoices"}}})
    blob = json.dumps([out, step])
    for leaked in ("expected_amount_minor", "evidence_sets", "issue_id", "ISS-"):
        assert leaked not in blob


@pytest.mark.parametrize("method,path,body,raw,status,code", [
    ("POST", "/api/reset", {"episode": "../../etc"}, None, 400, "unknown_episode"),
    ("POST", "/api/reset", {"episode": "train/99"}, None, 400, "unknown_episode"),
    ("POST", "/api/step", {"session": "nope", "action": {}}, None, 404, "unknown_session"),
    ("POST", "/api/step", {"session": "nope"}, None, 400, "bad_request"),
    ("POST", "/api/step", None, b"{not json", 400, "bad_json"),
    ("GET", "/api/review?session=nope", None, None, 404, "unknown_session"),
    ("GET", "/api/nothing", None, None, 404, "not_found"),
    ("POST", "/api/nothing", {}, None, 404, "not_found"),
])
def test_api_errors(server, method, path, body, raw, status, code):
    port, _ = server
    got_status, got = req(port, method, path, body, raw)
    assert got_status == status and got == {"error": code}


def test_body_too_large(server):
    import socket
    port, _ = server
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    s.sendall(b"POST /api/step HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
              b"Content-Length: 2000000\r\n\r\n")  # body never sent: the server must refuse before reading it
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
    status, got = req(port, "POST", "/api/step", {"session": first, "action": {"tool": "calculator",
                                                                                "args": {"expression": "1"}}})
    assert status == 404 and len(app.sessions) == 32
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd backend && PYTHONPATH=src python3 -m pytest -q tests/test_server.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'audit_env.server'`.

- [ ] **Step 3: Реализовать сервер**

`backend/src/audit_env/server.py`:
```python
"""Auditor Playground server: JSON API over AuditEnv (train mode) + static host for frontend/dist.

Stdlib only. Run: ``PYTHONPATH=src python -m audit_env.server`` (from backend/) -> http://127.0.0.1:8000
The API is a thin wrapper: /api/step returns exactly what AuditEnv.step returns. Truth is only read
by /api/review, and only after the episode has ended; it is used for open train/dev episodes only.
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
from urllib.parse import parse_qs, unquote, urlparse

from .env import AuditEnv
from .generator import load_private

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_EPISODES = BACKEND_ROOT / "episodes"
DEFAULT_STATIC = REPO_ROOT / "frontend" / "dist"
MAX_BODY = 1_000_000
MAX_SESSIONS = 32
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
            out.append({"key": key, "split": key.split("/")[0], "episode_id": m["episode_id"],
                        "company_name": m["company_name"], "period_start": m["period_start"],
                        "period_end": m["period_end"], "base_currency": m["base_currency"],
                        "timezone": m["timezone"], "counts": m["counts"]})
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
        issues = [{"type": i["type"], "affected_ids": i["affected_ids"],
                   "expected_amount_minor": i["expected_amount_minor"], "currency": i["currency"],
                   "evidence_sets": i["evidence_sets"],
                   "status": "found" if i["issue_id"] in matched else "missed",
                   "matched_finding": matched.get(i["issue_id"])} for i in truth["issues"]]
        used = set(matched.values())
        return {"metrics": {k: g[k] for k in METRIC_KEYS}, "issues": issues,
                "false_positives": [i for i in range(g["n_findings"]) if i not in used]}


def make_handler(app: PlaygroundApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AuditDesk/0.1"

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

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise ApiError(413, "too_large")
            raw = self.rfile.read(n) if n else b"null"
            try:
                return json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise ApiError(400, "bad_json") from None

        def _static(self, path: str) -> None:
            root = app.static_dir.resolve()
            target = (root / unquote(path).lstrip("/")).resolve()
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
    server = ThreadingHTTPServer((host, port), make_handler(app))
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
```

- [ ] **Step 4: Прогнать тесты сервера**

Run: `cd backend && PYTHONPATH=src python3 -m pytest -q tests/test_server.py`
Expected: PASS (все тесты).

- [ ] **Step 5: Прогнать всё**

Run: `make test`
Expected: PASS, число тестов = прежнее + новые.

- [ ] **Step 6: Commit**

```bash
git add backend/src/audit_env/server.py backend/tests/test_server.py
git commit -m "Playground HTTP server: JSON API over AuditEnv + static host

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Каркас фронта (Vite + React + TS, токены, API-клиент, хуки)

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/lib/format.ts`, `frontend/src/hooks/useEpisode.ts`, `frontend/src/hooks/useDraft.ts`, `frontend/src/styles.css`, `frontend/src/App.tsx` (временная заглушка)

**Interfaces:**
- Consumes: HTTP API из Task 2.
- Produces:
  - `types.ts`: `TableName`, `Rec`, `EpisodeInfo`, `Manifest`, `Policy`, `ResetObservation`, `StepObservation`, `StepResponse`, `IssueType`, `Finding`, `ReviewIssue`, `Review`.
  - `api.ts`: `api.episodes()`, `api.reset(key)`, `api.step(session, action)`, `api.review(session)`, `class ApiError {status, code}`.
  - `lib/format.ts`: `formatMinor(minor, currency, exps)`, `parseMajor(text, exp) -> number|null`, `formatDate(iso)`, `periodLabel(start, end)`, `lookupTarget(id)`, `ID_FIELD`, `OWN_KEYS`, `TYPE_LABEL`, `TABLE_LABEL`, `ISSUE_TYPES`.
  - `useEpisode(notify)` → `{session, obs, stepsRemaining, maxSteps, done, busy, tables, cache, calc, review, start, loadMore, open, calculate, submit, leave}`; `Opened = {table: TableName, record: Rec}`.
  - `useDraft(storageKey, baseCurrency, exponent: (ccy) => number)` → `{findings, form, setForm, addTo(kind, id), saveForm(): string|null, remove(i), edit(i), clear()}`; `FormState = {type, affected: string[], evidence: string[], amount: string, currency, explanation, editing: number|null}`.

- [ ] **Step 1: Конфигурация проекта**

`frontend/package.json`:
```json
{
  "name": "auditdesk",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@fontsource/inter": "5.1.0",
    "lucide-react": "0.460.0",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@types/react": "18.3.12",
    "@types/react-dom": "18.3.1",
    "@vitejs/plugin-react": "4.3.4",
    "typescript": "5.6.3",
    "vite": "5.4.11"
  }
}
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "resolveJsonModule": true
  },
  "include": ["src", "vite.config.ts"]
}
```

`frontend/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "dist", emptyOutDir: true },
});
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AuditDesk</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Run: `cd frontend && npm install` (создаёт `package-lock.json`; версии точные).

- [ ] **Step 2: Типы и API-клиент**

`frontend/src/types.ts`:
```ts
export type TableName = "ledger" | "invoices" | "payments" | "fx";
export type Rec = Record<string, any>;
export type IssueType = "duplicate_invoice" | "payment_allocation" | "fx_error" | "period_cutoff";

export interface EpisodeInfo {
  key: string; split: string; episode_id: string; company_name: string;
  period_start: string; period_end: string; base_currency: string; timezone: string;
  counts: Record<string, number>;
}
export interface Manifest {
  schema_version: string; env_version: string; episode_id: string; company_name: string;
  base_currency: string; period_start: string; period_end: string; timezone: string;
  counts: Record<string, number>; rounding: { mode: string; scope: string };
}
export interface Policy {
  functional_currency: string; ledger_currency: string;
  period: { start: string; end: string; timezone: string; membership: string };
  revenue_recognition: string;
  fx: { direction: string; rate_date: string; fallback: string; conversion: string };
  rounding: { mode: string; scope: string };
  payments: { application: string; carrying_amount: string; fx_difference: string; refunds: string };
  accounts: Record<string, string>;
  currency_exponents: Record<string, number>;
}
export interface ResetObservation {
  task: string; manifest: Manifest; policy: Policy;
  tables: Record<TableName, { id_field: string; count: number }>;
  tools: unknown[]; max_steps: number; steps_remaining: number;
}
export interface StepObservation {
  tool: string | null; ok: boolean; result: any;
  error: { code: string; message: string } | null; steps_remaining: number;
}
export interface StepResponse {
  observation: StepObservation; reward: number; terminated: boolean; truncated: boolean;
  info: Record<string, unknown>;
}
export interface Finding {
  type: IssueType; affected_ids: string[]; claimed_amount_minor: number; currency: string;
  evidence_ids: string[]; explanation: string;
}
export interface ReviewIssue {
  type: IssueType; affected_ids: string[]; expected_amount_minor: number; currency: string;
  evidence_sets: string[][]; status: "found" | "missed"; matched_finding: number | null;
}
export interface Review {
  metrics: { tp: number; fp: number; fn: number; precision: number; recall: number; f1: number;
             reward: number; inspection_steps: number; valid: boolean; termination: string };
  issues: ReviewIssue[]; false_positives: number[];
}
```

`frontend/src/api.ts`:
```ts
import type { EpisodeInfo, ResetObservation, Review, StepResponse } from "./types";

export class ApiError extends Error {
  constructor(public status: number, public code: string) { super(code); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, (body as { error?: string }).error ?? "http_error");
  return body as T;
}

export const api = {
  episodes: () => call<EpisodeInfo[]>("/api/episodes"),
  reset: (episode: string) =>
    call<{ session: string; observation: ResetObservation }>("/api/reset", {
      method: "POST", body: JSON.stringify({ episode }) }),
  step: (session: string, action: unknown) =>
    call<StepResponse>("/api/step", { method: "POST", body: JSON.stringify({ session, action }) }),
  review: (session: string) => call<Review>(`/api/review?session=${encodeURIComponent(session)}`),
};
```

- [ ] **Step 3: Форматирование**

`frontend/src/lib/format.ts`:
```ts
import type { IssueType, TableName } from "../types";

export const ISSUE_TYPES: IssueType[] = ["duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff"];
export const TYPE_LABEL: Record<IssueType, string> = {
  duplicate_invoice: "Дубль счёта",
  payment_allocation: "Распределение платежа",
  fx_error: "Ошибка курса",
  period_cutoff: "Отнесение к периоду",
};
export const TABLE_LABEL: Record<TableName, string> = {
  ledger: "Главная книга", invoices: "Счета", payments: "Платежи", fx: "Курсы FX",
};
export const ID_FIELD: Record<TableName, string> = {
  ledger: "row_id", invoices: "invoice_id", payments: "payment_id", fx: "rate_id",
};
export const OWN_KEYS: Record<TableName, string[]> = {
  ledger: ["row_id"], invoices: ["invoice_id", "doc_id"], payments: ["payment_id", "doc_id"], fx: ["rate_id"],
};
const PREFIX: Record<string, TableName> = { LR: "ledger", INV: "invoices", PAY: "payments", FXR: "fx" };

export function lookupTarget(id: string): { kind: "record"; table: TableName } | { kind: "document" } | null {
  const prefix = id.trim().split("-")[0].toUpperCase();
  if (prefix === "DOC") return { kind: "document" };
  const table = PREFIX[prefix];
  return table ? { kind: "record", table } : null;
}

export function formatMinor(minor: number, currency: string, exps: Record<string, number>): string {
  const e = exps[currency] ?? 2;
  const a = Math.abs(minor);
  const major = Math.floor(a / 10 ** e).toLocaleString("ru-RU");
  const frac = e ? "," + String(a % 10 ** e).padStart(e, "0") : "";
  return `${minor < 0 ? "−" : ""}${major}${frac} ${currency}`;
}

/** "1 234,56" | "1234.56" -> minor units; null if not a valid non-negative amount for this exponent. */
export function parseMajor(text: string, exp: number): number | null {
  const t = text.replace(/\s/g, "").replace(",", ".");
  if (!/^\d+(\.\d+)?$/.test(t)) return null;
  const [int, frac = ""] = t.split(".");
  if (frac.length > exp) return null;
  const minor = Number(int) * 10 ** exp + Number(frac.padEnd(exp, "0") || "0");
  return Number.isSafeInteger(minor) ? minor : null;
}

export function formatDate(iso: string): string {
  const [d] = iso.split("T");
  const [y, m, day] = d.split("-");
  return `${day}.${m}.${y}`;
}

export function formatTimestamp(iso: string): string {
  const [d, rest = ""] = iso.split("T");
  return `${formatDate(d)} ${rest.slice(0, 5)} (${rest.slice(8) || "+00:00"})`;
}

export function periodLabel(start: string, end: string): string {
  return `${formatDate(start)} – ${formatDate(end)}`;
}
```

- [ ] **Step 4: Хуки состояния**

`frontend/src/hooks/useEpisode.ts`:
```ts
import { useCallback, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Finding, Rec, ResetObservation, Review, StepResponse, TableName } from "../types";
import { OWN_KEYS, lookupTarget } from "../lib/format";

export interface Opened { table: TableName; record: Rec }
export interface TableState { rows: Rec[]; next: string | null; started: boolean }
export interface CalcEntry { expr: string; value: string | null; error: string | null }

const emptyTables = (): Record<TableName, TableState> => ({
  ledger: { rows: [], next: null, started: false },
  invoices: { rows: [], next: null, started: false },
  payments: { rows: [], next: null, started: false },
  fx: { rows: [], next: null, started: false },
});

export function useEpisode(notify: (msg: string) => void) {
  const [session, setSession] = useState<string | null>(null);
  const [obs, setObs] = useState<ResetObservation | null>(null);
  const [stepsRemaining, setSteps] = useState(0);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [tables, setTables] = useState(emptyTables);
  const [cache, setCache] = useState<Record<string, Opened>>({});
  const [calc, setCalc] = useState<CalcEntry[]>([]);
  const [review, setReview] = useState<Review | null>(null);
  const sessionRef = useRef<string | null>(null);
  const doneRef = useRef(false);
  const tablesRef = useRef(tables);
  tablesRef.current = tables;
  const cacheRef = useRef(cache);
  cacheRef.current = cache;

  const remember = useCallback((table: TableName, recs: Rec[]) => {
    setCache((c) => {
      const next = { ...c };
      for (const r of recs) for (const k of OWN_KEYS[table]) if (typeof r[k] === "string") next[r[k]] = { table, record: r };
      return next;
    });
  }, []);

  const step = useCallback(async (action: unknown): Promise<StepResponse | null> => {
    const s = sessionRef.current;
    if (!s || doneRef.current) return null;
    setBusy(true);
    try {
      const r = await api.step(s, action);
      setSteps(r.observation.steps_remaining);
      if (!r.observation.ok && r.observation.error) notify(`${r.observation.error.code}: ${r.observation.error.message}`);
      if (r.terminated || r.truncated) {
        doneRef.current = true;
        setDone(true);
        setReview(await api.review(s));
      }
      return r;
    } catch (e) {
      notify(e instanceof ApiError ? `Сервер: ${e.code}` : "Сервер недоступен");
      return null;
    } finally {
      setBusy(false);
    }
  }, [notify]);

  const start = useCallback(async (key: string) => {
    const r = await api.reset(key);
    sessionRef.current = r.session;
    doneRef.current = false;
    setSession(r.session);
    setObs(r.observation);
    setSteps(r.observation.steps_remaining);
    setDone(false);
    setTables(emptyTables());
    setCache({});
    setCalc([]);
    setReview(null);
  }, []);

  const leave = useCallback(() => {
    sessionRef.current = null;
    setSession(null);
    setObs(null);
    setReview(null);
  }, []);

  const loadMore = useCallback(async (table: TableName) => {
    const t = tablesRef.current[table];
    if (t.started && !t.next) return;
    const args: Record<string, unknown> = { table, limit: 50 };
    if (t.next) args.cursor = t.next;
    const r = await step({ tool: "list_records", args });
    if (!r || !r.observation.ok) return;
    const res = r.observation.result as { records: Rec[]; next_cursor: string | null };
    setTables((all) => ({ ...all, [table]: { rows: [...all[table].rows, ...res.records], next: res.next_cursor, started: true } }));
    remember(table, res.records);
  }, [step, remember]);

  const open = useCallback(async (id: string): Promise<Opened | null> => {
    const key = id.trim();
    if (cacheRef.current[key]) return cacheRef.current[key];
    const target = lookupTarget(key);
    if (!target) { notify("Неизвестный формат ID — шаг не потрачен"); return null; }
    const r = target.kind === "document"
      ? await step({ tool: "get_document", args: { doc_id: key } })
      : await step({ tool: "get_record", args: { table: target.table, id: key } });
    if (!r || !r.observation.ok) return null;
    let opened: Opened;
    if (target.kind === "document") {
      const res = r.observation.result as { doc_type: string; document: Rec };
      opened = { table: res.doc_type === "invoice" ? "invoices" : "payments", record: res.document };
    } else {
      opened = { table: target.table, record: r.observation.result as Rec };
    }
    remember(opened.table, [opened.record]);
    return opened;
  }, [step, remember, notify]);

  const calculate = useCallback(async (expr: string) => {
    const r = await step({ tool: "calculator", args: { expression: expr } });
    if (!r) return;
    const o = r.observation;
    setCalc((c) => [{ expr, value: o.ok ? String(o.result.value) : null, error: o.ok ? null : o.error?.message ?? "error" }, ...c]);
  }, [step]);

  const submit = useCallback(async (findings: Finding[]) => {
    if (!obs) return;
    await step({ tool: "submit", args: { episode_id: obs.manifest.episode_id, findings } });
  }, [step, obs]);

  return {
    session, obs, stepsRemaining, maxSteps: obs?.max_steps ?? 100, done, busy, tables, cache, calc, review,
    start, leave, loadMore, open, calculate, submit,
  };
}

export type EpisodeApi = ReturnType<typeof useEpisode>;
```

`frontend/src/hooks/useDraft.ts`:
```ts
import { useCallback, useEffect, useState } from "react";
import type { Finding, IssueType } from "../types";
import { parseMajor } from "../lib/format";

export interface FormState {
  type: IssueType; affected: string[]; evidence: string[]; amount: string; currency: string;
  explanation: string; editing: number | null;
}

const blank = (currency: string): FormState => ({
  type: "duplicate_invoice", affected: [], evidence: [], amount: "", currency, explanation: "", editing: null,
});

function load(key: string): Finding[] {
  try { const raw = localStorage.getItem(key); return raw ? (JSON.parse(raw) as Finding[]) : []; } catch { return []; }
}

export function useDraft(storageKey: string, baseCurrency: string, exponent: (ccy: string) => number) {
  const [findings, setFindings] = useState<Finding[]>(() => load(storageKey));
  const [form, setForm] = useState<FormState>(() => blank(baseCurrency));

  useEffect(() => { setFindings(load(storageKey)); setForm(blank(baseCurrency)); }, [storageKey, baseCurrency]);
  useEffect(() => { try { localStorage.setItem(storageKey, JSON.stringify(findings)); } catch { /* storage unavailable */ } },
    [storageKey, findings]);

  const addTo = useCallback((kind: "affected" | "evidence", id: string) => {
    setForm((f) => (f[kind].includes(id) || f[kind].length >= 10 ? f : { ...f, [kind]: [...f[kind], id] }));
  }, []);

  /** Returns an error message, or null on success. */
  const saveForm = useCallback((): string | null => {
    const cur = form.currency.trim().toUpperCase();
    if (!form.affected.length) return "Добавьте хотя бы один affected ID";
    if (!/^[A-Z]{3}$/.test(cur)) return "Валюта — три буквы";
    const minor = parseMajor(form.amount, exponent(cur));
    if (minor === null) return "Сумма: неотрицательное число с допустимым числом знаков после запятой";
    const f: Finding = { type: form.type, affected_ids: form.affected, claimed_amount_minor: minor, currency: cur,
                         evidence_ids: form.evidence, explanation: form.explanation.slice(0, 1000) };
    if (form.editing === null && findings.length >= 30) return "Не больше 30 выводов";
    setFindings((all) => (form.editing === null ? [...all, f] : all.map((x, i) => (i === form.editing ? f : x))));
    setForm(blank(baseCurrency));
    return null;
  }, [form, findings.length, baseCurrency, exponent]);

  const remove = useCallback((i: number) => setFindings((all) => all.filter((_, k) => k !== i)), []);
  const edit = useCallback((i: number) => {
    const f = findings[i];
    const e = exponent(f.currency);
    const major = e ? `${Math.floor(f.claimed_amount_minor / 10 ** e)}.${String(f.claimed_amount_minor % 10 ** e).padStart(e, "0")}` : String(f.claimed_amount_minor);
    setForm({ type: f.type, affected: f.affected_ids, evidence: f.evidence_ids, amount: major, currency: f.currency,
              explanation: f.explanation, editing: i });
  }, [findings, exponent]);
  const clear = useCallback(() => { setFindings([]); setForm(blank(baseCurrency)); }, [baseCurrency]);

  return { findings, form, setForm, addTo, saveForm, remove, edit, clear };
}

export type DraftApi = ReturnType<typeof useDraft>;
```

- [ ] **Step 5: Стили (токены по образцу NovaPay)**

`frontend/src/styles.css`:
```css
:root {
  --bg: #ffffff; --sidebar: #f7f8fa; --surface: #ffffff; --surface-2: #fafbfc;
  --border: #e6e8ec; --border-strong: #d5d9e0;
  --text: #111827; --text-2: #374151; --muted: #6b7280; --subtle: #9ca3af;
  --accent: #0e9f9a; --accent-soft: #e6f6f5;
  --danger: #c0262d; --danger-bg: #fdecec; --warn: #b45309; --warn-bg: #fff4e0;
  --success: #15803d; --success-bg: #e7f6ec; --info: #1d4ed8; --info-bg: #eaf0ff;
  --radius: 10px; --radius-sm: 6px;
  --shadow: 0 1px 2px rgba(16, 24, 40, 0.05); --shadow-lg: 0 12px 32px rgba(16, 24, 40, 0.14);
  --mono: "SFMono-Regular", ui-monospace, Menlo, Consolas, monospace;
  font-family: "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 14px; color: var(--text); background: var(--bg);
}
* { box-sizing: border-box; }
body { margin: 0; min-width: 1280px; }
button { font: inherit; cursor: pointer; }
input, select, textarea { font: inherit; color: var(--text); }
.mono { font-family: var(--mono); font-size: 12.5px; }
.muted { color: var(--muted); }
.num { text-align: right; font-variant-numeric: tabular-nums; }

/* shell */
.app { display: grid; grid-template-columns: 248px 1fr; height: 100vh; }
.sidebar { background: var(--sidebar); border-right: 1px solid var(--border); padding: 20px 14px; overflow-y: auto; }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 18px; padding: 0 8px 22px; }
.brand-mark { width: 28px; height: 28px; border-radius: 50%; border: 3px solid var(--accent); display: grid; place-items: center; color: var(--accent); }
.nav-section { font-size: 11px; font-weight: 600; letter-spacing: .06em; color: var(--muted); padding: 14px 8px 6px; text-transform: uppercase; }
.nav-item { display: flex; align-items: center; gap: 10px; width: 100%; padding: 7px 10px; border: 0; background: none; border-radius: 8px; color: var(--text-2); text-align: left; }
.nav-item:hover:not(:disabled) { background: #eef0f3; }
.nav-item.active { background: var(--surface); box-shadow: var(--shadow); border: 1px solid var(--border); color: var(--text); font-weight: 500; }
.nav-item:disabled { color: var(--subtle); cursor: default; }
.nav-sub { padding-left: 30px; }
.nav-count { margin-left: auto; font-size: 12px; color: var(--muted); }
.main { display: flex; flex-direction: column; min-width: 0; }
.topbar { height: 64px; flex: none; display: flex; align-items: center; gap: 16px; padding: 0 32px; border-bottom: 1px solid var(--border); }
.search { display: flex; align-items: center; gap: 8px; width: 380px; height: 38px; border: 1px solid var(--border); border-radius: 8px; padding: 0 12px; color: var(--muted); }
.search input { border: 0; outline: none; flex: 1; background: none; }
.topbar-right { margin-left: auto; display: flex; align-items: center; gap: 14px; }
.budget { display: flex; align-items: center; gap: 8px; font-weight: 500; }
.content { flex: 1; overflow-y: auto; padding: 24px 32px 120px; }
.page { max-width: 1120px; }

/* typography & primitives */
.back { display: inline-flex; align-items: center; gap: 6px; border: 0; background: none; color: var(--text-2); padding: 0; margin-bottom: 18px; }
h1 { font-size: 22px; font-weight: 600; margin: 0 0 10px; }
h2 { font-size: 17px; font-weight: 600; margin: 28px 0 14px; }
.headline { display: flex; align-items: center; gap: 10px; margin-bottom: 22px; }
.headline-big { font-size: 22px; font-weight: 700; }
.headline-big small { font-size: 14px; font-weight: 500; color: var(--muted); margin-left: 4px; }
.badge { display: inline-flex; align-items: center; gap: 4px; height: 22px; padding: 0 8px; border-radius: 6px; font-size: 12px; font-weight: 500; white-space: nowrap; }
.badge.red { background: var(--danger); color: #fff; }
.badge.danger { background: var(--danger-bg); color: var(--danger); }
.badge.warn { background: var(--warn-bg); color: var(--warn); }
.badge.success { background: var(--success-bg); color: var(--success); }
.badge.info { background: var(--info-bg); color: var(--info); }
.badge.neutral { background: #f1f3f5; color: var(--text-2); }
.chip { display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); font-family: var(--mono); font-size: 12px; }
.chip button { border: 0; background: none; padding: 0; color: var(--muted); display: flex; }
.attrs { display: grid; grid-template-columns: repeat(6, 1fr); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 16px 0; margin-bottom: 18px; }
.attrs > div + div { border-left: 1px solid var(--border); padding-left: 18px; }
.attr-label { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin-bottom: 6px; }
.attr-value { font-weight: 500; }
.note { border: 1px solid var(--border); background: var(--surface-2); border-radius: var(--radius-sm); padding: 12px 14px; max-width: 760px; }
.note-title { display: flex; align-items: center; gap: 8px; font-weight: 600; margin-bottom: 8px; }
.note-body { border-left: 2px solid var(--accent); padding-left: 10px; font-style: italic; color: var(--text-2); line-height: 1.5; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.card { border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); padding: 18px; }
.card-title { display: flex; align-items: center; gap: 10px; font-weight: 600; margin-bottom: 14px; }
.kv { display: grid; grid-template-columns: 130px 1fr; row-gap: 12px; column-gap: 12px; font-size: 13px; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; font-weight: 500; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
.btn { display: inline-flex; align-items: center; gap: 8px; height: 34px; padding: 0 14px; border-radius: 8px; border: 1px solid var(--border-strong); background: var(--surface); color: var(--text); font-weight: 500; }
.btn:hover:not(:disabled) { background: #f6f7f9; }
.btn:disabled { color: var(--subtle); background: #f3f4f6; cursor: default; }
.btn.primary { background: var(--text); border-color: var(--text); color: #fff; }
.btn.primary:hover:not(:disabled) { background: #1f2937; }
.btn.small { height: 28px; padding: 0 10px; font-size: 13px; }
.btn.ghost { border-color: transparent; background: none; }
.cost { font-size: 11px; color: var(--muted); font-weight: 500; }
.field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.field label { font-size: 12px; color: var(--muted); }
.input, .field select, .field textarea { border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; background: var(--surface); outline: none; }
.input:focus, .field select:focus, .field textarea:focus { border-color: var(--accent); }
.field textarea { min-height: 80px; resize: vertical; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.row { display: flex; gap: 8px; align-items: center; }
.error-text { color: var(--danger); font-size: 13px; }

/* lists & tables */
.list { display: flex; flex-direction: column; gap: 10px; max-height: 420px; overflow-y: auto; }
.list-item { border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; background: var(--surface); }
.list-item-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.table-wrap { border: 1px solid var(--border); border-radius: var(--radius); overflow: auto; background: var(--surface); }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); font-weight: 600; padding: 10px 12px; border-bottom: 1px solid var(--border); background: var(--surface-2); position: sticky; top: 0; }
td { padding: 9px 12px; border-bottom: 1px solid var(--border); white-space: nowrap; }
tbody tr { cursor: pointer; }
tbody tr:hover { background: #f8fafb; }
tbody tr.selected { background: var(--accent-soft); }
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.empty { padding: 40px; text-align: center; color: var(--muted); }
.link { border: 0; background: none; padding: 0; color: var(--info); font-family: var(--mono); font-size: 12.5px; }
.link:hover { text-decoration: underline; }

/* overlays */
.action-bar { position: fixed; bottom: 24px; left: calc(248px + (100vw - 248px) / 2); transform: translateX(-50%); display: flex; align-items: center; gap: 8px; padding: 8px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow-lg); z-index: 20; }
.action-bar .divider { width: 1px; height: 24px; background: var(--border); }
.menu { position: absolute; bottom: 48px; right: 8px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; box-shadow: var(--shadow-lg); padding: 6px; min-width: 220px; }
.menu button { display: flex; align-items: center; gap: 8px; width: 100%; border: 0; background: none; padding: 8px 10px; border-radius: 6px; text-align: left; }
.menu button:hover { background: #f3f4f6; }
.drawer { position: fixed; top: 0; right: 0; width: 460px; height: 100vh; background: var(--surface); border-left: 1px solid var(--border); box-shadow: var(--shadow-lg); z-index: 30; display: flex; flex-direction: column; }
.drawer-head { display: flex; align-items: center; gap: 10px; padding: 18px 20px; border-bottom: 1px solid var(--border); }
.drawer-body { flex: 1; overflow-y: auto; padding: 18px 20px; }
.drawer-foot { display: flex; gap: 8px; padding: 14px 20px; border-top: 1px solid var(--border); }
.toasts { position: fixed; bottom: 24px; right: 24px; display: flex; flex-direction: column; gap: 8px; z-index: 40; }
.toast { background: var(--text); color: #fff; padding: 10px 14px; border-radius: 8px; box-shadow: var(--shadow-lg); max-width: 380px; font-size: 13px; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(17, 24, 39, .35); display: grid; place-items: center; z-index: 50; }
.modal { background: var(--surface); border-radius: 12px; padding: 22px; width: 420px; box-shadow: var(--shadow-lg); }
.episode-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.episode-card { display: flex; flex-direction: column; gap: 10px; }
.metric-big { font-size: 28px; font-weight: 700; }
pre.json { background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: var(--mono); font-size: 12px; white-space: pre-wrap; word-break: break-all; }
```

- [ ] **Step 6: Точка входа и временный App**

`frontend/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "./styles.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

`frontend/src/App.tsx` (заглушка, заменяется в Task 4):
```tsx
export default function App() {
  return <div className="content">AuditDesk</div>;
}
```

- [ ] **Step 7: Проверить сборку**

Run: `cd frontend && npm run build`
Expected: `tsc` без ошибок (хуки/типы компилируются, хотя ещё не используются — `noUnusedLocals` не трогает экспорты), `dist/index.html` создан.

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html frontend/src
git commit -m "Frontend scaffold: Vite + React + TS, API client, state hooks, design tokens

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Каркас приложения — сайдбар, верхняя панель, выбор эпизода, тосты

**Files:**
- Create: `frontend/src/components/Sidebar.tsx`, `TopBar.tsx`, `Badge.tsx`, `Toasts.tsx`, `frontend/src/screens/EpisodePicker.tsx`, `frontend/src/screens/Help.tsx`
- Modify: `frontend/src/App.tsx` (полная версия; экраны Task 5–7 подключаются через `View`)

**Interfaces:**
- Consumes: `useEpisode`, `useDraft`, `api.episodes`, `TABLE_LABEL`.
- Produces: `type View = {name: "episodes"} | {name: "overview"} | {name: "records"; table: TableName} | {name: "findings"} | {name: "calculator"} | {name: "policy"} | {name: "help"} | {name: "review"}`; `Badge({tone, children})` где `tone: "red"|"danger"|"warn"|"success"|"info"|"neutral"`; `useToasts() -> {toasts, notify}`; `Toasts({toasts})`.

- [ ] **Step 1: Примитивы**

`frontend/src/components/Badge.tsx`:
```tsx
import type { ReactNode } from "react";

export type Tone = "red" | "danger" | "warn" | "success" | "info" | "neutral";

export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
```

`frontend/src/components/Toasts.tsx`:
```tsx
import { useCallback, useState } from "react";

export interface Toast { id: number; text: string }

export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const notify = useCallback((text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  return { toasts, notify };
}

export function Toasts({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="toasts">
      {toasts.map((t) => <div key={t.id} className="toast">{t.text}</div>)}
    </div>
  );
}
```

- [ ] **Step 2: Сайдбар и верхняя панель**

`frontend/src/components/Sidebar.tsx`:
```tsx
import { BookOpen, Calculator, CircleHelp, ClipboardCheck, FolderOpen, House, Layers, ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import type { TableName } from "../types";
import { TABLE_LABEL } from "../lib/format";
import type { View } from "../App";

interface Props { view: View; go: (v: View) => void; hasEpisode: boolean; done: boolean; findings: number }

function Item({ active, disabled, onClick, icon, children, count, sub }:
  { active: boolean; disabled?: boolean; onClick: () => void; icon?: ReactNode; children: ReactNode; count?: number; sub?: boolean }) {
  return (
    <button className={`nav-item${active ? " active" : ""}${sub ? " nav-sub" : ""}`} disabled={disabled} onClick={onClick}>
      {icon}<span>{children}</span>{count !== undefined && <span className="nav-count">{count}</span>}
    </button>
  );
}

const TABLES: TableName[] = ["ledger", "invoices", "payments", "fx"];

export function Sidebar({ view, go, hasEpisode, done, findings }: Props) {
  const off = !hasEpisode;
  return (
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">A</span>AuditDesk</div>
      <div className="nav-section">Расследование</div>
      <Item active={view.name === "overview"} disabled={off} onClick={() => go({ name: "overview" })} icon={<House size={16} />}>Обзор</Item>
      <Item active={false} disabled={off} onClick={() => go({ name: "records", table: "ledger" })} icon={<Layers size={16} />}>
        Записи <ChevronDown size={14} style={{ verticalAlign: "middle" }} />
      </Item>
      {TABLES.map((t) => (
        <Item key={t} sub active={view.name === "records" && view.table === t} disabled={off}
              onClick={() => go({ name: "records", table: t })}>{TABLE_LABEL[t]}</Item>
      ))}
      <Item active={view.name === "findings"} disabled={off} onClick={() => go({ name: "findings" })}
            icon={<ClipboardCheck size={16} />} count={hasEpisode ? findings : undefined}>Выводы</Item>
      {done && <Item active={view.name === "review"} onClick={() => go({ name: "review" })} icon={<ClipboardCheck size={16} />}>Разбор</Item>}
      <div className="nav-section">Инструменты</div>
      <Item active={view.name === "calculator"} disabled={off} onClick={() => go({ name: "calculator" })} icon={<Calculator size={16} />}>Калькулятор</Item>
      <Item active={view.name === "policy"} disabled={off} onClick={() => go({ name: "policy" })} icon={<BookOpen size={16} />}>Политика</Item>
      <div className="nav-section">Эпизоды</div>
      <Item active={view.name === "episodes"} onClick={() => go({ name: "episodes" })} icon={<FolderOpen size={16} />}>Сменить эпизод</Item>
      <div className="nav-section">Справка</div>
      <Item active={view.name === "help"} onClick={() => go({ name: "help" })} icon={<CircleHelp size={16} />}>Как играть</Item>
    </aside>
  );
}
```

`frontend/src/components/TopBar.tsx`:
```tsx
import { Copy, Search } from "lucide-react";
import { useState } from "react";

interface Props {
  enabled: boolean; stepsRemaining: number; maxSteps: number; episodeId?: string;
  onSearch: (id: string) => void; notify: (m: string) => void;
}

function Ring({ value, max }: { value: number; max: number }) {
  const r = 11, c = 2 * Math.PI * r, frac = max ? value / max : 0;
  const color = value < 20 ? "var(--danger)" : "var(--accent)";
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden>
      <circle cx="14" cy="14" r={r} fill="none" stroke="var(--border)" strokeWidth="3" />
      <circle cx="14" cy="14" r={r} fill="none" stroke={color} strokeWidth="3" strokeDasharray={`${c * frac} ${c}`}
              strokeLinecap="round" transform="rotate(-90 14 14)" />
    </svg>
  );
}

export function TopBar({ enabled, stepsRemaining, maxSteps, episodeId, onSearch, notify }: Props) {
  const [q, setQ] = useState("");
  return (
    <header className="topbar">
      <form className="search" onSubmit={(e) => { e.preventDefault(); if (q.trim()) { onSearch(q.trim()); setQ(""); } }}>
        <Search size={16} />
        <input placeholder={enabled ? "Найти запись по ID · 1 шаг" : "Выберите эпизод"} value={q}
               disabled={!enabled} onChange={(e) => setQ(e.target.value)} />
      </form>
      {enabled && episodeId && (
        <div className="topbar-right">
          <div className="budget" title="Оставшийся бюджет шагов">
            <Ring value={stepsRemaining} max={maxSteps} />
            <span>{stepsRemaining}/{maxSteps} шагов</span>
          </div>
          <button className="chip" onClick={() => { navigator.clipboard?.writeText(episodeId); notify("ID эпизода скопирован"); }}>
            <Copy size={12} />{episodeId}
          </button>
        </div>
      )}
    </header>
  );
}
```

- [ ] **Step 3: Экран выбора эпизода и справка**

`frontend/src/screens/EpisodePicker.tsx`:
```tsx
import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { api } from "../api";
import type { EpisodeInfo } from "../types";
import { periodLabel } from "../lib/format";
import { Badge } from "../components/Badge";

export function EpisodePicker({ onStart, notify }: { onStart: (key: string) => Promise<void>; notify: (m: string) => void }) {
  const [episodes, setEpisodes] = useState<EpisodeInfo[] | null>(null);
  useEffect(() => { api.episodes().then(setEpisodes).catch(() => notify("Не удалось загрузить список эпизодов")); }, [notify]);
  return (
    <div className="page">
      <h1>Выберите эпизод</h1>
      <p className="muted">Одна вымышленная компания × один отчётный период. Ошибок может не быть вовсе.</p>
      {!episodes ? <div className="empty">Загрузка…</div> : (["train", "dev"] as const).map((split) => (
        <section key={split}>
          <h2>{split === "train" ? "Обучающие (train)" : "Проверочные (dev)"}</h2>
          <div className="episode-grid">
            {episodes.filter((e) => e.split === split).map((e) => (
              <div key={e.key} className="card episode-card">
                <div className="row"><Badge tone="neutral">{e.key}</Badge><span className="mono muted">{e.episode_id}</span></div>
                <div style={{ fontWeight: 600 }}>{e.company_name}</div>
                <div className="muted">{periodLabel(e.period_start, e.period_end)} · {e.base_currency} · UTC{e.timezone}</div>
                <div className="muted">{e.counts.ledger_rows} проводок · {e.counts.documents} документов</div>
                <button className="btn small" onClick={() => onStart(e.key)}>Начать <ArrowRight size={14} /></button>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
```

`frontend/src/screens/Help.tsx`:
```tsx
export function Help() {
  return (
    <div className="page">
      <h1>Как играть</h1>
      <div className="card" style={{ maxWidth: 760, lineHeight: 1.6 }}>
        <p>Вы — аудитор. У вас <b>100 шагов</b>. Шагом считается каждый вызов среды: страница таблицы
          (до 50 записей), открытие записи по ID, вычисление в калькуляторе и отправка выводов. Ошибочный
          вызов тоже расходует шаг. Награда: <span className="mono">clip(2·F1 − 1 − 0.002·шаги, −1, 1)</span>.</p>
        <p>Бесплатно: фильтр и просмотр уже загруженных записей, политика, черновик выводов.</p>
        <p>Вывод засчитывается, если совпадают тип, набор affected ID, валюта, сумма (±1 минорная единица)
          и среди доказательств есть полный допустимый набор. Сумма — абсолютное искажение в
          функциональной валюте. Повторы и лишние выводы — ложные срабатывания.</p>
        <ul>
          <li><b>Дубль счёта</b>: оба invoice_id; сумма проводки более позднего.</li>
          <li><b>Распределение платежа</b>: [payment_id, invoice_id]; сумма кредита 2200 по этому платежу.</li>
          <li><b>Ошибка курса</b>: [invoice_id] или [payment_id]; |проведено − по курсу политики|.</li>
          <li><b>Отнесение к периоду</b>: [invoice_id]; проведённая сумма.</li>
        </ul>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Полный `App.tsx`** (экраны Task 5–7 пока отсутствуют — их импорты добавляются в соответствующих задачах; в этой задаче остальные `View` рендерят `<Help />`)

`frontend/src/App.tsx`:
```tsx
import { useCallback, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { Toasts, useToasts } from "./components/Toasts";
import { useEpisode, type Opened } from "./hooks/useEpisode";
import { useDraft } from "./hooks/useDraft";
import { EpisodePicker } from "./screens/EpisodePicker";
import { Help } from "./screens/Help";
import type { TableName } from "./types";

export type View =
  | { name: "episodes" } | { name: "overview" } | { name: "records"; table: TableName } | { name: "findings" }
  | { name: "calculator" } | { name: "policy" } | { name: "help" } | { name: "review" };

export default function App() {
  const { toasts, notify } = useToasts();
  const ep = useEpisode(notify);
  const [view, setView] = useState<View>({ name: "episodes" });
  const [opened, setOpened] = useState<Opened | null>(null);
  const exps = ep.obs?.policy.currency_exponents;
  const exponent = useCallback((c: string) => exps?.[c] ?? 2, [exps]);
  const draft = useDraft(`auditdesk:draft:${ep.session ?? "none"}`, ep.obs?.manifest.base_currency ?? "USD", exponent);

  const start = useCallback(async (key: string) => {
    try { await ep.start(key); setOpened(null); setView({ name: "overview" }); } catch { notify("Не удалось начать эпизод"); }
  }, [ep, notify]);
  const openId = useCallback(async (id: string) => { const o = await ep.open(id); if (o) setOpened(o); }, [ep]);
  const go = useCallback((v: View) => { setOpened(null); setView(v); }, []);
  void opened; // rendered by RecordDrawer (Task 6)

  let screen;
  switch (view.name) {
    case "episodes": screen = <EpisodePicker onStart={start} notify={notify} />; break;
    default: screen = <Help />;
  }

  return (
    <div className="app">
      <Sidebar view={view} go={go} hasEpisode={!!ep.obs} done={ep.done} findings={draft.findings.length} />
      <div className="main">
        <TopBar enabled={!!ep.obs && !ep.done} stepsRemaining={ep.stepsRemaining} maxSteps={ep.maxSteps}
                episodeId={ep.obs?.manifest.episode_id} onSearch={openId} notify={notify} />
        <main className="content">{screen}</main>
      </div>
      <Toasts toasts={toasts} />
    </div>
  );
}
```

- [ ] **Step 5: Сборка и ручная проверка**

Run: `cd frontend && npm run build`, затем в другом терминале `make play`, открыть `http://127.0.0.1:8000`.
Expected: сайдбар с секциями, список 10 train + 10 dev эпизодов; «Начать» включает пункты сайдбара и бюджет «100/100 шагов».

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "Frontend shell: sidebar, top bar with budget, episode picker, toasts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Обзор и черновик выводов (форма, список, панель действий)

**Files:**
- Create: `frontend/src/components/KeyValueCard.tsx`, `FindingForm.tsx`, `FindingList.tsx`, `ActionBar.tsx`, `frontend/src/screens/Overview.tsx`, `frontend/src/screens/Findings.tsx`
- Modify: `frontend/src/App.tsx` (подключить экраны и `ActionBar`)

**Interfaces:**
- Consumes: `EpisodeApi`, `DraftApi`, `FormState`, `formatMinor`, `periodLabel`, `TYPE_LABEL`, `ISSUE_TYPES`, `Badge`.
- Produces: `KeyValueCard({icon, title, rows: [string, ReactNode][]})`; `FindingForm({draft})`; `FindingList({draft, exps, readOnly?})`; `ActionBar({count, disabled, onSubmit, onClear, onExport})`; `Overview({ep, draft, notify, onBack})`; `Findings({ep, draft})`.

- [ ] **Step 1: Компоненты**

`frontend/src/components/KeyValueCard.tsx`:
```tsx
import type { ReactNode } from "react";

export function KeyValueCard({ icon, title, rows }: { icon: ReactNode; title: string; rows: [string, ReactNode][] }) {
  return (
    <div className="card">
      <div className="card-title">{icon}{title}</div>
      <dl className="kv">
        {rows.map(([k, v]) => [<dt key={`${k}-k`}>{k}</dt>, <dd key={`${k}-v`}>{v}</dd>])}
      </dl>
    </div>
  );
}
```

`frontend/src/components/FindingForm.tsx`:
```tsx
import { PenLine, Plus, X } from "lucide-react";
import { useState } from "react";
import type { DraftApi } from "../hooks/useDraft";
import type { IssueType } from "../types";
import { ISSUE_TYPES, TYPE_LABEL } from "../lib/format";

function IdChips({ ids, onRemove }: { ids: string[]; onRemove: (id: string) => void }) {
  return (
    <div className="chips">
      {ids.map((id) => <span key={id} className="chip">{id}<button onClick={() => onRemove(id)} aria-label="убрать"><X size={12} /></button></span>)}
      {!ids.length && <span className="muted">пусто — добавляйте из таблиц кнопками «+»</span>}
    </div>
  );
}

function AddId({ onAdd }: { onAdd: (id: string) => void }) {
  const [v, setV] = useState("");
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); if (v.trim()) { onAdd(v.trim()); setV(""); } }}>
      <input className="input mono" style={{ flex: 1 }} placeholder="ID вручную" value={v} onChange={(e) => setV(e.target.value)} />
      <button className="btn small" type="submit"><Plus size={14} /></button>
    </form>
  );
}

export function FindingForm({ draft }: { draft: DraftApi }) {
  const { form, setForm, addTo, saveForm } = draft;
  const [error, setError] = useState<string | null>(null);
  const drop = (kind: "affected" | "evidence") => (id: string) => setForm((f) => ({ ...f, [kind]: f[kind].filter((x) => x !== id) }));
  return (
    <div className="card">
      <div className="card-title"><PenLine size={18} />{form.editing === null ? "Новый вывод" : `Вывод #${form.editing + 1}`}</div>
      <div className="field">
        <label>Тип</label>
        <select value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as IssueType }))}>
          {ISSUE_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
        </select>
      </div>
      <div className="field"><label>Затронутые ID (affected_ids)</label><IdChips ids={form.affected} onRemove={drop("affected")} /><AddId onAdd={(id) => addTo("affected", id)} /></div>
      <div className="field"><label>Доказательства (evidence_ids, ≤ 10)</label><IdChips ids={form.evidence} onRemove={drop("evidence")} /><AddId onAdd={(id) => addTo("evidence", id)} /></div>
      <div className="row">
        <div className="field" style={{ flex: 2 }}>
          <label>Сумма искажения (в мажорных единицах)</label>
          <input className="input" inputMode="decimal" placeholder="1234.56" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} />
        </div>
        <div className="field" style={{ flex: 1 }}>
          <label>Валюта</label>
          <input className="input" maxLength={3} value={form.currency} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))} />
        </div>
      </div>
      <div className="field">
        <label>Пояснение ({form.explanation.length}/1000) — на награду не влияет</label>
        <textarea maxLength={1000} value={form.explanation} onChange={(e) => setForm((f) => ({ ...f, explanation: e.target.value }))} />
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button className="btn primary" onClick={() => setError(saveForm())}>Сохранить</button>
      </div>
    </div>
  );
}
```

`frontend/src/components/FindingList.tsx`:
```tsx
import { ClipboardCheck, Pencil, Trash2 } from "lucide-react";
import type { DraftApi } from "../hooks/useDraft";
import { formatMinor, TYPE_LABEL } from "../lib/format";
import { Badge } from "./Badge";

export function FindingList({ draft, exps, readOnly }: { draft: DraftApi; exps: Record<string, number>; readOnly?: boolean }) {
  return (
    <div className="card">
      <div className="card-title"><ClipboardCheck size={18} />Выводы <span className="muted">({draft.findings.length})</span></div>
      <div className="list">
        {!draft.findings.length && <div className="empty">Черновик пуст. Молчание на чистых книгах — тоже ответ.</div>}
        {draft.findings.map((f, i) => (
          <div key={i} className="list-item">
            <div className="list-item-head">
              <Badge tone="info">{TYPE_LABEL[f.type]}</Badge>
              <span className="muted">#{i + 1}</span>
              <span style={{ marginLeft: "auto", fontWeight: 600 }}>{formatMinor(f.claimed_amount_minor, f.currency, exps)}</span>
              {!readOnly && <>
                <button className="btn ghost small" onClick={() => draft.edit(i)} aria-label="редактировать"><Pencil size={14} /></button>
                <button className="btn ghost small" onClick={() => draft.remove(i)} aria-label="удалить"><Trash2 size={14} /></button>
              </>}
            </div>
            <div className="mono">{f.affected_ids.join(", ")}</div>
            <div className="muted mono" style={{ marginTop: 4 }}>доказательства: {f.evidence_ids.join(", ") || "—"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

`frontend/src/components/ActionBar.tsx`:
```tsx
import { ArrowRightToLine, Check, ChevronDown, Download, Trash2 } from "lucide-react";
import { useState } from "react";

interface Props { count: number; disabled: boolean; onSubmit: () => void; onClear: () => void; onExport: () => void }

export function ActionBar({ count, disabled, onSubmit, onClear, onExport }: Props) {
  const [menu, setMenu] = useState(false);
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <div className="action-bar">
        <button className="btn" disabled>Черновик · {count} <Check size={14} /></button>
        <button className="btn" disabled={disabled} onClick={() => setConfirm(true)}>Отправить выводы <ArrowRightToLine size={14} /></button>
        <span className="divider" />
        <button className="btn ghost" onClick={() => setMenu((m) => !m)}>Ещё <ChevronDown size={14} /></button>
        {menu && (
          <div className="menu" onMouseLeave={() => setMenu(false)}>
            <button onClick={() => { setMenu(false); onExport(); }}><Download size={14} />Экспорт черновика (JSON)</button>
            <button onClick={() => { setMenu(false); onClear(); }} disabled={disabled}><Trash2 size={14} />Очистить черновик</button>
          </div>
        )}
      </div>
      {confirm && (
        <div className="modal-backdrop" onClick={() => setConfirm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ marginTop: 0 }}>Отправить {count} вывод(ов)?</h2>
            <p className="muted">Эпизод завершится, отправка стоит 1 шаг. Повторно отправить нельзя.</p>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setConfirm(false)}>Отмена</button>
              <button className="btn primary" onClick={() => { setConfirm(false); onSubmit(); }}>Отправить</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 2: Экраны «Обзор» и «Выводы»**

`frontend/src/screens/Overview.tsx`:
```tsx
import { ArrowLeft, Copy, Landmark, MessageSquareText, Repeat, Scale } from "lucide-react";
import type { EpisodeApi } from "../hooks/useEpisode";
import type { DraftApi } from "../hooks/useDraft";
import { Badge } from "../components/Badge";
import { KeyValueCard } from "../components/KeyValueCard";
import { FindingForm } from "../components/FindingForm";
import { FindingList } from "../components/FindingList";
import { periodLabel } from "../lib/format";

export function Overview({ ep, draft, notify, onBack }: { ep: EpisodeApi; draft: DraftApi; notify: (m: string) => void; onBack: () => void }) {
  const obs = ep.obs!;
  const m = obs.manifest, p = obs.policy;
  return (
    <div className="page">
      <button className="back" onClick={onBack}><ArrowLeft size={16} />Эпизоды</button>
      <h1>{m.company_name}</h1>
      <div className="headline">
        <span className="headline-big">{periodLabel(m.period_start, m.period_end)}<small>{m.base_currency}</small></span>
        {ep.stepsRemaining < 20 ? <Badge tone="red">осталось {ep.stepsRemaining} шагов</Badge>
                                : <Badge tone="warn">осталось {ep.stepsRemaining} шагов</Badge>}
        <button className="chip" onClick={() => { navigator.clipboard?.writeText(m.episode_id); notify("ID эпизода скопирован"); }}>
          <Copy size={12} />{m.episode_id}
        </button>
      </div>
      <div className="attrs">
        {([["Период", periodLabel(m.period_start, m.period_end)], ["Часовой пояс", `UTC${m.timezone}`],
           ["Функц. валюта", m.base_currency], ["Округление", m.rounding.mode],
           ["Проводок", String(m.counts.ledger_rows)], ["Документов", String(m.counts.documents)]] as const).map(([k, v]) => (
          <div key={k}><div className="attr-label">{k}</div><div className="attr-value">{v}</div></div>
        ))}
      </div>
      <div className="note">
        <div className="note-title"><MessageSquareText size={16} color="var(--accent)" />Задание:</div>
        <div className="note-body">“{obs.task}”</div>
      </div>
      <h2>Сводка политики</h2>
      <div className="cards">
        <KeyValueCard icon={<Landmark size={18} />} title="Признание выручки" rows={[
          ["Период", `${periodLabel(p.period.start, p.period.end)}`], ["Пояс", `UTC${p.period.timezone}`],
          ["Принадлежность", "локальная дата в поясе компании"], ["Проводка", "Dr 1100 / Cr 4000"]]} />
        <KeyValueCard icon={<Repeat size={18} />} title="Курсы FX" rows={[
          ["Дата курса", "дата документа (локальная)"], ["Выходные", "последний рабочий день"],
          ["Округление", `${p.rounding.mode}, один раз`], ["Счёт разниц", "7900"]]} />
        <KeyValueCard icon={<Scale size={18} />} title="Оплаты и 2200" rows={[
          ["Применение", "по invoice_refs"], ["Без ссылок", "→ 2200"], ["Переплата", "→ 2200 (корректно)"],
          ["Возврат", "Dr 2200 / Cr 1000"]]} />
      </div>
      <div className="two-col">
        <FindingList draft={draft} exps={p.currency_exponents} readOnly={ep.done} />
        {!ep.done && <FindingForm draft={draft} />}
      </div>
    </div>
  );
}
```

`frontend/src/screens/Findings.tsx`:
```tsx
import type { EpisodeApi } from "../hooks/useEpisode";
import type { DraftApi } from "../hooks/useDraft";
import { FindingForm } from "../components/FindingForm";
import { FindingList } from "../components/FindingList";

export function Findings({ ep, draft }: { ep: EpisodeApi; draft: DraftApi }) {
  return (
    <div className="page">
      <h1>Выводы</h1>
      <p className="muted">Черновик бесплатен. Шагом станет только отправка.</p>
      <div className="two-col">
        <FindingList draft={draft} exps={ep.obs!.policy.currency_exponents} readOnly={ep.done} />
        {!ep.done && <FindingForm draft={draft} />}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Подключить в `App.tsx`**

Добавить импорты:
```tsx
import { ActionBar } from "./components/ActionBar";
import { Overview } from "./screens/Overview";
import { Findings } from "./screens/Findings";
```
Добавить ветки в `switch (view.name)`:
```tsx
    case "overview": screen = ep.obs ? <Overview ep={ep} draft={draft} notify={notify} onBack={() => go({ name: "episodes" })} /> : null; break;
    case "findings": screen = ep.obs ? <Findings ep={ep} draft={draft} /> : null; break;
```
Добавить функцию экспорта и панель после `<main>` внутри `.main`:
```tsx
  const exportDraft = useCallback(() => {
    const blob = new Blob([JSON.stringify({ episode_id: ep.obs?.manifest.episode_id, findings: draft.findings }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `findings-${ep.obs?.manifest.episode_id ?? "draft"}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }, [ep.obs, draft.findings]);
```
```tsx
        {ep.obs && !ep.done && view.name !== "episodes" && view.name !== "help" && (
          <ActionBar count={draft.findings.length} disabled={ep.busy} onClear={draft.clear} onExport={exportDraft}
                     onSubmit={async () => { await ep.submit(draft.findings); setView({ name: "review" }); }} />
        )}
```
(Строку `void opened;` пока оставить — её удаляет Task 6.)

- [ ] **Step 4: Сборка и ручная проверка**

Run: `cd frontend && npm run build`, `make play`.
Expected: «Обзор» как на референсе (шапка, бейджи, строка атрибутов, «Задание», 3 карточки, две колонки); сохранение вывода с пустыми affected показывает ошибку; валидный вывод появляется в списке и переживает перезагрузку страницы в рамках сессии.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "Overview screen, findings draft and floating action bar

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Записи, карточка записи, поиск, калькулятор, политика

**Files:**
- Create: `frontend/src/components/RecordDrawer.tsx`, `frontend/src/screens/Records.tsx`, `frontend/src/screens/CalculatorScreen.tsx`, `frontend/src/screens/PolicyScreen.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `EpisodeApi.{tables, loadMore, open, cache, calc, calculate, busy, done}`, `DraftApi.addTo`, `Opened`, `formatMinor`, `formatTimestamp`, `ID_FIELD`, `TABLE_LABEL`.
- Produces: `RecordDrawer({opened, exps, accounts, readOnly, cached: (id) => boolean, onOpen(id), onAdd(kind, id), onClose})`; `Records({table, ep, selected?, onSelect(opened)})`; `CalculatorScreen({ep})`; `PolicyScreen({ep})`.

- [ ] **Step 1: Карточка записи**

`frontend/src/components/RecordDrawer.tsx`:
```tsx
import { FileText, Plus, X } from "lucide-react";
import type { Opened } from "../hooks/useEpisode";
import { ID_FIELD, TABLE_LABEL, formatMinor } from "../lib/format";

const LINK_FIELDS = new Set(["row_id", "entry_id", "invoice_id", "payment_id", "doc_id", "rate_id"]);
const MONEY_FIELDS = new Set(["debit_minor", "credit_minor", "total_minor", "amount_minor", "unit_price_minor"]);

interface Props {
  opened: Opened; exps: Record<string, number>; accounts: Record<string, string>; readOnly: boolean;
  cached: (id: string) => boolean; onOpen: (id: string) => void; onAdd: (kind: "affected" | "evidence", id: string) => void; onClose: () => void;
}

export function RecordDrawer({ opened, exps, accounts, readOnly, cached, onOpen, onAdd, onClose }: Props) {
  const { table, record } = opened;
  const id = record[ID_FIELD[table]] as string;
  const ccy = (record.currency as string) ?? "";
  const value = (k: string, v: unknown) => {
    if (v === null || v === undefined) return <span className="muted">null</span>;
    if (MONEY_FIELDS.has(k) && typeof v === "number") return <span className="mono">{v} <span className="muted">({formatMinor(v, ccy, exps)})</span></span>;
    if (k === "account") return <span>{String(v)} <span className="muted">· {accounts[String(v)] ?? ""}</span></span>;
    if (typeof v === "string" && LINK_FIELDS.has(k) && v !== id && k !== "entry_id")
      return <button className="link" onClick={() => onOpen(v)}>{v}{!cached(v) && <span className="cost"> · 1 шаг</span>}</button>;
    if (typeof v === "object") return <pre className="json">{JSON.stringify(v, null, 2)}</pre>;
    return <span className={typeof v === "string" && v.includes("-") ? "mono" : ""}>{String(v)}</span>;
  };
  return (
    <aside className="drawer">
      <div className="drawer-head">
        <FileText size={18} />
        <div><div className="muted" style={{ fontSize: 12 }}>{TABLE_LABEL[table]}</div><div className="mono" style={{ fontWeight: 600 }}>{id}</div></div>
        <button className="btn ghost small" style={{ marginLeft: "auto" }} onClick={onClose} aria-label="закрыть"><X size={16} /></button>
      </div>
      <div className="drawer-body">
        <dl className="kv">
          {Object.entries(record).map(([k, v]) => [<dt key={`${k}-k`} className="mono">{k}</dt>, <dd key={`${k}-v`}>{value(k, v)}</dd>])}
        </dl>
      </div>
      {!readOnly && (
        <div className="drawer-foot">
          <button className="btn small" onClick={() => onAdd("affected", table === "ledger" || table === "fx" ? id : (record[ID_FIELD[table]] as string))}><Plus size={14} />в affected</button>
          <button className="btn small" onClick={() => onAdd("evidence", (record.doc_id as string) ?? id)}><Plus size={14} />в доказательства</button>
        </div>
      )}
    </aside>
  );
}
```

- [ ] **Step 2: Таблицы**

`frontend/src/screens/Records.tsx`:
```tsx
import { Download, Search } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import type { EpisodeApi, Opened } from "../hooks/useEpisode";
import type { Rec, TableName } from "../types";
import { Badge } from "../components/Badge";
import { ID_FIELD, TABLE_LABEL, formatMinor, formatTimestamp } from "../lib/format";

type Col = { title: string; render: (r: Rec) => ReactNode; num?: boolean };

function columns(table: TableName, exps: Record<string, number>): Col[] {
  const money = (field: string) => (r: Rec) => (r[field] ? formatMinor(r[field], r.currency, exps) : <span className="muted">—</span>);
  const id = (field: string) => (r: Rec) => (r[field] ? <span className="mono">{r[field]}</span> : <span className="muted">null</span>);
  switch (table) {
    case "ledger": return [
      { title: "row_id", render: id("row_id") }, { title: "Время", render: (r) => formatTimestamp(r.timestamp) },
      { title: "Счёт", render: (r) => <Badge tone="neutral">{r.account}</Badge> },
      { title: "Дебет", render: money("debit_minor"), num: true }, { title: "Кредит", render: money("credit_minor"), num: true },
      { title: "entity_id", render: id("entity_id") }, { title: "invoice_id", render: id("invoice_id") },
      { title: "payment_id", render: id("payment_id") }, { title: "entry_id", render: id("entry_id") }];
    case "invoices": return [
      { title: "doc_id", render: id("doc_id") }, { title: "invoice_id", render: id("invoice_id") },
      { title: "entity_id", render: id("entity_id") }, { title: "Выставлен", render: (r) => formatTimestamp(r.issued_at) },
      { title: "Срок", render: (r) => formatTimestamp(r.due_at) }, { title: "Сумма", render: money("total_minor"), num: true },
      { title: "Строк", render: (r) => r.line_items.length, num: true }];
    case "payments": return [
      { title: "doc_id", render: id("doc_id") }, { title: "payment_id", render: id("payment_id") },
      { title: "Вид", render: (r) => <Badge tone={r.kind === "refund" ? "warn" : "neutral"}>{r.kind}</Badge> },
      { title: "Время", render: (r) => formatTimestamp(r.timestamp) }, { title: "entity_id", render: id("entity_id") },
      { title: "Сумма", render: money("amount_minor"), num: true },
      { title: "Ссылки", render: (r) => (r.invoice_refs ? r.invoice_refs.map((x: Rec) => x.invoice_id).join(", ") : <span className="muted">null</span>) }];
    case "fx": return [
      { title: "rate_id", render: id("rate_id") }, { title: "Дата", render: (r) => r.date },
      { title: "Пара", render: (r) => `${r.source_currency} → ${r.target_currency}` },
      { title: "Курс", render: (r) => <span className="mono">{r.rate}</span>, num: true }];
  }
}

export function Records({ table, ep, selected, onSelect }: { table: TableName; ep: EpisodeApi; selected?: string; onSelect: (o: Opened) => void }) {
  const [filter, setFilter] = useState("");
  const t = ep.tables[table];
  const total = ep.obs!.tables[table].count;
  const cols = useMemo(() => columns(table, ep.obs!.policy.currency_exponents), [table, ep.obs]);
  const rows = useMemo(() => (filter ? t.rows.filter((r) => JSON.stringify(r).toLowerCase().includes(filter.toLowerCase())) : t.rows), [t.rows, filter]);
  const canLoad = !ep.done && (!t.started || !!t.next);
  return (
    <div className="page" style={{ maxWidth: "none" }}>
      <h1>{TABLE_LABEL[table]}</h1>
      <div className="toolbar">
        <div className="search" style={{ width: 320 }}>
          <Search size={16} /><input placeholder="Фильтр по загруженным · бесплатно" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <span className="muted">Загружено {t.rows.length} из {total}</span>
        <button className="btn" style={{ marginLeft: "auto" }} disabled={!canLoad || ep.busy} onClick={() => ep.loadMore(table)}>
          <Download size={14} />{t.started ? "Загрузить ещё 50" : "Загрузить первые 50"} <span className="cost">· 1 шаг</span>
        </button>
      </div>
      <div className="table-wrap">
        {!t.rows.length ? <div className="empty">Записи ещё не загружены. Каждая страница — 1 шаг.</div> : (
          <table>
            <thead><tr>{cols.map((c) => <th key={c.title} className={c.num ? "num" : ""}>{c.title}</th>)}</tr></thead>
            <tbody>
              {rows.map((r) => {
                const id = r[ID_FIELD[table]];
                return (
                  <tr key={id} className={selected === id ? "selected" : ""} onClick={() => onSelect({ table, record: r })}>
                    {cols.map((c) => <td key={c.title} className={c.num ? "num" : ""}>{c.render(r)}</td>)}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Калькулятор и политика**

`frontend/src/screens/CalculatorScreen.tsx`:
```tsx
import { Calculator } from "lucide-react";
import { useState } from "react";
import type { EpisodeApi } from "../hooks/useEpisode";

export function CalculatorScreen({ ep }: { ep: EpisodeApi }) {
  const [expr, setExpr] = useState("");
  return (
    <div className="page" style={{ maxWidth: 760 }}>
      <h1>Калькулятор</h1>
      <p className="muted">Только арифметика над десятичными числами (Decimal). Каждое вычисление — 1 шаг.</p>
      <form className="card row" onSubmit={(e) => { e.preventDefault(); if (expr.trim()) { ep.calculate(expr.trim()); setExpr(""); } }}>
        <Calculator size={18} />
        <input className="input mono" style={{ flex: 1 }} placeholder="12500.00 * 1.084512" value={expr} onChange={(e) => setExpr(e.target.value)} disabled={ep.done} />
        <button className="btn primary" type="submit" disabled={ep.done || ep.busy}>Вычислить <span className="cost" style={{ color: "#cbd5e1" }}>· 1 шаг</span></button>
      </form>
      <div className="list" style={{ marginTop: 16, maxHeight: "none" }}>
        {ep.calc.map((c, i) => (
          <div key={i} className="list-item row">
            <span className="mono" style={{ flex: 1 }}>{c.expr}</span>
            {c.error ? <span className="error-text">{c.error}</span> : <span className="mono" style={{ fontWeight: 600 }}>= {c.value}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
```

`frontend/src/screens/PolicyScreen.tsx`:
```tsx
import type { EpisodeApi } from "../hooks/useEpisode";

function Section({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-title">{title}</div>
      <dl className="kv" style={{ gridTemplateColumns: "180px 1fr" }}>
        {Object.entries(data).map(([k, v]) => [<dt key={`${k}-k`} className="mono">{k}</dt>,
          <dd key={`${k}-v`} style={{ fontWeight: 400, lineHeight: 1.5 }}>{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>])}
      </dl>
    </div>
  );
}

export function PolicyScreen({ ep }: { ep: EpisodeApi }) {
  const p = ep.obs!.policy;
  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <h1>Политика учёта</h1>
      <p className="muted">policy.json приходит в первом наблюдении — просмотр бесплатный.</p>
      <Section title="Период" data={p.period} />
      <Section title="Признание выручки" data={{ rule: p.revenue_recognition, ledger: p.ledger_currency }} />
      <Section title="Курсы FX" data={p.fx} />
      <Section title="Оплаты" data={p.payments} />
      <Section title="Округление" data={p.rounding} />
      <Section title="План счетов" data={p.accounts} />
      <Section title="Разрядность валют" data={p.currency_exponents} />
    </div>
  );
}
```

- [ ] **Step 4: Подключить в `App.tsx`**

Импорты:
```tsx
import { RecordDrawer } from "./components/RecordDrawer";
import { Records } from "./screens/Records";
import { CalculatorScreen } from "./screens/CalculatorScreen";
import { PolicyScreen } from "./screens/PolicyScreen";
```
Ветки `switch`:
```tsx
    case "records": screen = ep.obs ? <Records table={view.table} ep={ep} onSelect={setOpened}
        selected={opened && opened.table === view.table ? String(opened.record[ID_FIELD[view.table]]) : undefined} /> : null; break;
    case "calculator": screen = ep.obs ? <CalculatorScreen ep={ep} /> : null; break;
    case "policy": screen = ep.obs ? <PolicyScreen ep={ep} /> : null; break;
```
(добавить `import { ID_FIELD } from "./lib/format";` и удалить строку `void opened;`). После `<Toasts>`:
```tsx
      {opened && ep.obs && (
        <RecordDrawer opened={opened} exps={ep.obs.policy.currency_exponents} accounts={ep.obs.policy.accounts}
                      readOnly={ep.done} cached={(id) => !!ep.cache[id]} onOpen={openId}
                      onAdd={(kind, id) => { draft.addTo(kind, id); notify(`${id} → ${kind === "affected" ? "affected" : "доказательства"}`); }}
                      onClose={() => setOpened(null)} />
      )}
```

- [ ] **Step 5: Сборка и ручная проверка**

Run: `cd frontend && npm run build`, `make play`.
Expected: «Загрузить первые 50» уменьшает бюджет на 1 и показывает таблицу; фильтр не тратит шаги; клик по строке открывает карточку; ссылка на незагруженный ID подписана «· 1 шаг» и открывается через `get_record`; поиск в верхней панели по `DOC-…` вызывает `get_document`; калькулятор показывает результат и ошибку `calculator_error` тостом.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "Records tables, record drawer, ID search, calculator and policy screens

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Экран «Разбор», финальная сборка, документация

**Files:**
- Create: `frontend/src/screens/Review.tsx`, `frontend/dist/**` (сборка)
- Modify: `frontend/src/App.tsx`, `README.md`, `DESIGN.md`

**Interfaces:**
- Consumes: `EpisodeApi.review`, `DraftApi.findings`, `ReviewIssue`, `formatMinor`, `TYPE_LABEL`, `Badge`.
- Produces: `Review({ep, draft, onAgain, onOther})`.

- [ ] **Step 1: Экран разбора**

`frontend/src/screens/Review.tsx`:
```tsx
import { CircleCheck, CircleX, RotateCcw, FolderOpen, ShieldCheck } from "lucide-react";
import type { EpisodeApi } from "../hooks/useEpisode";
import type { DraftApi } from "../hooks/useDraft";
import { Badge } from "../components/Badge";
import { formatMinor, TYPE_LABEL } from "../lib/format";

const TERMINATION: Record<string, string> = { submit: "отправка выводов", step_limit: "исчерпан бюджет шагов", time_limit: "превышено время" };

export function Review({ ep, draft, onAgain, onOther }: { ep: EpisodeApi; draft: DraftApi; onAgain: () => void; onOther: () => void }) {
  const r = ep.review;
  if (!r) return <div className="empty">Разбор загружается…</div>;
  const exps = ep.obs!.policy.currency_exponents;
  const m = r.metrics;
  return (
    <div className="page">
      <h1>Разбор эпизода</h1>
      <div className="headline">
        <span className="headline-big">{m.reward.toFixed(3)}<small>награда</small></span>
        <Badge tone={m.f1 === 1 ? "success" : m.f1 > 0 ? "warn" : "danger"}>F1 {m.f1.toFixed(3)}</Badge>
        <Badge tone="success">TP {m.tp}</Badge><Badge tone="danger">FP {m.fp}</Badge><Badge tone="warn">FN {m.fn}</Badge>
        {!m.valid && <Badge tone="red">неверная структура ответа</Badge>}
      </div>
      <div className="attrs">
        {([["Precision", m.precision.toFixed(3)], ["Recall", m.recall.toFixed(3)], ["Шагов исследования", String(m.inspection_steps)],
           ["Ошибок в эталоне", String(r.issues.length)], ["Выводов отправлено", String(draft.findings.length)],
           ["Завершение", TERMINATION[m.termination] ?? m.termination]] as const).map(([k, v]) => (
          <div key={k}><div className="attr-label">{k}</div><div className="attr-value">{v}</div></div>
        ))}
      </div>
      <h2><ShieldCheck size={18} style={{ verticalAlign: "-3px" }} /> Проверка по эталону</h2>
      {!r.issues.length ? <div className="card">Книги чистые: правильный ответ — пустой список выводов.</div> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Статус</th><th>Тип</th><th>Affected</th><th className="num">Ожидалось</th><th className="num">Ваша сумма</th><th>Допустимые доказательства</th></tr></thead>
            <tbody>
              {r.issues.map((i, k) => {
                const mine = i.matched_finding !== null ? draft.findings[i.matched_finding] : undefined;
                return (
                  <tr key={k} style={{ cursor: "default" }}>
                    <td>{i.status === "found" ? <Badge tone="success"><CircleCheck size={12} />Найдено</Badge> : <Badge tone="danger"><CircleX size={12} />Пропущено</Badge>}</td>
                    <td>{TYPE_LABEL[i.type]}</td>
                    <td className="mono">{i.affected_ids.join(", ")}</td>
                    <td className="num">{formatMinor(i.expected_amount_minor, i.currency, exps)}</td>
                    <td className="num">{mine ? formatMinor(mine.claimed_amount_minor, mine.currency, exps) : <span className="muted">—</span>}</td>
                    <td className="mono" style={{ whiteSpace: "normal", minWidth: 280 }}>{i.evidence_sets.slice(0, 2).map((s) => s.join(" + ")).join("  или  ")}{i.evidence_sets.length > 2 && ` (+${i.evidence_sets.length - 2})`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {r.false_positives.length > 0 && (
        <>
          <h2>Ложные срабатывания</h2>
          <div className="list" style={{ maxHeight: "none" }}>
            {r.false_positives.map((idx) => { const f = draft.findings[idx]; return f && (
              <div key={idx} className="list-item">
                <div className="list-item-head"><Badge tone="danger">FP</Badge><span>#{idx + 1} {TYPE_LABEL[f.type]}</span>
                  <span style={{ marginLeft: "auto" }}>{formatMinor(f.claimed_amount_minor, f.currency, exps)}</span></div>
                <div className="mono">{f.affected_ids.join(", ")}</div>
              </div>); })}
          </div>
        </>
      )}
      <div className="row" style={{ marginTop: 24 }}>
        <button className="btn primary" onClick={onAgain}><RotateCcw size={14} />Сыграть ещё раз</button>
        <button className="btn" onClick={onOther}><FolderOpen size={14} />Другой эпизод</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Подключить в `App.tsx`**

Импорт `import { Review } from "./screens/Review";`, ключ текущего эпизода хранить в состоянии: `const [episodeKey, setEpisodeKey] = useState<string | null>(null);` и в `start` вызывать `setEpisodeKey(key)`. Ветка `switch`:
```tsx
    case "review": screen = ep.obs ? <Review ep={ep} draft={draft} onAgain={() => episodeKey && start(episodeKey)}
        onOther={() => go({ name: "episodes" })} /> : null; break;
```
Автопереход при усечении — добавить эффект:
```tsx
  useEffect(() => { if (ep.done && ep.review) setView({ name: "review" }); }, [ep.done, ep.review]);
```
(добавить `useEffect` в импорт из `react`).

- [ ] **Step 3: Финальная сборка**

Run: `cd frontend && npm run build`
Expected: `tsc` без ошибок, `frontend/dist/` содержит `index.html`, `assets/*.js|css|woff2`.

- [ ] **Step 4: Ручной прогон в браузере**

Run: `make play`, открыть `http://127.0.0.1:8000`, пройти `dev/04`: загрузить платежи и книгу, найти платёж с кредитом 2200 при полной ссылке, добавить вывод через карточку записи, отправить.
Expected: «Разбор» показывает награду, TP ≥ 1, пропущенные ошибки красными метками; «Сыграть ещё раз» начинает новый эпизод со 100 шагами.

- [ ] **Step 5: Документация**

В `README.md` после раздела «Использование среды» добавить:
```markdown
## Сыграть за аудитора (веб-интерфейс)

```bash
make play        # http://127.0.0.1:8000 — сервер на stdlib раздаёт собранный frontend/dist
```

Тот же бюджет 100 шагов и те же инструменты, что у агента; после отправки — разбор по эталону
(только для открытых train/dev эпизодов). Пересборка фронта (нужны Node 18+ и сеть для `npm ci`):
`make frontend`. Разработка: `cd frontend && npm run dev` (Vite проксирует `/api` на `:8000`).
```
В `DESIGN.md` добавить раздел «11. Auditor Playground»: сервер `backend/src/audit_env/server.py` — тонкая обёртка над `AuditEnv("train")`, `/api/review` только после конца эпизода и только для открытых эпизодов; фронт не влияет на `make verify` и Docker.

- [ ] **Step 6: Полная проверка и commit**

Run: `make verify`
Expected: все шаги `OK`.

```bash
git add frontend/src frontend/dist README.md DESIGN.md
git commit -m "Review screen, built frontend bundle, playground docs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
