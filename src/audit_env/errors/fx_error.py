"""fx_error: a foreign-currency document booked with the wrong rate date or a wrong rate.

Variants:
- ``wrong_date``: rate of another published date (printed date in the
  counterparty's offset, booking date, due date, or a nearby day);
- ``stale_rate``: a rate several weeks old;
- ``inverted``: the reciprocal of the correct rate (wrong direction).
Canonical form: affected_ids = [invoice_id] or [payment_id]; amount =
|booked functional amount - amount at the policy rate|. Evidence: the document,
the booking row (AR/revenue for invoices, bank for payments) and the fx row the
policy prescribes.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from ..world import Invoice, Payment, _fmt_rate
from .base import InjectionContext, IssueSpec, evidence_product, min_material_diff, printed_date


def _doc_time(obj):
    return obj.issued_at if isinstance(obj, Invoice) else obj.timestamp


def _amount(obj) -> int:
    return obj.total_minor if isinstance(obj, Invoice) else obj.amount_minor


def _candidate_dates(ctx: InjectionContext, obj, variant: str) -> list:
    w = ctx.world
    d0 = w.local(_doc_time(obj))
    if variant == "stale_rate":
        return [d0 - timedelta(days=k) for k in range(20, 46)]
    out = [printed_date(obj), w.local(obj.booking_ts)]
    if isinstance(obj, Invoice):
        out.append(w.local(obj.due_at))
    out += [d0 + timedelta(days=k) for k in (-3, -2, -1, 1, 2, 3)]
    return out


def _try_override(ctx: InjectionContext, obj, variant: str, prefer: Optional[date] = None) -> Optional[str]:
    """Set a wrong rate on ``obj``; returns the variant actually applied or None."""
    w, rng = ctx.world, ctx.rng
    amount = _amount(obj)
    correct_rate = w.policy_rate(obj.currency, _doc_time(obj))
    correct = w.to_base(amount, obj.currency, correct_rate.rate)
    threshold = min_material_diff(correct)
    if variant == "inverted":
        inv_rate = _fmt_rate(Decimal(1) / Decimal(correct_rate.rate))
        if abs(w.to_base(amount, obj.currency, inv_rate) - correct) >= threshold:
            obj.rate_override = inv_rate
            return variant
        return None
    dates = _candidate_dates(ctx, obj, variant)
    if prefer is not None:
        dates = [prefer] + dates
    good = []
    for d in dates:
        try:
            r = w.fx.lookup(obj.currency, d)
        except KeyError:
            continue
        if r.rate_id != correct_rate.rate_id and abs(w.to_base(amount, obj.currency, r.rate) - correct) >= threshold:
            good.append(d)
    if not good:
        return None
    obj.rate_date_override = good[0] if prefer is not None and good[0] == prefer else rng.choice(good)
    return variant


def apply(ctx: InjectionContext, obj, variant: str, scenario: Optional[str] = None,
          prefer: Optional[date] = None) -> Optional[IssueSpec]:
    kind = "invoice" if isinstance(obj, Invoice) else "payment"
    ctx.touch(kind, obj)
    applied = _try_override(ctx, obj, variant, prefer)
    if applied is None:
        for alt in ("wrong_date", "stale_rate", "inverted"):
            applied = _try_override(ctx, obj, alt)
            if applied:
                break
    if applied is None:
        return None
    bid = obj.invoice_id if kind == "invoice" else obj.payment_id
    ctx.lock(bid)

    def resolve(world, ledger):
        src = (kind, bid)
        rate = world.policy_rate(obj.currency, _doc_time(obj))
        correct = world.to_base(_amount(obj), obj.currency, rate.rate)
        if kind == "invoice":
            booked = ledger.row(src, "ar").debit_minor
            rows = [ledger.row(src, "ar").row_id, ledger.row(src, "rev").row_id]
        else:
            booked = ledger.row(src, "bank").debit_minor
            rows = [ledger.row(src, "bank").row_id]
        return abs(booked - correct), evidence_product([[obj.doc_id], rows, [rate.rate_id]])

    return IssueSpec("fx_error", [bid], resolve, [(kind, bid)], applied, scenario)


def eligible_invoice(ctx, i) -> bool:
    w = ctx.world
    return (i.period_class == "current" and i.booking_ts is not None and i.currency != w.base
            and ctx.is_free(i.invoice_id) and i.rate_override is None and i.rate_date_override is None)


def eligible_payment(ctx, p) -> bool:
    w = ctx.world
    return (p.kind == "receipt" and p.booking_ts is not None and p.currency != w.base
            and p.applied_override is None and ctx.is_free(p.payment_id) and p.rate_override is None
            and p.rate_date_override is None)


def inject(ctx: InjectionContext, variant: Optional[str] = None) -> list:
    w, rng = ctx.world, ctx.rng
    invs = sorted((i for i in w.invoices.values() if eligible_invoice(ctx, i)), key=lambda i: i.invoice_id)
    pays = sorted((p for p in w.payments.values() if eligible_payment(ctx, p)), key=lambda p: p.payment_id)
    pool = [("invoice", i) for i in invs] + [("payment", p) for p in pays]
    if not pool:
        return []
    _, obj = rng.choice(pool)
    variant = variant or rng.choice(["wrong_date", "wrong_date", "stale_rate", "inverted"])
    spec = apply(ctx, obj, variant)
    return [spec] if spec else []
