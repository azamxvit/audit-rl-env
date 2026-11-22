PYTHON ?= python3
BACKEND := backend
RUN := cd $(BACKEND) && PYTHONPATH=src $(PYTHON)
# ruff from the active environment (pip install -r backend/requirements-dev.txt), or the local .venv
RUFF ?= $(shell command -v ruff 2>/dev/null || echo $(CURDIR)/.venv/bin/ruff)

.PHONY: ci ci-fast hooks train-learned-check verify test episodes check-data fuzz baselines train-learned eval-learned demo demo-steps demo-record play frontend frontend-test e2e format lint clean

# One command: generate episodes -> tests -> independent data checks -> baselines (trajectories + report)
# -> held-out evaluation of the learned auditor
verify:
	$(RUN) scripts/verify_all.py

episodes:
	$(RUN) scripts/generate_episodes.py

test:
	$(RUN) -m pytest -q

check-data:
	$(RUN) scripts/verify.py

# Unseen seeds x random parameter combinations through the independent checker (CASES=1000 for a long run)
CASES ?= 300
fuzz:
	$(RUN) scripts/fuzz_generator.py --cases $(CASES)

baselines:
	$(RUN) scripts/run_baselines.py

# Learned auditor: retrain the detector (~5 s, CPU, stdlib) and evaluate it on held-out episodes
train-learned:
	$(RUN) scripts/train_learned.py

train-learned-check:
	$(RUN) scripts/train_learned.py --check

eval-learned:
	$(RUN) scripts/eval_learned.py

# Demo tour in 7 scenes (PACE=2.5 pauses between scenes for screen recording, see DEMO.md)
PACE ?= 0
STEP ?=
demo:
	$(RUN) scripts/demo_tour.py --pace $(PACE) $(if $(STEP),--step,)

# One-take screen recording: Docker check -> tour (Enter between scenes) -> report -> web UI (DEMO.md)
demo-record:
	bash scripts/demo_record.sh

# Step-by-step run of one scripted policy on one dev episode
demo-steps:
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
	$(RUFF) check --fix --config $(BACKEND)/pyproject.toml ci && $(RUFF) format --config $(BACKEND)/pyproject.toml ci
	cd frontend && npx prettier --write . ../README.md ../DESIGN.md ../DEMO.md ../docs/superpowers

# Check formatting and lint without changing files
lint:
	cd $(BACKEND) && $(RUFF) check . && $(RUFF) format --check .
	$(RUFF) check --config $(BACKEND)/pyproject.toml ci && $(RUFF) format --check --config $(BACKEND)/pyproject.toml ci
	cd frontend && npx prettier --check . ../README.md ../DESIGN.md ../DEMO.md ../docs/superpowers

clean:
	rm -rf $(BACKEND)/.pytest_cache

# Local CI (no hosted runners): full pipeline + report in ci/last-run.md; see ci/ci.py
ci:
	$(PYTHON) ci/ci.py

ci-fast:
	$(PYTHON) ci/ci.py --fast

# Run `make ci-fast` before every git push (undo: git config --unset core.hooksPath)
hooks:
	git config core.hooksPath .githooks
	@echo "pre-push hook enabled: make ci-fast runs before every push"
