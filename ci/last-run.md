# Local CI - last run

**PASS** (full) for commit `5b4379b05a9a`, 2026-11-22T08:39:43Z, 130.9 s, Darwin arm64.

Tools: python 3.14.6, node v24.16.0, docker 29.5.2, ruff ruff 0.8.4.

| step | result | time, s | note |
|---|---|---|---|
| lint: ruff + prettier | PASS | 0.9 |  |
| backend tests | PASS | 13.4 |  |
| make verify (episodes, tests, data, fuzz 150, baselines, learned eval) | PASS | 36.3 |  |
| published episodes byte-identical after regeneration | PASS | 0.1 |  |
| learned auditor weights reproducible | PASS | 4.7 |  |
| generator fuzz, 600 random configs | PASS | 17.8 |  |
| frontend unit tests (Vitest) | PASS | 1.6 |  |
| frontend/dist matches sources | PASS | 1.6 |  |
| frontend e2e + axe (Playwright) | PASS | 10.0 |  |
| Docker: build + verify offline, --cpus 2 --memory 4g | PASS | 44.1 |  |

Produced by `make ci` (ci/ci.py). Reproduce on your machine with the same command.
