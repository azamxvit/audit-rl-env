"""Interacting-error scenarios (two issues on the same documents).

``fx_partial_boundary``
    A foreign-currency *partial* receipt arrives late on the last local day of
    the period; the remittance's printed timestamp (payer offset) already shows
    the next day. The bookkeeper (a) used the rate of the printed date and
    (b) applied only part of the remitted reference, parking the rest in 2200.
    -> one ``fx_error`` on the payment + one ``payment_allocation``. The 2200
    amount is itself converted at the wrong rate, so the two must be analysed
    together (amount of allocation issue = what is actually in 2200).

``cutoff_fx``
    A next-period foreign invoice is booked in this period *and* at a wrong
    rate. -> one ``period_cutoff`` (amount = what was booked) + one
    ``fx_error`` (difference to the policy rate for its own issue date).
"""
from __future__ import annotations

from ..world import Payment
from . import fx_error, payment_allocation, period_cutoff
from .base import InjectionContext, printed_date


def _boundary_partial_hosts(ctx: InjectionContext) -> list:
    w = ctx.world
    out = []
    for p in w.payments.values():
        if not payment_allocation.eligible(ctx, p) or p.currency == w.base:
            continue
        inv = w.invoices[p.invoice_refs[0]["invoice_id"]]
        if (p.amount_minor < inv.total_minor and w.local(p.timestamp) == w.period_end
                and printed_date(p) != w.period_end and fx_error.eligible_payment(ctx, p)):
            out.append(p)
    return sorted(out, key=lambda p: p.payment_id)


def fx_partial_boundary(ctx: InjectionContext) -> list:
    hosts = _boundary_partial_hosts(ctx)
    if not hosts:
        return []
    pay: Payment = ctx.rng.choice(hosts)
    fx_spec = fx_error.apply(ctx, pay, "wrong_date", scenario="fx_partial_boundary", prefer=printed_date(pay))
    if fx_spec is None:
        return []
    # unlock for the second, deliberately overlapping issue
    ctx.locked.discard(pay.payment_id)
    alloc_spec = payment_allocation.apply(ctx, pay, "partial", scenario="fx_partial_boundary")
    return [fx_spec, alloc_spec]


def cutoff_fx(ctx: InjectionContext) -> list:
    w = ctx.world
    cands = [i for i in w.invoices.values()
             if period_cutoff.eligible(ctx, i, "next") and i.currency != w.base]
    inv = ctx.pick(cands, key=lambda i: i.invoice_id)
    if inv is None:
        return []
    cut_spec = period_cutoff.apply(ctx, inv, scenario="cutoff_fx")
    ctx.locked.discard(inv.invoice_id)
    fx_spec = fx_error.apply(ctx, inv, ctx.rng.choice(["wrong_date", "inverted"]), scenario="cutoff_fx")
    if fx_spec is None:  # cannot happen in practice (inverted always material); keep cut-off alone
        ctx.lock(inv.invoice_id)
        return [cut_spec]
    return [cut_spec, fx_spec]


SCENARIOS = {
    "fx_partial_boundary": fx_partial_boundary,
    "cutoff_fx": cutoff_fx,
}
