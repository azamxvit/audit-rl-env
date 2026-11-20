"""A policy as a separate process, speaking JSON lines. Port this loop to any language.

Run:  PYTHONPATH=src python3 scripts/run_policy.py --cmd "python3 examples/jsonl_policy.py" --split dev --mode eval

stdin : one JSON object per line - {"type": "reset"|"step", "observation": {...}} or {"type": "close"}
stdout: one action per line, in reply to every reset/step message
stderr: free for logging
This example reads one page of invoices and submits an empty answer (right only for clean books).
Deliberately no imports from audit_env: nothing but the protocol is shared.
"""

import json
import sys

episode_id = None
for line in sys.stdin:
    msg = json.loads(line)
    if msg["type"] == "close":
        break
    obs = msg["observation"]
    if msg["type"] == "reset":
        episode_id = obs["manifest"]["episode_id"]
        action = {"tool": "list_records", "args": {"table": "invoices", "limit": 50}}
    else:
        print(f"read {len(obs['result']['records']) if obs['ok'] else 0} invoices", file=sys.stderr)
        action = {"tool": "submit", "args": {"episode_id": episode_id, "findings": []}}
    sys.stdout.write(json.dumps(action) + "\n")
    sys.stdout.flush()
