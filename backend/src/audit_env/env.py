"""AuditEnv — Gymnasium-style, JSON-compatible reset/step contract.

    env = AuditEnv(mode="train")
    obs, info = env.reset(seed=7, config=cfg)
    obs, reward, terminated, truncated, info = env.step({"tool": "list_records",
                                                         "args": {"table": "ledger"}})

Tools: list_records(table, cursor=None, limit=50), get_record(table, id),
get_document(doc_id), calculator(expression), submit(episode_id, findings).
"""

from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Callable, Optional

from . import ENV_VERSION, SCHEMA_VERSION
from .calculator import CalculatorError, evaluate
from .grader import Grader, SubprocessGrader, load_episode
from .store import TABLES, RecordStore, ToolError
from .util import sha256_text

MAX_STEPS = 100
TIME_LIMIT_S = 60.0

TASK_TEXT = (
    "You are auditing the books of one fictional company for one reporting period. Investigate the records "
    "with the tools and submit findings with evidence. Possible issue types: duplicate_invoice, "
    "payment_allocation, fx_error, period_cutoff. Some books are clean; many look-alikes are legitimate "
    "(split payments, refunds, recurring identical amounts, weekend FX fallback, timezone offsets). "
    "Conventions for a finding: claimed_amount_minor = absolute misstatement in the FUNCTIONAL currency "
    "(manifest.base_currency) in minor units, currency = that functional currency. affected_ids: "
    "duplicate_invoice -> both invoice_ids, amount booked for the later-issued copy; payment_allocation -> "
    "[payment_id, invoice_id], amount credited to 2200 by that receipt; fx_error -> [invoice_id] or "
    "[payment_id], |booked - amount at the policy rate|; period_cutoff -> [invoice_id], amount booked. "
    "evidence_ids: record ids (doc_id or invoice_id/payment_id for documents, row_id for ledger rows, rate_id "
    "for fx rates) that together prove the issue (documents, the booking row(s), the fx row used by policy). "
    "Amount tolerance is 1 minor unit. Every step (including errors) costs budget; submit ends the episode."
)

TOOLS = [
    {
        "name": "list_records",
        "args": {"table": "ledger|invoices|payments|fx", "cursor": "str|null", "limit": "int 1..50 (default 50)"},
    },
    {"name": "get_record", "args": {"table": "ledger|invoices|payments|fx", "id": "str"}},
    {"name": "get_document", "args": {"doc_id": "str"}},
    {"name": "calculator", "args": {"expression": "arithmetic on decimal numbers"}},
    {
        "name": "submit",
        "args": {
            "episode_id": "str",
            "findings": "list (<=30) of {type, affected_ids, "
            "claimed_amount_minor, currency, evidence_ids (<=10), explanation (<=1000 chars)}",
        },
    },
]


class AuditEnv:
    """Train mode: in-process grader, terminal reward returned. Eval mode: grader in a separate process,
    policy receives reward 0 and empty info; results only in the grader log."""

    def __init__(
        self,
        mode: str = "train",
        max_steps: int = MAX_STEPS,
        time_limit_s: float = TIME_LIMIT_S,
        clock: Optional[Callable[[], float]] = None,
        grader_log: Optional[Path] = None,
        eval_plan: Optional[Path] = None,
    ):
        if mode not in ("train", "eval"):
            raise ValueError("mode must be 'train' or 'eval'")
        self.mode = mode
        self.max_steps = max_steps
        self.time_limit_s = time_limit_s
        self._clock = clock or time.monotonic
        self._grader_log = Path(grader_log) if grader_log else None
        self._remote: Optional[SubprocessGrader] = None
        if mode == "eval":
            if self._grader_log is None:
                raise ValueError("eval mode needs grader_log (results stay with the grader)")
            self._remote = SubprocessGrader(self._grader_log, eval_plan)
        self._grader: Optional[Grader] = None
        self._store: Optional[RecordStore] = None
        self._episode_id: Optional[str] = None
        self._steps = 0
        self._done = True
        self._started = False

    # ------------------------------------------------------------------ API
    def reset(self, seed=None, config: Optional[dict] = None, options: Optional[dict] = None):
        cfg = config if config is not None else (options or {}).get("config")
        if self.mode == "train":
            ep = load_episode(seed, cfg)
            public = ep.public
            self._grader = Grader(public, ep.truth, self._grader_log)
        else:
            public = self._remote.load(seed, cfg)
            self._grader = None
        self._episode_id = public["manifest"]["episode_id"]
        self._store = RecordStore(public, cursor_salt=sha256_text(self._episode_id + "|cursor"))
        self._steps = 0
        self._done = False
        self._started = True
        self._terminated = False
        self._truncated = False
        self._t0 = self._clock()
        obs = {
            "task": TASK_TEXT,
            "manifest": copy.deepcopy(public["manifest"]),
            "policy": copy.deepcopy(public["policy"]),
            "tables": {t: {"id_field": k, "count": self._store.counts()[t]} for t, k in TABLES.items()},
            "tools": copy.deepcopy(TOOLS),
            "max_steps": self.max_steps,
            "steps_remaining": self.max_steps,
        }
        return obs, {"env_version": ENV_VERSION, "schema_version": SCHEMA_VERSION, "mode": self.mode}

    def step(self, action):
        if not self._started:
            raise RuntimeError("call reset() before step()")
        if self._done:
            obs = self._obs(self._tool_name(action), error=ToolError("episode_finished"))
            return obs, 0.0, self._terminated, self._truncated, {}
        if self._clock() - self._t0 > self.time_limit_s:
            return self._finish_truncated(
                self._obs(self._tool_name(action), error=ToolError("time_limit")), "time_limit"
            )
        self._steps += 1
        tool = self._tool_name(action)
        if tool == "submit":
            return self._submit(action.get("args"))
        try:
            result = self._dispatch(action)
            obs = self._obs(tool, result=result)
        except ToolError as exc:
            obs = self._obs(tool, error=exc)
        if self._steps >= self.max_steps:
            return self._finish_truncated(obs, "step_limit")
        return obs, 0.0, False, False, {}

    def close(self) -> None:
        if self._remote is not None:
            self._remote.close()
            self._remote = None

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _tool_name(action) -> Optional[str]:
        if isinstance(action, dict) and isinstance(action.get("tool"), str):
            return action["tool"]
        return None

    def _remaining(self) -> int:
        return max(0, self.max_steps - self._steps)

    def _obs(self, tool, result=None, error: Optional[ToolError] = None) -> dict:
        return {
            "tool": tool if tool in {t["name"] for t in TOOLS} else None,
            "ok": error is None,
            "result": result,
            "error": error.as_dict() if error else None,
            "steps_remaining": self._remaining(),
        }

    def _dispatch(self, action):
        if not isinstance(action, dict) or not isinstance(action.get("tool"), str):
            raise ToolError("invalid_action")
        args = action.get("args", {})
        if not isinstance(args, dict) or set(action) - {"tool", "args"}:
            raise ToolError("invalid_action")
        tool = action["tool"]
        st = self._store
        try:
            if tool == "list_records":
                self._only(args, {"table"}, {"cursor", "limit"})
                return st.list_records(args["table"], args.get("cursor"), args.get("limit", 50))
            if tool == "get_record":
                self._only(args, {"table", "id"})
                return st.get_record(args["table"], args["id"])
            if tool == "get_document":
                self._only(args, {"doc_id"})
                return st.get_document(args["doc_id"])
            if tool == "calculator":
                self._only(args, {"expression"})
                try:
                    return {"value": evaluate(args["expression"])}
                except CalculatorError as exc:
                    raise ToolError("calculator_error", str(exc)) from None
        except KeyError:
            raise ToolError("invalid_args") from None
        raise ToolError("unknown_tool")

    @staticmethod
    def _only(args: dict, required: set, optional: set = frozenset()) -> None:
        if not required <= set(args) or set(args) - required - set(optional):
            raise ToolError("invalid_args")

    def _grade(self, submission, inspection_steps: int, termination: str) -> tuple:
        if self.mode == "train":
            res = self._grader.grade(submission, inspection_steps, termination)
            info = {
                "termination": termination,
                "valid": res["valid"],
                "inspection_steps": inspection_steps,
                "metrics": {k: res[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1")},
            }
            return float(res["reward"]), info
        self._remote.submit(submission, inspection_steps, termination)
        return 0.0, {}

    def _submit(self, args) -> tuple:
        if isinstance(args, dict) and set(args) == {"findings"} and isinstance(args["findings"], dict):
            submission = args["findings"]  # submit(findings=<findings.json>)
        else:
            submission = args  # submit(episode_id=..., findings=[...])
        self._done = True
        self._terminated = True
        reward, info = self._grade(submission, self._steps - 1, "submit")
        obs = self._obs("submit", result={"status": "received"})
        return obs, reward, True, False, info

    def _finish_truncated(self, obs: dict, reason: str) -> tuple:
        self._done = True
        self._truncated = True
        empty = {"episode_id": self._episode_id, "findings": []}
        reward, info = self._grade(empty, self._steps, reason)
        obs["steps_remaining"] = self._remaining()
        return obs, reward, False, True, info
