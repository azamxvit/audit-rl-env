# Local CI - last run

**PASS** (full) for commit `56684f63b84f`, 2026-11-20T17:58:25Z, 120.3 s, Darwin arm64.

Tools: python 3.14.6, node v24.16.0, docker 29.5.2, ruff ruff 0.8.4.

| step | result | time, s | note |
|---|---|---|---|
| lint: ruff + prettier | PASS | 1.0 |  |
| backend tests | PASS | 9.5 |  |
| make verify (episodes, tests, data, fuzz 150, baselines, learned eval) | PASS | 31.5 |  |
| published episodes byte-identical after regeneration | PASS | 0.1 |  |
| learned auditor weights reproducible | PASS | 4.5 |  |
| generator fuzz, 600 random configs | PASS | 17.1 |  |
| frontend unit tests (Vitest) | PASS | 2.2 |  |
| frontend/dist matches sources | PASS | 1.8 |  |
| frontend e2e + axe (Playwright) | PASS | 9.9 |  |
| Docker: build + verify offline, --cpus 2 --memory 4g | PASS | 42.2 |  |

Produced by `make ci` (ci/ci.py). Reproduce on your machine with the same command.
