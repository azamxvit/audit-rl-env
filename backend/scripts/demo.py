"""Demo: a scripted policy audits one dev episode step by step, then the grader scores it.

usage: python scripts/demo.py [episode_index_in_dev] [--policy simple_reconciler|oracle|flag_all|random_explorer]
"""

import argparse
import json

from _common import episode_dirs
from audit_env.env import AuditEnv
from audit_env.generator import load_private
from audit_env.policies import FlagAllPolicy, OraclePolicy, RandomExplorerPolicy, SimpleReconcilerPolicy


def short(action):
    if action["tool"] == "submit":
        return f"submit({len(action['args']['findings'])} findings)"
    return f"{action['tool']}({json.dumps(action.get('args', {}))[:70]})"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("index", nargs="?", type=int, default=0)
    ap.add_argument("--policy", default="simple_reconciler")
    a = ap.parse_args()
    path, meta = episode_dirs("dev")[a.index]
    truth, _ = load_private(path)
    policy = {
        "simple_reconciler": SimpleReconcilerPolicy,
        "oracle": lambda: OraclePolicy(truth),
        "flag_all": FlagAllPolicy,
        "random_explorer": lambda: RandomExplorerPolicy(0),
    }[a.policy]()
    env = AuditEnv("train")
    obs, _ = env.reset(config={"episode_dir": str(path)})
    m = obs["manifest"]
    print(
        f"Episode {m['episode_id']}  {m['company_name']}  {m['period_start']}..{m['period_end']} "
        f"tz {m['timezone']}  base {m['base_currency']}"
    )
    print("  tables: " + ", ".join(f"{t}={v['count']}" for t, v in obs["tables"].items()))
    policy.reset(obs)
    done = False
    while not done:
        action = policy.act(obs)
        obs, reward, term, trunc, info = env.step(action)
        status = "ok" if obs["ok"] else obs["error"]["code"]
        n = (
            len(obs["result"]["records"])
            if obs["ok"] and isinstance(obs["result"], dict) and "records" in obs["result"]
            else ""
        )
        print(f"  step {100 - obs['steps_remaining']:3d}  {short(action):<80} {status} {n}")
        if action["tool"] == "submit":
            for f in action["args"]["findings"]:
                print(
                    f"           -> {f['type']:<19} {','.join(f['affected_ids']):<28} "
                    f"{f['claimed_amount_minor']:>12} {f['currency']}"
                )
        done = term or trunc
    g = env._grader.result
    print(
        f"\nGrader: valid={g['valid']} TP={g['tp']} FP={g['fp']} FN={g['fn']} F1={g['f1']:.3f} "
        f"reward={g['reward']:.3f}  (truth has {len(truth['issues'])} issues; missed: {g.get('missed_types')})"
    )


if __name__ == "__main__":
    main()
