"""Plug in any policy: a Python class, or a process in any language that speaks JSON lines.

Python:  a class with ``reset(observation)`` and ``act(observation) -> action`` (see policies/base.py),
         addressed as ``package.module:Class`` or ``path/to/file.py:Class``.

Process: ``ProcessPolicy(["node", "agent.js"])``. The environment writes one JSON object per line to
         the process's stdin and reads one action per line from its stdout:

             -> {"type": "reset", "observation": <reset observation>}
             <- {"tool": "list_records", "args": {"table": "ledger"}}
             -> {"type": "step", "observation": <step observation>}
             <- {"tool": "submit", "args": {"episode_id": "...", "findings": [...]}}
             -> {"type": "reset", ...}                       (next episode, same process)
             -> {"type": "close"}                            (then stdin is closed)

         A line that is not JSON is passed through as-is and costs a step (``invalid_action``);
         a crashed or silent process sends no action, so the episode runs into its limits.
         stderr is inherited, so the process can log freely there.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import selectors
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .policies.base import Policy


def load_policy_class(spec: str):
    """``pkg.module:Class`` or ``path/to/file.py:Class`` -> the class."""
    target, sep, name = spec.rpartition(":")
    if not sep or not name:
        raise ValueError("policy spec must look like 'module:Class' or 'file.py:Class'")
    if target.endswith(".py"):
        path = Path(target).resolve()
        mod_spec = importlib.util.spec_from_file_location(f"_policy_{path.stem}", path)
        if mod_spec is None or mod_spec.loader is None:
            raise ValueError(f"cannot load {target}")
        module = importlib.util.module_from_spec(mod_spec)
        sys.modules[mod_spec.name] = module
        mod_spec.loader.exec_module(module)
    else:
        module = importlib.import_module(target)
    return getattr(module, name)


class ProcessPolicy(Policy):
    """Adapter for a policy that runs as a separate process speaking JSON lines (see module docstring)."""

    name = "process"

    def __init__(self, cmd: list, reply_timeout_s: float = 60.0, cwd: Optional[str] = None):
        self.cmd = list(cmd)
        self.reply_timeout_s = reply_timeout_s
        self.proc = subprocess.Popen(
            self.cmd,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._sel = selectors.DefaultSelector()
        self._sel.register(self.proc.stdout, selectors.EVENT_READ)
        self._first = False

    def _send(self, msg: dict) -> None:
        if self.proc.poll() is not None:
            return
        try:
            self.proc.stdin.write(json.dumps(msg, separators=(",", ":")) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def _read(self):
        if not self._sel.select(self.reply_timeout_s):
            return None  # silent process: no action
        line = self.proc.stdout.readline()
        if not line:
            return None  # process exited
        line = line.strip()
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return line  # the env answers invalid_action and charges a step

    def reset(self, observation: dict) -> None:
        self._send({"type": "reset", "observation": observation})
        self._first = True

    def act(self, observation: dict):
        if not self._first:
            self._send({"type": "step", "observation": observation})
        self._first = False
        return self._read()

    def close(self) -> None:
        self._send({"type": "close"})
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self._sel.close()
