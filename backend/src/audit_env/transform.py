"""Harmless transformations for paired checks: permute record order and rename every ID.

The mapping is a random bijection that keeps each ID's prefix (``INV-``, ``LR-`` ...)
so formats stay valid. Truth is rewritten with the same mapping. A correct
environment must give the oracle (and any order/ID-agnostic policy) the same
reward on the original and on the transformed episode.
"""
from __future__ import annotations

import copy

from .util import IdFactory, derive_rng

ID_FIELDS = {
    "ledger": ["row_id", "entry_id", "entity_id", "invoice_id", "payment_id"],
    "invoices": ["doc_id", "invoice_id", "entity_id"],
    "payments": ["doc_id", "payment_id", "entity_id"],
    "fx": ["rate_id"],
}


def _collect_ids(public: dict) -> list:
    ids = {public["manifest"]["episode_id"]}
    for table, fields in ID_FIELDS.items():
        for rec in public[table]:
            for f in fields:
                if rec.get(f):
                    ids.add(rec[f])
            for ref in rec.get("invoice_refs") or []:
                ids.add(ref["invoice_id"])
    return sorted(ids)


def transform_episode(public: dict, truth: dict, seed: object, permute: bool = True, rename: bool = True):
    """Return (public', truth', mapping old_id -> new_id)."""
    rng = derive_rng(seed, "metamorphic")
    old = _collect_ids(public)
    mapping = {i: i for i in old}
    if rename:
        factory = IdFactory(derive_rng(seed, "metamorphic-ids"), used=set(old))
        mapping = {i: factory.new(i.split("-", 1)[0]) for i in old}
    m = mapping.get
    pub = copy.deepcopy(public)
    pub["manifest"]["episode_id"] = m(pub["manifest"]["episode_id"])
    for table, fields in ID_FIELDS.items():
        for rec in pub[table]:
            for f in fields:
                if rec.get(f):
                    rec[f] = m(rec[f])
            if rec.get("invoice_refs"):
                for ref in rec["invoice_refs"]:
                    ref["invoice_id"] = m(ref["invoice_id"])
        if permute:
            rng.shuffle(pub[table])
    tr = copy.deepcopy(truth)
    tr["episode_id"] = m(tr["episode_id"])
    for issue in tr["issues"]:
        issue["affected_ids"] = sorted(m(x) for x in issue["affected_ids"])
        issue["evidence_sets"] = sorted(sorted(m(x) for x in es) for es in issue["evidence_sets"])
    tr["issues"].sort(key=lambda i: (i["type"], i["affected_ids"], i["issue_id"]))
    return pub, tr, mapping


def map_findings(submission: dict, mapping: dict) -> dict:
    """Apply an ID mapping to a submission (to compare answers across a transformation)."""
    sub = copy.deepcopy(submission)
    sub["episode_id"] = mapping.get(sub["episode_id"], sub["episode_id"])
    for f in sub["findings"]:
        f["affected_ids"] = [mapping.get(x, x) for x in f["affected_ids"]]
        f["evidence_ids"] = [mapping.get(x, x) for x in f["evidence_ids"]]
    return sub
