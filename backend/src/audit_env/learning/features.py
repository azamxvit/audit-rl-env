"""Candidates and features for the learned auditor, built from PUBLIC records only.

The same function runs at training time (on ``Episode.public``) and inside the
policy (on the tables it paged through with ``list_records``), so the model sees
exactly what an agent can see. Nothing here reads truth, provenance or seeds.

Three candidate kinds, each with its own feature vector and output heads:

* ``invoice`` - every invoice with an AR booking (Dr 1100, no payment_id);
  heads ``period_cutoff`` and ``fx_error``.
* ``payment`` - every receipt with ledger rows; heads ``payment_allocation``
  and ``fx_error``.
* ``pair``    - two booked invoices of one customer with the same currency and
  total (cheap blocking, as in record linkage); head ``duplicate_invoice``.

Several features are deliberately competing hypotheses (company time zone vs the
printed offset vs UTC, rate on the document date vs the booking date vs the
printed date): the distractors in the generator make the wrong ones misleading,
and the model has to learn which signal the policy actually uses.

The learned part is detection only. Once a candidate is flagged, the amount and
the evidence IDs are assembled deterministically from the same records.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from ..money import MoneyError, convert
from ..util import parse_tz_label

HEADS = {
    "invoice": ("period_cutoff", "fx_error"),
    "payment": ("payment_allocation", "fx_error"),
    "pair": ("duplicate_invoice",),
}

FEATURES = {
    "invoice": (
        "foreign",
        "outside_period_company_tz",
        "outside_period_printed_offset",
        "outside_period_utc",
        "days_outside_company_tz",
        "within_1d_of_boundary",
        "booking_lag_days",
        "fx_gap_document_date",
        "fx_gap_document_date_rel",
        "fx_gap_printed_date",
        "fx_gap_booking_date",
        "fx_rate_missing",
        "bookings_count",
        "log_amount",
    ),
    "payment": (
        "foreign",
        "fx_gap_value_date",
        "fx_gap_value_date_rel",
        "fx_gap_printed_date",
        "refs_count",
        "refs_cover_payment",
        "single_full_ref",
        "unapplied_share",
        "unapplied_excess",
        "unapplied_excess_rel",
        "has_fx_difference_row",
        "within_1d_of_boundary",
        "log_amount",
    ),
    "pair": (
        "line_items_identical",
        "descriptions_identical",
        "service_periods_identical",
        "hours_apart",
        "same_local_day",
        "group_size",
        "both_issued_in_period",
    ),
}


@dataclass
class Candidate:
    kind: str
    key: tuple  # ("invoice", inv_id) / ("payment", pay_id) / ("pair", first_id, later_id)
    x: list
    # Deterministic finding templates per head: (affected_ids, amount_minor, evidence_ids)
    findings: dict = field(default_factory=dict)


def _clip(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _log_amount(minor: int) -> float:
    return _clip(math.log10(abs(minor) + 1) / 9, 0.0, 1.0)


def _rel(diff: int, base: int) -> float:
    return _clip(100 * abs(diff) / max(abs(base), 1), 0.0, 1.0)


class _Books:
    def __init__(self, public: dict):
        m = public["manifest"]
        self.base = m["base_currency"]
        self.tz = parse_tz_label(m["timezone"])
        self.start = date.fromisoformat(m["period_start"])
        self.end = date.fromisoformat(m["period_end"])
        self.rounding = public["policy"]["rounding"]["mode"]
        self.invoices = {i["invoice_id"]: i for i in public["invoices"]}
        self.rates: dict = {}
        for f in public["fx"]:
            if f["target_currency"] == self.base:
                self.rates.setdefault(f["source_currency"], []).append((date.fromisoformat(f["date"]), f))
        for lst in self.rates.values():
            lst.sort(key=lambda x: (x[0], x[1]["rate_id"]))
        self.ar: dict = {}  # invoice_id -> AR booking rows
        self.by_payment: dict = {}
        for r in public["ledger"]:
            if r["account"] == "1100" and r["debit_minor"] > 0 and r["invoice_id"] and r["payment_id"] is None:
                self.ar.setdefault(r["invoice_id"], []).append(r)
            if r["payment_id"]:
                self.by_payment.setdefault(r["payment_id"], []).append(r)

    def local(self, ts: str) -> date:
        return datetime.fromisoformat(ts).astimezone(self.tz).date()

    def outside(self, d: date) -> bool:
        return not (self.start <= d <= self.end)

    def days_outside(self, d: date) -> int:
        return max((self.start - d).days, (d - self.end).days, 0)

    def near_boundary(self, d: date) -> bool:
        return min(abs((d - self.start).days), abs((d - self.end).days)) <= 1

    def rate(self, ccy: str, day: date):
        best = None
        for d, rec in self.rates.get(ccy, []):
            if d > day:
                break
            best = rec
        return best

    def gap(self, booked: int, amount: int, ccy: str, day: date):
        """(booked - converted at the rate in force on ``day``, fx record) or (None, None)."""
        rec = self.rate(ccy, day)
        if rec is None:
            return None, None
        try:
            return booked - convert(amount, ccy, self.base, rec["rate"], self.rounding), rec
        except MoneyError:
            return None, None


def _printed_date(ts: str) -> date:
    return date.fromisoformat(ts[:10])


def _invoice_candidates(b: _Books) -> list:
    out = []
    for inv_id in sorted(b.ar):
        inv = b.invoices.get(inv_id)
        if inv is None:
            continue
        rows = b.ar[inv_id]
        row = rows[0]
        booked = sum(r["debit_minor"] for r in rows)
        issued = b.local(inv["issued_at"])
        printed = _printed_date(inv["issued_at"])
        utc_day = datetime.fromisoformat(inv["issued_at"]).astimezone(timezone.utc).date()
        booked_day = b.local(row["timestamp"])
        foreign = inv["currency"] != b.base
        g_doc = g_printed = g_booking = None
        fx_rec = None
        if foreign:
            g_doc, fx_rec = b.gap(booked, inv["total_minor"], inv["currency"], issued)
            g_printed, _ = b.gap(booked, inv["total_minor"], inv["currency"], printed)
            g_booking, _ = b.gap(booked, inv["total_minor"], inv["currency"], booked_day)
        x = [
            float(foreign),
            float(b.outside(issued)),
            float(b.outside(printed)),
            float(b.outside(utc_day)),
            _clip(b.days_outside(issued) / 31, 0.0, 1.0),
            float(b.near_boundary(issued)),
            _clip((booked_day - issued).days / 3),
            float(g_doc is not None and abs(g_doc) > 1),
            _rel(g_doc, booked) if g_doc is not None else 0.0,
            float(g_printed is not None and abs(g_printed) > 1),
            float(g_booking is not None and abs(g_booking) > 1),
            float(foreign and g_doc is None),
            _clip((len(rows) - 1) / 2, 0.0, 1.0),
            _log_amount(booked),
        ]
        c = Candidate("invoice", ("invoice", inv_id), x)
        c.findings["period_cutoff"] = ([inv_id], booked, [inv["doc_id"], row["row_id"]])
        if g_doc is not None and fx_rec is not None:
            c.findings["fx_error"] = ([inv_id], abs(g_doc), [inv["doc_id"], row["row_id"], fx_rec["rate_id"]])
        out.append(c)
    return out


def _payment_candidates(b: _Books, payments: list) -> list:
    out = []
    for pay in sorted(payments, key=lambda p: p["payment_id"]):
        rows = b.by_payment.get(pay["payment_id"], [])
        if pay["kind"] != "receipt" or not rows:
            continue
        bank_rows = [r for r in rows if r["account"] == "1000" and r["debit_minor"] > 0]
        unapplied_rows = [r for r in rows if r["account"] == "2200" and r["credit_minor"] > 0]
        bank = sum(r["debit_minor"] for r in bank_rows)
        unapplied = sum(r["credit_minor"] for r in unapplied_rows)
        refs = pay["invoice_refs"] or []
        ref_sum = sum(r["amount_minor"] for r in refs)
        day = b.local(pay["timestamp"])
        foreign = pay["currency"] != b.base
        g_val = g_printed = None
        fx_rec = None
        rate = "1"
        if foreign:
            g_val, fx_rec = b.gap(bank, pay["amount_minor"], pay["currency"], day)
            g_printed, _ = b.gap(bank, pay["amount_minor"], pay["currency"], _printed_date(pay["timestamp"]))
            rate = fx_rec["rate"] if fx_rec else None
        unref = pay["amount_minor"] - ref_sum
        expected_unapplied = 0
        if unref > 0 and rate is not None:
            try:
                expected_unapplied = convert(unref, pay["currency"], b.base, rate, b.rounding)
            except MoneyError:
                expected_unapplied = 0
        excess = unapplied - expected_unapplied
        x = [
            float(foreign),
            float(g_val is not None and abs(g_val) > 1),
            _rel(g_val, bank) if g_val is not None else 0.0,
            float(g_printed is not None and abs(g_printed) > 1),
            _clip(len(refs) / 3, 0.0, 1.0),
            float(bool(refs) and ref_sum == pay["amount_minor"]),
            float(len(refs) == 1 and ref_sum == pay["amount_minor"]),
            _clip(unapplied / max(bank, 1), 0.0, 1.0),
            float(excess > 1),
            _clip(excess / max(bank, 1), -1.0, 1.0),
            float(any(r["account"] == "7900" for r in rows)),
            float(b.near_boundary(day)),
            _log_amount(bank),
        ]
        c = Candidate("payment", ("payment", pay["payment_id"]), x)
        if unapplied_rows and len(refs) == 1:
            c.findings["payment_allocation"] = (
                [pay["payment_id"], refs[0]["invoice_id"]],
                unapplied_rows[0]["credit_minor"],
                [pay["doc_id"], unapplied_rows[0]["row_id"]],
            )
        if g_val is not None and fx_rec is not None and bank_rows:
            c.findings["fx_error"] = (
                [pay["payment_id"]],
                abs(g_val),
                [pay["doc_id"], bank_rows[0]["row_id"], fx_rec["rate_id"]],
            )
        out.append(c)
    return out


PERIOD_KEYS = ("service_period_start", "service_period_end")
LINE_KEYS = ("description", "quantity", "unit_price_minor", "amount_minor") + PERIOD_KEYS


def _lines(inv: dict, keys) -> list:
    return sorted(json.dumps({k: li.get(k) for k in keys}, sort_keys=True) for li in inv["line_items"])


def _pair_candidates(b: _Books) -> list:
    groups: dict = {}
    for inv_id in sorted(b.ar):
        inv = b.invoices.get(inv_id)
        if inv is not None:
            groups.setdefault((inv["entity_id"], inv["currency"], inv["total_minor"]), []).append(inv)
    out = []
    for key in sorted(groups):
        invs = groups[key]
        if len(invs) < 2:
            continue
        invs.sort(key=lambda i: (datetime.fromisoformat(i["issued_at"]), i["invoice_id"]))
        for i, first in enumerate(invs):
            for later in invs[i + 1 :]:
                out.append(_pair(b, first, later, len(invs)))
    return out


def _pair(b: _Books, first: dict, later: dict, group_size: int) -> Candidate:
    hours = (
        datetime.fromisoformat(later["issued_at"]) - datetime.fromisoformat(first["issued_at"])
    ).total_seconds() / 3600
    x = [
        float(_lines(first, LINE_KEYS) == _lines(later, LINE_KEYS)),
        float(_lines(first, ("description",)) == _lines(later, ("description",))),
        float(_lines(first, PERIOD_KEYS) == _lines(later, PERIOD_KEYS)),
        _clip(hours / 72, 0.0, 1.0),
        float(b.local(first["issued_at"]) == b.local(later["issued_at"])),
        _clip((group_size - 2) / 3, 0.0, 1.0),
        float(not b.outside(b.local(first["issued_at"])) and not b.outside(b.local(later["issued_at"]))),
    ]
    ra, rb = b.ar[first["invoice_id"]][0], b.ar[later["invoice_id"]][0]
    c = Candidate("pair", ("pair", first["invoice_id"], later["invoice_id"]), x)
    c.findings["duplicate_invoice"] = (
        [first["invoice_id"], later["invoice_id"]],
        sum(r["debit_minor"] for r in b.ar[later["invoice_id"]]),
        [first["doc_id"], later["doc_id"], ra["row_id"], rb["row_id"]],
    )
    return c


def extract(public: dict) -> list:
    """All candidates of an episode, in a deterministic order."""
    b = _Books(public)
    return _invoice_candidates(b) + _payment_candidates(b, public["payments"]) + _pair_candidates(b)


def labels(candidates: list, truth: dict) -> list:
    """Training targets (grader side only): per candidate, the set of heads that are real issues."""
    issues = {(i["type"], tuple(sorted(i["affected_ids"]))) for i in truth["issues"]}
    out = []
    for c in candidates:
        y = {}
        for head in HEADS[c.kind]:
            if c.kind == "invoice":
                ids = (c.key[1],)
            elif c.kind == "payment" and head == "fx_error":
                ids = (c.key[1],)
            elif c.kind == "payment":
                tmpl = c.findings.get(head)
                ids = tuple(sorted(tmpl[0])) if tmpl else None
            else:
                ids = tuple(sorted(c.key[1:]))
            y[head] = float(ids is not None and (head, ids) in issues)
        out.append(y)
    return out


def coverage(candidates: list, truth: dict) -> float:
    """Share of truth issues some candidate can express (the recall ceiling of the learned policy)."""
    if not truth["issues"]:
        return 1.0
    reachable = set()
    for c in candidates:
        for head, (ids, _amt, _ev) in c.findings.items():
            reachable.add((head, tuple(sorted(ids))))
    hit = sum((i["type"], tuple(sorted(i["affected_ids"]))) in reachable for i in truth["issues"])
    return hit / len(truth["issues"])
