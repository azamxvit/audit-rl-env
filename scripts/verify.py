"""Independent data verification of the published episodes + paired (permutation / ID-renaming) checks.

For every episode in episodes/index.json:
  1. regenerate from (config, seed) and require byte-identical public files and identical truth (reproducibility);
  2. accounting invariants on the pre-injection books, clean-books audit finds nothing;
  3. invariants after injection, rule-based audit == truth, every evidence set independently sufficient;
  4. paired check: permute + rename IDs -> episode still valid, oracle answer (renamed) gets the same reward.
Exit code 1 on any problem.
"""
import json
import sys

from _common import CONFIGS, EPISODES, RUNS, episode_dirs

from audit_env.checker import verify_episode
from audit_env.generator import generate_episode, load_config, load_private, load_public, public_files
from audit_env.grader import Grader
from audit_env.transform import map_findings, transform_episode
from audit_env.util import dumps, sha256_text


def oracle_submission(truth):
    return {"episode_id": truth["episode_id"], "findings": [
        {"type": i["type"], "affected_ids": i["affected_ids"], "claimed_amount_minor": i["expected_amount_minor"],
         "currency": i["currency"], "evidence_ids": i["evidence_sets"][0], "explanation": ""} for i in truth["issues"]]}


def main() -> int:
    problems, rows = [], []
    for split in ("train", "dev"):
        for path, meta in episode_dirs(split):
            public = load_public(path)
            truth, _ = load_private(path)
            regen = generate_episode(meta["seed"], load_config(CONFIGS / meta["config"]))
            p = []
            if sha256_text(dumps(public_files(regen.public))) != meta["public_sha256"] or regen.public != public:
                p.append("public files not reproducible from (config, seed)")
            if regen.truth != truth:
                p.append("truth not reproducible")
            p += verify_episode(public, truth, regen.clean_public)
            pub2, tr2, mapping = transform_episode(public, truth, seed=("pair", meta["episode_id"]))
            p += [f"paired: {x}" for x in verify_episode(pub2, tr2)]
            sub = oracle_submission(truth)
            r1 = Grader(public, truth).grade(sub, 0, "submit")["reward"]
            r2 = Grader(pub2, tr2).grade(map_findings(sub, mapping), 0, "submit")["reward"]
            if not (r1 == r2 == 1.0):
                p.append(f"paired oracle reward {r1} vs {r2}")
            rows.append({"episode": meta["path"], "issues": meta["n_issues"], "ok": not p, "problems": p})
            print(f"{'OK ' if not p else 'BAD'} {meta['path']} issues={meta['n_issues']}")
            problems += [f"{meta['path']}: {x}" for x in p]
    RUNS.mkdir(exist_ok=True)
    (RUNS / "data_verification.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(f"data verification: {sum(r['ok'] for r in rows)}/{len(rows)} episodes OK")
    for x in problems:
        print("  -", x)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
