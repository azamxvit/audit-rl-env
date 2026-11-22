# Local CI - last run

**PASS** (full) for commit `536080b27593` **with uncommitted changes**, 2026-11-22T16:04:13Z, 138.4 s, Darwin arm64.

Tools: python 3.14.6, node v24.16.0, docker 29.5.2, ruff ruff 0.8.4.

| step | result | time, s | note |
|---|---|---|---|
| lint: ruff + prettier | PASS | 1.2 |  |
| backend tests | PASS | 14.6 |  |
| make verify (episodes, tests, data, fuzz 150, baselines, learned eval) | PASS | 37.4 |  |
| published episodes byte-identical after regeneration | PASS | 0.1 |  |
| learned auditor weights reproducible | PASS | 4.7 |  |
| generator fuzz, 600 random configs | PASS | 18.8 |  |
| frontend unit tests (Vitest) | PASS | 1.9 |  |
| frontend/dist matches sources | PASS | 1.8 |  |
| frontend e2e + axe (Playwright) | PASS | 10.8 |  |
| Docker: build + verify offline, --cpus 2 --memory 4g | PASS | 46.8 |  |

Produced by `make ci` (ci/ci.py). Reproduce on your machine with the same command.
