"""period_cutoff: revenue of another period booked in this period's ledger.

Variants:
- ``next_period``: an invoice issued after period end (local date) is booked in
  the last days of the period (incl. the boundary trap where the printed date
  in the customer's offset still shows the last day of the period);
- ``prior_period``: an invoice issued (and recognised) before period start is
  booked again in the first days of the period.
Canonical form: affected_ids = [invoice_id]; amount = functional amount booked.
Evidence: the invoice document and its booking row (AR or revenue).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from ..world import Invoice
from .base import InjectionContext, IssueSpec, evidence_product, random_time_on


def eligible(ctx: InjectionContext, i: Invoice, period_class: str) -> bool:
    return i.period_class == period_class and i.booking_ts is None and ctx.is_free(i.invoice_id)


def apply(ctx: InjectionContext, inv: Invoice, scenario: Optional[str] = None) -> IssueSpec:
    w, rng = ctx.world, ctx.rng
    ctx.touch("invoice", inv)
    if inv.period_class == "next":
        day = w.period_end - timedelta(days=rng.randint(0, 2))
        variant = "next_period"
    else:
        day = w.period_start + timedelta(days=rng.randint(0, 2))
        variant = "prior_period"
    inv.booking_ts = random_time_on(w, rng, day)
    ctx.lock(inv.invoice_id)

    def resolve(world, ledger):
        src = ("invoice", inv.invoice_id)
        rows = [ledger.row(src, "ar").row_id, ledger.row(src, "rev").row_id]
        return ledger.row(src, "ar").debit_minor, evidence_product([[inv.doc_id], rows])

    return IssueSpec("period_cutoff", [inv.invoice_id], resolve, [("invoice", inv.invoice_id)], variant, scenario)


def inject(ctx: InjectionContext, variant: Optional[str] = None) -> list:
    w, rng = ctx.world, ctx.rng
    variant = variant or rng.choice(["next_period", "next_period", "prior_period"])
    order = ["next", "prior"] if variant == "next_period" else ["prior", "next"]
    for cls in order:
        inv = ctx.pick([i for i in w.invoices.values() if eligible(ctx, i, cls)], key=lambda i: i.invoice_id)
        if inv is not None:
            return [apply(ctx, inv)]
    return []
