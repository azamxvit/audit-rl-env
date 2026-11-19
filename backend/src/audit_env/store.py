"""Read-only record store behind the agent's tools.

- Records are served in file order (no re-sorting), so permuting files permutes pages.
- Pages hold at most 50 records; cursors are opaque, stable tokens (same position ->
  same token within an episode) and are validated server-side.
- Every returned record is a fresh copy; the agent cannot mutate the store.
"""
from __future__ import annotations

import copy
import hashlib

TABLES = {
    "ledger": "row_id",
    "invoices": "invoice_id",
    "payments": "payment_id",
    "fx": "rate_id",
}
MAX_PAGE = 50


class ToolError(Exception):
    """Bounded error: ``code`` and a fixed short message, never implementation details or inputs."""

    MESSAGES = {
        "unknown_tool": "Unknown tool.",
        "invalid_action": "Action must be an object {\"tool\": str, \"args\": object}.",
        "invalid_args": "Invalid or missing arguments for this tool.",
        "unknown_table": "Unknown table.",
        "unknown_id": "No record with this id.",
        "invalid_cursor": "Invalid cursor.",
        "invalid_limit": "limit must be an integer between 1 and 50.",
        "calculator_error": "Expression rejected or not computable.",
        "episode_finished": "Episode already finished; call reset().",
        "time_limit": "Time limit exceeded; episode truncated.",
    }

    def __init__(self, code: str, detail: str | None = None):
        super().__init__(code)
        self.code = code
        self.detail = detail  # only for calculator messages, which never contain data

    def as_dict(self) -> dict:
        msg = self.MESSAGES[self.code]
        if self.detail:
            msg = f"{msg} ({self.detail})"
        return {"code": self.code, "message": msg}


class RecordStore:
    def __init__(self, public: dict, cursor_salt: str):
        self._tables = {t: [copy.deepcopy(r) for r in public[t]] for t in TABLES}
        self._index = {t: {r[k]: r for r in self._tables[t]} for t, k in TABLES.items()}
        self._docs = {}
        self._docs_by_table: dict = {"invoices": {}, "payments": {}}
        for t in ("invoices", "payments"):
            for r in self._tables[t]:
                self._docs[r["doc_id"]] = r
                self._docs_by_table[t][r["doc_id"]] = r
        self._salt = cursor_salt
        self._cursors: dict = {}

    def counts(self) -> dict:
        return {t: len(v) for t, v in self._tables.items()}

    def _token(self, table: str, offset: int) -> str:
        h = hashlib.sha256(f"{self._salt}|{table}|{offset}".encode()).hexdigest()[:20]
        token = f"c_{h}"
        self._cursors[token] = (table, offset)
        return token

    def list_records(self, table, cursor=None, limit=MAX_PAGE) -> dict:
        if not isinstance(table, str) or table not in TABLES:
            raise ToolError("unknown_table")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE:
            raise ToolError("invalid_limit")
        if cursor is None:
            offset = 0
        else:
            if not isinstance(cursor, str) or cursor not in self._cursors:
                raise ToolError("invalid_cursor")
            t, offset = self._cursors[cursor]
            if t != table:
                raise ToolError("invalid_cursor")
        rows = self._tables[table]
        page = [copy.deepcopy(r) for r in rows[offset:offset + limit]]
        nxt = offset + len(page)
        return {
            "table": table,
            "records": page,
            "next_cursor": self._token(table, nxt) if nxt < len(rows) else None,
        }

    def get_record(self, table, record_id) -> dict:
        if not isinstance(table, str) or table not in TABLES:
            raise ToolError("unknown_table")
        if not isinstance(record_id, str):
            raise ToolError("invalid_args")
        rec = self._index[table].get(record_id)
        if rec is None and table in self._docs_by_table:
            rec = self._docs_by_table[table].get(record_id)
        if rec is None:
            raise ToolError("unknown_id")
        return copy.deepcopy(rec)

    def get_document(self, doc_id) -> dict:
        if not isinstance(doc_id, str):
            raise ToolError("invalid_args")
        rec = self._docs.get(doc_id)
        if rec is None:
            raise ToolError("unknown_id")
        out = copy.deepcopy(rec)
        doc_type = "invoice" if rec["doc_id"] in self._docs_by_table["invoices"] else "payment"
        return {"doc_type": doc_type, "document": out}
