"""duplicate_invoice: the same invoice entered twice under a new doc_id/invoice_id.

Canonical form: affected_ids = both invoice_ids; amount = functional-currency
amount booked for the later-issued copy. Evidence: both documents (identical
entity, currency, total and line items incl. service period) and one booking
row (AR or revenue) for each copy.
"""

from __future__ import annotations

import copy
from datetime import timedelta
from typing import Optional

from ..world import Invoice
from .base import InjectionContext, IssueSpec, evidence_product


def inject(ctx: InjectionContext, variant: Optional[str] = None) -> list:
    w, rng = ctx.world, ctx.rng
    last_ok = w.period_end - timedelta(days=4)
    cands = [
        i
        for i in w.invoices.values()
        if i.period_class == "current"
        and i.booking_ts is not None
        and ctx.is_free(i.invoice_id)
        and w.local(i.issued_at) <= last_ok
        and i.rate_override is None
        and i.rate_date_override is None
    ]
    a = ctx.pick(cands, key=lambda i: i.invoice_id)
    if a is None:
        return []
    variant = variant or rng.choice(["re_entered", "re_entered_later"])
    delta = (
        timedelta(seconds=rng.randint(3600, 8 * 3600))
        if variant == "re_entered"
        else timedelta(days=rng.randint(1, 3), seconds=rng.randint(0, 6 * 3600))
    )
    issued = a.issued_at + delta
    b = Invoice(
        doc_id=ctx.ids.new("DOC"),
        invoice_id=ctx.ids.new("INV"),
        entity_id=a.entity_id,
        currency=a.currency,
        issued_at=issued,
        due_at=issued + (a.due_at - a.issued_at),
        render_tz=a.render_tz,
        line_items=copy.deepcopy(a.line_items),
        total_minor=a.total_minor,
        period_class="current",
        booking_ts=issued,
    )
    w.invoices[b.invoice_id] = b
    ctx.added.add(("invoice", b.invoice_id))
    ctx.lock(a.invoice_id, b.invoice_id)

    def resolve(world, ledger):
        ra, rb = ("invoice", a.invoice_id), ("invoice", b.invoice_id)
        amount = ledger.row(rb, "ar").debit_minor
        slots = [
            [a.doc_id],
            [b.doc_id],
            [ledger.row(ra, "ar").row_id, ledger.row(ra, "rev").row_id],
            [ledger.row(rb, "ar").row_id, ledger.row(rb, "rev").row_id],
        ]
        return amount, evidence_product(slots)

    return [
        IssueSpec(
            "duplicate_invoice", sorted([a.invoice_id, b.invoice_id]), resolve, [("invoice", b.invoice_id)], variant
        )
    ]
