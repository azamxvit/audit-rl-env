"""Submission validation, normalisation and one-to-one matching against truth.

Published rules (also in DESIGN.md §5); they follow the organisers' check definitions
("Точные соглашения matcher"):

Structure (a violation makes the whole submit invalid: reward -1, error in the grader log)
  * root: exactly {episode_id, findings}; episode_id equals the episode; findings: list of <= 30.
  * finding: exactly {type, affected_ids, claimed_amount_minor, currency, evidence_ids, explanation};
    type/currency/explanation are strings, explanation <= 1000 Unicode code points;
    affected_ids/evidence_ids are lists of strings, evidence_ids <= 10 items counted BEFORE
    removing repeats; claimed_amount_minor is a JSON integer (not bool, string or float).

Normalisation (no case folding, no whitespace trimming, no fuzzy ids)
  * ids are compared exactly. The one published alias: a document may be named by its doc_id or
    by its business id (invoice_id / payment_id) - both are exact ids of the same open record.
    affected_ids map doc_id -> business id, evidence_ids map business id -> doc_id.
  * affected_ids and evidence_ids are sets (order and repeats inside a list do not matter).
  * type and currency are compared exactly; an unknown type string is simply never matched (FP).

Candidate pair (finding f, issue t) iff
  f.type == t.type and f.affected == t.affected and f.currency == t.currency and
  |f.amount - t.amount| <= tolerance_minor (truth.json; 0 by default = exact) and every evidence
  id exists among the open records and some admissible evidence set of t is a subset of f.evidence.

Matching
  Maximum-cardinality bipartite matching (Kuhn) - never greedy, so TP does not depend on the
  order of findings. Among maximum matchings the deterministic choice is the lexicographically
  smallest sequence of (issue_id, finding index) pairs, issue_ids sorted by code point. This only
  decides which of identical findings is labelled TP in diagnostics; TP/FP/FN and the reward depend
  on the matching size alone. Unmatched findings (including repeats) are FP, unmatched issues FN.
"""

from __future__ import annotations

from dataclasses import dataclass

ISSUE_TYPES = ("duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff")
MAX_FINDINGS = 30
MAX_EVIDENCE = 10
MAX_EXPLANATION = 1000
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
    evidence_exists: bool


def _str_list(value, max_len: int | None) -> None:
    if not isinstance(value, list) or (max_len is not None and len(value) > max_len):
        raise SubmissionError("bad id list")
    if not all(isinstance(v, str) for v in value):
        raise SubmissionError("bad id")


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
        if not isinstance(f["type"], str):
            raise SubmissionError("type")
        _str_list(f["affected_ids"], None)
        _str_list(f["evidence_ids"], MAX_EVIDENCE)
        amt = f["claimed_amount_minor"]
        if isinstance(amt, bool) or not isinstance(amt, int):
            raise SubmissionError("amount")
        if not isinstance(f["currency"], str):
            raise SubmissionError("currency")
        if not isinstance(f["explanation"], str) or len(f["explanation"]) > MAX_EXPLANATION:
            raise SubmissionError("explanation")
    return findings


class Aliases:
    """doc_id <-> business id maps and the set of every open record id, built from the public records."""

    def __init__(self, public: dict):
        self.doc_to_business = {}
        self.business_to_doc = {}
        self.known = {r["row_id"] for r in public["ledger"]} | {r["rate_id"] for r in public["fx"]}
        self.known |= {d["doc_id"] for t in ("invoices", "payments") for d in public[t]}
        for inv in public["invoices"]:
            self.doc_to_business[inv["doc_id"]] = inv["invoice_id"]
            self.business_to_doc[inv["invoice_id"]] = inv["doc_id"]
        for pay in public["payments"]:
            self.doc_to_business[pay["doc_id"]] = pay["payment_id"]
            self.business_to_doc[pay["payment_id"]] = pay["doc_id"]


def normalize(f: dict, aliases: Aliases) -> NormFinding:
    affected = frozenset(aliases.doc_to_business.get(x, x) for x in f["affected_ids"])
    evidence = frozenset(aliases.business_to_doc.get(x, x) for x in f["evidence_ids"])
    return NormFinding(
        f["type"], affected, f["claimed_amount_minor"], f["currency"], evidence, evidence <= aliases.known
    )


def is_candidate(f: NormFinding, issue: dict, tolerance: int) -> bool:
    return (
        f.type == issue["type"]
        and f.affected == frozenset(issue["affected_ids"])
        and f.currency == issue["currency"]
        and abs(f.amount - issue["expected_amount_minor"]) <= tolerance
        and f.evidence_exists
        and any(set(es) <= f.evidence for es in issue["evidence_sets"])
    )


def _max_matching(adj: dict, left: list, right: set) -> int:
    """Size of a maximum matching between ``left`` (issue indices) and ``right`` (finding indices)."""
    owner: dict = {}

    def augment(j: int, seen: set) -> bool:
        for i in adj[j]:
            if i in right and i not in seen:
                seen.add(i)
                if i not in owner or augment(owner[i], seen):
                    owner[i] = j
                    return True
        return False

    return sum(augment(j, set()) for j in left)


def match(findings: list, issues: list, tolerance: int) -> list:
    """Maximum one-to-one matching with the published deterministic choice.

    Returns sorted (finding_index, issue_index) pairs.
    """
    adj = {j: [i for i, f in enumerate(findings) if is_candidate(f, t, tolerance)] for j, t in enumerate(issues)}
    order = sorted(range(len(issues)), key=lambda j: issues[j].get("issue_id", ""))
    free = set(range(len(findings)))
    best = _max_matching(adj, order, free)
    pairs = []
    for pos, j in enumerate(order):
        rest = order[pos + 1 :]
        for i in adj[j]:  # finding indices ascending
            if i in free and 1 + _max_matching(adj, rest, free - {i}) == best - len(pairs):
                pairs.append((i, j))
                free.discard(i)
                break
    return sorted(pairs)
