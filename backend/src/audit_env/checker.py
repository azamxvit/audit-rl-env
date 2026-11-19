"""Independent data checker — works only from PUBLIC records + policy.

This module deliberately does not import the generator, the world model or the
injectors. It re-implements the bookkeeping rules stated in ``policy.json`` and
is used to verify, for every episode:

1. accounting invariants (balanced entries, one-sided rows, functional currency,
   referential integrity) — before *and* after injection;
2. that a full rule-based audit of the clean books finds nothing (distractors are
   really legitimate) and of the injected books finds exactly ``truth.json``
   (no undeclared errors, no unsolvable declared ones);
3. that every admissible evidence set, on its own, is sufficient to re-derive the
   issue's type, affected IDs and amount ("independent sufficiency").
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from .money import CURRENCY_EXPONENTS, convert


class CheckError(AssertionError):
    pass


def _tz(label: str) -> timezone:
    sign = 1 if label[0] == "+" else -1
    hh, mm = label[1:].split(":")
    return timezone(sign * timedelta(hours=int(hh), minutes=int(mm)))


def _dt(text: str) -> datetime:
    d = datetime.fromisoformat(text)
    if d.tzinfo is None:
        raise CheckError("timestamp without offset")
    return d


@dataclass
class Books:
    public: dict
    base: str = ""
    tz: timezone = timezone.utc
    start: date = date.min
    end: date = date.max
    rounding: str = "half_even"
    invoices: dict = field(default_factory=dict)
    inv_by_doc: dict = field(default_factory=dict)
    payments: dict = field(default_factory=dict)
    pay_by_doc: dict = field(default_factory=dict)
    rows: dict = field(default_factory=dict)
    entries: dict = field(default_factory=dict)
    fx: dict = field(default_factory=dict)  # rate_id -> record
    fx_by_ccy: dict = field(default_factory=dict)  # ccy -> sorted [(date, record)]

    @classmethod
    def from_public(cls, public: dict) -> "Books":
        m = public["manifest"]
        b = cls(
            public,
            m["base_currency"],
            _tz(m["timezone"]),
            date.fromisoformat(m["period_start"]),
            date.fromisoformat(m["period_end"]),
            public["policy"]["rounding"]["mode"],
        )
        for inv in public["invoices"]:
            b.invoices[inv["invoice_id"]] = inv
            b.inv_by_doc[inv["doc_id"]] = inv
        for pay in public["payments"]:
            b.payments[pay["payment_id"]] = pay
            b.pay_by_doc[pay["doc_id"]] = pay
        for r in public["ledger"]:
            b.rows[r["row_id"]] = r
            b.entries.setdefault(r["entry_id"], []).append(r)
        for f in public["fx"]:
            b.fx[f["rate_id"]] = f
            b.fx_by_ccy.setdefault(f["source_currency"], []).append((date.fromisoformat(f["date"]), f))
        for lst in b.fx_by_ccy.values():
            lst.sort(key=lambda x: x[0])
        return b

    def local(self, ts: str) -> date:
        return _dt(ts).astimezone(self.tz).date()

    def in_period(self, ts: str) -> bool:
        return self.start <= self.local(ts) <= self.end

    def rate(self, ccy: str, day: date) -> dict:
        best = None
        for d, rec in self.fx_by_ccy.get(ccy, []):
            if d <= day:
                best = rec
        if best is None:
            raise CheckError("no fx rate on or before date")
        return best

    def to_base(self, amount: int, ccy: str, rate: str) -> int:
        return convert(amount, ccy, self.base, rate, self.rounding)


# --------------------------------------------------------------------------- invariants


def check_invariants(public: dict) -> list:
    """Return a list of human-readable violations (empty = OK)."""
    b = Books.from_public(public)
    problems = []
    ids = (
        [r["row_id"] for r in public["ledger"]]
        + [i["doc_id"] for i in public["invoices"]]
        + [p["doc_id"] for p in public["payments"]]
    )
    if len(ids) != len(set(ids)):
        problems.append("duplicate record ids")
    if len(b.invoices) != len(public["invoices"]) or len(b.payments) != len(public["payments"]):
        problems.append("duplicate business ids")
    total_d = total_c = 0
    for entry_id, rows in b.entries.items():
        d = sum(r["debit_minor"] for r in rows)
        c = sum(r["credit_minor"] for r in rows)
        total_d += d
        total_c += c
        if d != c:
            problems.append(f"unbalanced entry {entry_id}")
        if len({r["timestamp"] for r in rows}) != 1:
            problems.append(f"entry {entry_id} spans timestamps")
        for r in rows:
            if (r["debit_minor"] > 0) == (r["credit_minor"] > 0) or min(r["debit_minor"], r["credit_minor"]) < 0:
                problems.append(f"row {r['row_id']} not one-sided")
            if r["currency"] != b.base:
                problems.append(f"row {r['row_id']} not in functional currency")
            if not b.in_period(r["timestamp"]):
                problems.append(f"row {r['row_id']} outside period")
            if r["invoice_id"] is not None and r["invoice_id"] not in b.invoices:
                problems.append(f"row {r['row_id']} references unknown invoice")
            if r["payment_id"] is not None and r["payment_id"] not in b.payments:
                problems.append(f"row {r['row_id']} references unknown payment")
            if r["account"] not in public["policy"]["accounts"]:
                problems.append(f"row {r['row_id']} unknown account")
    if total_d != total_c:
        problems.append("trial balance does not balance")
    for inv in public["invoices"]:
        if sum(li["amount_minor"] for li in inv["line_items"]) != inv["total_minor"]:
            problems.append(f"invoice {inv['invoice_id']} lines do not sum to total")
        for li in inv["line_items"]:
            if li["quantity"] * li["unit_price_minor"] != li["amount_minor"]:
                problems.append(f"invoice {inv['invoice_id']} line amount mismatch")
        if inv["currency"] not in CURRENCY_EXPONENTS:
            problems.append("unknown currency")
    for pay in public["payments"]:
        refs = pay["invoice_refs"]
        if refs is not None:
            if sum(r["amount_minor"] for r in refs) > pay["amount_minor"]:
                problems.append(f"payment {pay['payment_id']} references exceed amount")
            for r in refs:
                if r["invoice_id"] not in b.invoices:
                    problems.append(f"payment {pay['payment_id']} references unknown invoice")
                elif b.invoices[r["invoice_id"]]["currency"] != pay["currency"]:
                    problems.append(f"payment {pay['payment_id']} currency differs from invoice")
    # every invoice is never over-settled by remittances
    settled: dict = {}
    for pay in public["payments"]:
        for r in pay["invoice_refs"] or []:
            settled[r["invoice_id"]] = settled.get(r["invoice_id"], 0) + r["amount_minor"]
    for inv_id, amt in settled.items():
        if inv_id in b.invoices and amt > b.invoices[inv_id]["total_minor"]:
            problems.append(f"invoice {inv_id} over-settled")
    return problems


# --------------------------------------------------------------------------- full audit


def _invoice_bookings(b: Books) -> dict:
    out: dict = {}
    for rows in b.entries.values():
        for r in rows:
            if r["account"] == "1100" and r["debit_minor"] > 0 and r["invoice_id"] and r["payment_id"] is None:
                out.setdefault(r["invoice_id"], []).append(r)
    return out


def _content_key(inv: dict) -> str:
    return json.dumps(
        [
            inv["entity_id"],
            inv["currency"],
            inv["total_minor"],
            sorted(json.dumps(li, sort_keys=True) for li in inv["line_items"]),
        ]
    )


def audit(public: dict, tolerance: int = 1) -> list:
    """Rule-based full audit. Returns findings as dicts {type, affected_ids, amount_minor, currency}."""
    b = Books.from_public(public)
    found = []

    def add(t, ids, amount):
        found.append({"type": t, "affected_ids": sorted(ids), "amount_minor": amount, "currency": b.base})

    bookings = _invoice_bookings(b)
    groups: dict = {}
    for inv_id, rows in sorted(bookings.items()):
        inv = b.invoices[inv_id]
        booked = sum(r["debit_minor"] for r in rows)
        if not b.in_period(inv["issued_at"]):
            add("period_cutoff", [inv_id], booked)
        if inv["currency"] != b.base:
            rate = b.rate(inv["currency"], b.local(inv["issued_at"]))
            diff = booked - b.to_base(inv["total_minor"], inv["currency"], rate["rate"])
            if abs(diff) > tolerance:
                add("fx_error", [inv_id], abs(diff))
        groups.setdefault(_content_key(inv), []).append(inv)
    for invs in groups.values():
        if len(invs) < 2:
            continue
        invs.sort(key=lambda i: (_dt(i["issued_at"]), i["invoice_id"]))
        first = invs[0]
        for later in invs[1:]:
            add(
                "duplicate_invoice",
                [first["invoice_id"], later["invoice_id"]],
                sum(r["debit_minor"] for r in bookings[later["invoice_id"]]),
            )

    pay_rows: dict = {}
    for r in b.rows.values():
        if r["payment_id"]:
            pay_rows.setdefault(r["payment_id"], []).append(r)
    for pay_id, rows in sorted(pay_rows.items()):
        pay = b.payments[pay_id]
        if pay["kind"] != "receipt":
            continue
        rate = "1" if pay["currency"] == b.base else b.rate(pay["currency"], b.local(pay["timestamp"]))["rate"]
        bank = sum(r["debit_minor"] for r in rows if r["account"] == "1000")
        if pay["currency"] != b.base:
            diff = bank - b.to_base(pay["amount_minor"], pay["currency"], rate)
            if abs(diff) > tolerance:
                add("fx_error", [pay_id], abs(diff))
        refs = pay["invoice_refs"] or []
        unref = pay["amount_minor"] - sum(r["amount_minor"] for r in refs)
        expected_unapplied = b.to_base(unref, pay["currency"], rate) if unref > 0 else 0
        actual_unapplied = sum(r["credit_minor"] for r in rows if r["account"] == "2200")
        excess = actual_unapplied - expected_unapplied
        if excess > tolerance:
            applied = {r["invoice_id"] for r in rows if r["account"] == "1100" and r["credit_minor"] > 0}
            if len(refs) == 1:
                missing = [refs[0]["invoice_id"]]
            else:
                missing = [r["invoice_id"] for r in refs if r["invoice_id"] not in applied]
            add("payment_allocation", [pay_id] + missing, excess)
    found.sort(key=lambda f: (f["type"], f["affected_ids"]))
    return found


# --------------------------------------------------------------------------- evidence sufficiency


def derive_from_evidence(issue_type: str, evidence_ids: list, public: dict) -> dict:
    """Re-derive {type, affected_ids, amount_minor} using ONLY the evidence records (+ policy/manifest)."""
    b = Books.from_public(public)
    docs_inv = [b.inv_by_doc[e] for e in evidence_ids if e in b.inv_by_doc]
    docs_pay = [b.pay_by_doc[e] for e in evidence_ids if e in b.pay_by_doc]
    rows = [b.rows[e] for e in evidence_ids if e in b.rows]
    fxs = [b.fx[e] for e in evidence_ids if e in b.fx]
    if len(docs_inv) + len(docs_pay) + len(rows) + len(fxs) != len(set(evidence_ids)):
        raise CheckError("evidence references unknown records")

    def booking_amount(row: dict, inv_id: str) -> int:
        if row["invoice_id"] != inv_id or row["payment_id"] is not None:
            raise CheckError("row is not the booking of this invoice")
        if row["account"] == "1100" and row["debit_minor"] > 0:
            return row["debit_minor"]
        if row["account"] == "4000" and row["credit_minor"] > 0:
            return row["credit_minor"]
        raise CheckError("row is not an AR/revenue booking row")

    if issue_type == "duplicate_invoice":
        if len(docs_inv) != 2 or len(rows) != 2:
            raise CheckError("duplicate needs two invoices and their bookings")
        a, c = sorted(docs_inv, key=lambda i: (_dt(i["issued_at"]), i["invoice_id"]))
        if _content_key(a) != _content_key(c):
            raise CheckError("documents differ")
        if not all(b.in_period(r["timestamp"]) for r in rows):
            raise CheckError("booking outside period")
        by_inv = {r["invoice_id"]: r for r in rows}
        if set(by_inv) != {a["invoice_id"], c["invoice_id"]}:
            raise CheckError("bookings do not cover both copies")
        booking_amount(by_inv[a["invoice_id"]], a["invoice_id"])
        amount = booking_amount(by_inv[c["invoice_id"]], c["invoice_id"])
        return {"type": issue_type, "affected_ids": sorted([a["invoice_id"], c["invoice_id"]]), "amount_minor": amount}

    if issue_type == "payment_allocation":
        if len(docs_pay) != 1 or len(rows) != 1:
            raise CheckError("allocation needs the payment and its unapplied row")
        pay, row = docs_pay[0], rows[0]
        refs = pay["invoice_refs"] or []
        if pay["kind"] != "receipt" or len(refs) != 1 or refs[0]["amount_minor"] != pay["amount_minor"]:
            raise CheckError("payment is not fully referenced to one invoice")
        if row["account"] != "2200" or row["credit_minor"] <= 0 or row["payment_id"] != pay["payment_id"]:
            raise CheckError("row is not unapplied cash of this payment")
        return {
            "type": issue_type,
            "affected_ids": sorted([pay["payment_id"], refs[0]["invoice_id"]]),
            "amount_minor": row["credit_minor"],
        }

    if issue_type == "fx_error":
        if len(docs_inv) + len(docs_pay) != 1 or len(rows) != 1 or len(fxs) != 1:
            raise CheckError("fx needs document, booking row and fx rate")
        fx, row = fxs[0], rows[0]
        if docs_inv:
            doc = docs_inv[0]
            day = b.local(doc["issued_at"])
            booked = booking_amount(row, doc["invoice_id"])
            amount, bid = doc["total_minor"], doc["invoice_id"]
        else:
            doc = docs_pay[0]
            day = b.local(doc["timestamp"])
            if row["account"] != "1000" or row["debit_minor"] <= 0 or row["payment_id"] != doc["payment_id"]:
                raise CheckError("row is not the bank row of this payment")
            booked, amount, bid = row["debit_minor"], doc["amount_minor"], doc["payment_id"]
        fx_day = date.fromisoformat(fx["date"])
        if fx["source_currency"] != doc["currency"] or fx["target_currency"] != b.base or fx_day > day:
            raise CheckError("fx rate does not apply")
        d = fx_day + timedelta(days=1)
        while d <= day:  # policy: rates published Mon-Fri; fx row must be the latest business day
            if d.weekday() < 5:
                raise CheckError("a later published rate exists")
            d += timedelta(days=1)
        diff = abs(booked - b.to_base(amount, doc["currency"], fx["rate"]))
        return {"type": issue_type, "affected_ids": [bid], "amount_minor": diff}

    if issue_type == "period_cutoff":
        if len(docs_inv) != 1 or len(rows) != 1:
            raise CheckError("cutoff needs invoice and booking row")
        doc, row = docs_inv[0], rows[0]
        if b.in_period(doc["issued_at"]) or not b.in_period(row["timestamp"]):
            raise CheckError("no cut-off violation visible")
        return {
            "type": issue_type,
            "affected_ids": [doc["invoice_id"]],
            "amount_minor": booking_amount(row, doc["invoice_id"]),
        }

    raise CheckError("unknown issue type")


def verify_episode(public: dict, truth: dict, clean_public: dict | None = None) -> list:
    """Full independent verification. Returns a list of problems (empty = episode is valid)."""
    problems = []
    tol = truth.get("tolerance_minor", 1)
    if clean_public is not None:
        problems += [f"clean: {p}" for p in check_invariants(clean_public)]
        problems += [f"clean books not clean: {f}" for f in audit(clean_public, tol)]
    problems += [f"injected: {p}" for p in check_invariants(public)]
    found = audit(public, tol)
    expected = sorted(
        (
            {
                "type": i["type"],
                "affected_ids": i["affected_ids"],
                "amount_minor": i["expected_amount_minor"],
                "currency": i["currency"],
            }
            for i in truth["issues"]
        ),
        key=lambda f: (f["type"], f["affected_ids"]),
    )
    if [(f["type"], f["affected_ids"]) for f in found] != [(f["type"], f["affected_ids"]) for f in expected]:
        problems.append(f"audit/truth mismatch: found={found} expected={expected}")
    else:
        for f, e in zip(found, expected, strict=False):
            if abs(f["amount_minor"] - e["amount_minor"]) > tol or f["currency"] != e["currency"]:
                problems.append(f"amount mismatch {f} vs {e}")
    for issue in truth["issues"]:
        if not issue["evidence_sets"]:
            problems.append(f"{issue['issue_id']}: no evidence sets")
        for ev in issue["evidence_sets"]:
            if len(ev) > 10:
                problems.append(f"{issue['issue_id']}: evidence set larger than submit limit")
            try:
                got = derive_from_evidence(issue["type"], ev, public)
            except CheckError as exc:
                problems.append(f"{issue['issue_id']}: evidence {ev} insufficient: {exc}")
                continue
            if got["affected_ids"] != issue["affected_ids"] or got["amount_minor"] != issue["expected_amount_minor"]:
                problems.append(f"{issue['issue_id']}: evidence derives {got}")
        if issue["expected_amount_minor"] <= tol:
            problems.append(f"{issue['issue_id']}: immaterial amount")
    return problems
