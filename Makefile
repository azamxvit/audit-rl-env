PYTHON ?= python3
BACKEND := backend
RUN := cd $(BACKEND) && PYTHONPATH=src $(PYTHON)
# ruff from the active environment (pip install -r backend/requirements-dev.txt), or the local .venv
RUFF ?= $(shell command -v ruff 2>/dev/null || echo $(CURDIR)/.venv/bin/ruff)

.PHONY: verify test episodes check-data baselines demo play frontend frontend-test e2e format lint clean

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

# Unit/component tests of the frontend (Vitest + Testing Library)
frontend-test:
	cd frontend && npm test

# End-to-end: builds dist, starts the backend server, drives Chromium (Playwright + axe)
e2e:
	cd frontend && npm run build && npx playwright test

# Autoformat everything: Python (ruff) + TS/CSS/JSON/Markdown (Prettier, Tailwind class order)
format:
	cd $(BACKEND) && $(RUFF) check --fix . && $(RUFF) format .
	cd frontend && npx prettier --write . ../README.md ../DESIGN.md ../docs/superpowers

# Check formatting and lint without changing files
lint:
	cd $(BACKEND) && $(RUFF) check . && $(RUFF) format --check .
	cd frontend && npx prettier --check . ../README.md ../DESIGN.md ../docs/superpowers

clean:
	rm -rf $(BACKEND)/.pytest_cache
