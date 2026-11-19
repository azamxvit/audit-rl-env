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
