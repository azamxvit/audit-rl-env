PYTHON ?= python3
export PYTHONPATH := src

.PHONY: verify test episodes check-data baselines demo clean

# One command: generate episodes -> tests -> independent data checks -> 4 baselines (trajectories + report)
verify:
	$(PYTHON) scripts/verify_all.py

episodes:
	$(PYTHON) scripts/generate_episodes.py

test:
	$(PYTHON) -m pytest -q

check-data:
	$(PYTHON) scripts/verify.py

baselines:
	$(PYTHON) scripts/run_baselines.py

demo:
	$(PYTHON) scripts/demo.py 4

clean:
	rm -rf .pytest_cache
