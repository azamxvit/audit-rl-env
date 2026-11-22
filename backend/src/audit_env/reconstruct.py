"""Rebuild the books BEFORE error injection from the open files + private/provenance.json.

Check definitions, block 2, condition 1: the generation history and the documents must let anyone verify the
pre-injection state independently. Every injected change is recorded with the ledger rows it removed
(``ledger_before``) and added (``ledger_after``), and with any document it added (``document_added``).
Undoing the changes in reverse order gives the clean books, which ``checker.check_invariants`` and
``checker.audit`` then verify (balanced entries, no issues).

    PYTHONPATH=src python3 -m audit_env.reconstruct <episode_dir>
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


def clean_books(public: dict, provenance: dict) -> dict:
    books = copy.deepcopy(public)
    for change in reversed(provenance["changes"]):
        added = {r["row_id"] for r in change["ledger_after"] or []}
        books["ledger"] = [r for r in books["ledger"] if r["row_id"] not in added]
        books["ledger"] += copy.deepcopy(change["ledger_before"] or [])
        doc = change["document_added"]
        if doc is not None:
            table = "invoices" if "invoice_id" in doc else "payments"
            books[table] = [d for d in books[table] if d["doc_id"] != doc["doc_id"]]
    return books


def main(argv: list) -> int:
    from .checker import audit, check_invariants
    from .generator import load_private, load_public

    d = Path(argv[0])
    public = load_public(d)
    _, provenance = load_private(d)
    clean = clean_books(public, provenance)
    report = {
        "changes_undone": len(provenance["changes"]),
        "ledger_rows": {"injected": len(public["ledger"]), "clean": len(clean["ledger"])},
        "clean_invariant_problems": check_invariants(clean),
        "clean_audit_findings": audit(clean),
    }
    print(json.dumps(report, indent=2))
    return 0 if not report["clean_invariant_problems"] and not report["clean_audit_findings"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
