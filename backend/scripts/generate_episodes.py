"""Generate the open train/dev episodes from configs/splits.json into episodes/<split>/<NN>_<episode_id>/."""

import json
import shutil

from _common import CONFIGS, EPISODES, ROOT, splits
from audit_env import ENV_VERSION, SCHEMA_VERSION
from audit_env.generator import generate_episode, load_config, public_files, write_episode
from audit_env.util import dumps, sha256_text


def main() -> None:
    sp = splits()
    if EPISODES.exists():
        shutil.rmtree(EPISODES)
    index = {"schema_version": SCHEMA_VERSION, "env_version": ENV_VERSION, "episodes": []}
    for split in ("train", "dev"):
        for n, item in enumerate(sp[split]):
            cfg = load_config(CONFIGS / item["config"])
            ep = generate_episode(item["seed"], cfg)
            rel = f"{split}/{n:02d}_{ep.episode_id}"
            write_episode(ep, EPISODES / rel)
            types = {}
            for i in ep.truth["issues"]:
                types[i["type"]] = types.get(i["type"], 0) + 1
            index["episodes"].append(
                {
                    "split": split,
                    "path": rel,
                    "episode_id": ep.episode_id,
                    "config": item["config"],
                    "config_id": cfg["config_id"],
                    "seed": item["seed"],
                    "public_sha256": sha256_text(dumps(public_files(ep.public))),
                    "n_issues": len(ep.truth["issues"]),
                    "issue_types": types,
                    "scenarios": sorted({i["scenario"] for i in ep.truth["issues"] if i["scenario"]}),
                    "counts": ep.public["manifest"]["counts"],
                }
            )
            print(
                f"{rel}: {ep.public['manifest']['counts']['ledger_rows']} rows, "
                f"{ep.public['manifest']['counts']['documents']} docs, {len(ep.truth['issues'])} issues"
            )
    (EPISODES / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"wrote {len(index['episodes'])} episodes to {EPISODES.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
