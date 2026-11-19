"""CLI: write a permuted + ID-renamed copy of an episode (for paired checks).

usage: python scripts/transform_episode.py episodes/dev/00_EP-XXXX /tmp/out [--seed S] [--no-permute] [--no-rename]
Writes <out>/public, <out>/private/truth.json (renamed) and <out>/private/id_mapping.json.
"""
import argparse
import json
from pathlib import Path

import _common  # noqa: F401  (sys.path)

from audit_env.generator import Episode, load_private, load_public, write_episode
from audit_env.transform import transform_episode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--seed", default="pair")
    ap.add_argument("--no-permute", action="store_true")
    ap.add_argument("--no-rename", action="store_true")
    a = ap.parse_args()
    public = load_public(Path(a.src))
    truth, prov = load_private(Path(a.src))
    pub2, tr2, mapping = transform_episode(public, truth, a.seed, not a.no_permute, not a.no_rename)
    write_episode(Episode(pub2, tr2, {"note": "transformed copy", "source_episode": truth["episode_id"]}, {}),
                  Path(a.dst))
    (Path(a.dst) / "private" / "id_mapping.json").write_text(json.dumps(mapping, indent=2, sort_keys=True))
    print(f"wrote {a.dst} ({len(mapping)} ids remapped)")


if __name__ == "__main__":
    main()
