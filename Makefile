PYTHON ?= python3
export PYTHONPATH := src

.PHONY: verify test episodes baselines check-data demo clean

verify: episodes test check-data baselines
	@echo "verify: OK"

episodes:
	$(PYTHON) scripts/generate_episodes.py

test:
	$(PYTHON) -m pytest

check-data:
	$(PYTHON) scripts/verify.py

baselines:
	$(PYTHON) scripts/run_baselines.py

demo:
	$(PYTHON) scripts/demo.py

clean:
	rm -rf runs .pytest_cache
