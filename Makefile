PYTHON ?= python3
BACKEND := backend
RUN := cd $(BACKEND) && PYTHONPATH=src $(PYTHON)
# ruff from the active environment (pip install -r backend/requirements-dev.txt), or the local .venv
RUFF ?= $(shell command -v ruff 2>/dev/null || echo $(CURDIR)/.venv/bin/ruff)

.PHONY: verify test episodes check-data fuzz baselines train-learned eval-learned demo play frontend frontend-test e2e format lint clean

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

eval-learned:
	$(RUN) scripts/eval_learned.py

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
