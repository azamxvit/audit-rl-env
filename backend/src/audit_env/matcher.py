"""Submission validation, normalisation and one-to-one matching against truth.

Published rules (also in DESIGN.md):

Normalisation
  * ``type``: ``strip().lower()``; must be one of the four issue types.
  * ``affected_ids``: each ``strip()``-ed; a ``doc_id`` is mapped to the business
    id of its document (invoice_id / payment_id); duplicates removed; compared
    as a *set* with the canonical affected_ids of the issue.
  * ``evidence_ids``: each ``strip()``-ed; an invoice_id / payment_id is mapped
    to its ``doc_id``; compared as a set.
  * ``currency``: ``strip().upper()``.

Candidate pair (finding f, issue t) iff
  f.type == t.type and f.affected == t.affected and f.currency == t.currency and
  |f.amount - t.amount| <= tolerance_minor (1) and some admissible evidence set of
  t is a subset of f.evidence.

Matching
  Maximum bipartite matching (Kuhn's augmenting paths). Findings are processed
  in submission order, issues in truth order (sorted by type, affected_ids,
  issue_id). The *size* of a maximum matching is unique, so TP/FP/FN do not
  depend on the tie-break; the order only fixes which duplicate finding is
  labelled TP in diagnostics. Unmatched findings are FP (this includes repeats),
  unmatched issues are FN.
"""

from __future__ import annotations

from dataclasses import dataclass

ISSUE_TYPES = ("duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff")
MAX_FINDINGS = 30
MAX_EVIDENCE = 10
MAX_AFFECTED = 10
MAX_EXPLANATION = 1000
MAX_ID_LEN = 64
MAX_AMOUNT = 10**15
FINDING_KEYS = {"type", "affected_ids", "claimed_amount_minor", "currency", "evidence_ids", "explanation"}
ROOT_KEYS = {"episode_id", "findings"}


class SubmissionError(ValueError):
    pass


@dataclass(frozen=True)
class NormFinding:
    type: str
    affected: frozenset
    amount: int
    currency: str
    evidence: frozenset


def _id_list(value, max_len: int, allow_empty: bool) -> list:
    if not isinstance(value, list) or len(value) > max_len or (not allow_empty and not value):
        raise SubmissionError("bad id list")
    out = []
    for v in value:
        if not isinstance(v, str) or not v.strip() or len(v) > MAX_ID_LEN:
            raise SubmissionError("bad id")
        out.append(v.strip())
    return out


def validate_submission(sub, episode_id: str) -> list:
    """Return the list of raw findings if the structure is valid, else raise SubmissionError."""
    if not isinstance(sub, dict) or set(sub) != ROOT_KEYS:
        raise SubmissionError("root must have exactly episode_id and findings")
    if sub["episode_id"] != episode_id:
        raise SubmissionError("episode_id mismatch")
    findings = sub["findings"]
    if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
        raise SubmissionError("findings must be a list of at most 30")
    for f in findings:
        if not isinstance(f, dict) or set(f) != FINDING_KEYS:
            raise SubmissionError("finding keys")
        if not isinstance(f["type"], str) or f["type"].strip().lower() not in ISSUE_TYPES:
            raise SubmissionError("type")
        _id_list(f["affected_ids"], MAX_AFFECTED, allow_empty=False)
        _id_list(f["evidence_ids"], MAX_EVIDENCE, allow_empty=True)
        amt = f["claimed_amount_minor"]
        if isinstance(amt, bool) or not isinstance(amt, int) or not 0 <= amt < MAX_AMOUNT:
            raise SubmissionError("amount")
        cur = f["currency"]
        if not isinstance(cur, str) or len(cur.strip()) != 3 or not cur.strip().isalpha():
            raise SubmissionError("currency")
        if not isinstance(f["explanation"], str) or len(f["explanation"]) > MAX_EXPLANATION:
            raise SubmissionError("explanation")
    return findings


class Aliases:
    """doc_id <-> business id maps built from the public records."""

    def __init__(self, public: dict):
        self.doc_to_business = {}
        self.business_to_doc = {}
        for inv in public["invoices"]:
            self.doc_to_business[inv["doc_id"]] = inv["invoice_id"]
            self.business_to_doc[inv["invoice_id"]] = inv["doc_id"]
        for pay in public["payments"]:
            self.doc_to_business[pay["doc_id"]] = pay["payment_id"]
            self.business_to_doc[pay["payment_id"]] = pay["doc_id"]


def normalize(f: dict, aliases: Aliases) -> NormFinding:
    affected = frozenset(aliases.doc_to_business.get(x, x) for x in (i.strip() for i in f["affected_ids"]))
    evidence = frozenset(aliases.business_to_doc.get(x, x) for x in (i.strip() for i in f["evidence_ids"]))
    return NormFinding(
        f["type"].strip().lower(), affected, f["claimed_amount_minor"], f["currency"].strip().upper(), evidence
    )


def is_candidate(f: NormFinding, issue: dict, tolerance: int) -> bool:
    return (
        f.type == issue["type"]
        and f.affected == frozenset(issue["affected_ids"])
        and f.currency == issue["currency"]
        and abs(f.amount - issue["expected_amount_minor"]) <= tolerance
        and any(set(es) <= f.evidence for es in issue["evidence_sets"])
    )


def match(findings: list, issues: list, tolerance: int) -> list:
    """Maximum one-to-one matching. Returns list of (finding_index, issue_index)."""
    adj = [[j for j, t in enumerate(issues) if is_candidate(f, t, tolerance)] for f in findings]
    issue_owner = [-1] * len(issues)

    def augment(i: int, seen: list) -> bool:
        for j in adj[i]:
            if seen[j]:
                continue
            seen[j] = True
            if issue_owner[j] == -1 or augment(issue_owner[j], seen):
                issue_owner[j] = i
                return True
        return False

    for i in range(len(findings)):
        augment(i, [False] * len(issues))
    return sorted((i, j) for j, i in enumerate(issue_owner) if i != -1)
