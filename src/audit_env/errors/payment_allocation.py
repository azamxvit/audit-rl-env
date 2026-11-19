"""payment_allocation: a remitted receipt is not (fully) applied to the invoice it references.

Hosts are receipts with exactly one invoice reference that covers the whole
receipt, so policy expects no unapplied cash at all. Variants:
- ``missing``: nothing applied, the whole receipt sits in 2200;
- ``partial``: only part of the reference is applied, the rest sits in 2200.
Canonical form: affected_ids = [payment_id, invoice_id]; amount = the 2200
credit booked by that receipt (functional currency). Evidence: the payment
document (shows the reference) and the 2200 row of that receipt.
"""
from __future__ import annotations

from typing import Optional

from ..world import Payment
from .base import InjectionContext, IssueSpec, evidence_product


def eligible(ctx: InjectionContext, p: Payment) -> bool:
    refs = p.invoice_refs or []
    return (p.kind == "receipt" and p.booking_ts is not None and len(refs) == 1
            and refs[0]["amount_minor"] == p.amount_minor and p.applied_override is None
            and ctx.is_free(p.payment_id, refs[0]["invoice_id"]))


def apply(ctx: InjectionContext, pay: Payment, variant: str, scenario: Optional[str] = None) -> IssueSpec:
    ref = pay.invoice_refs[0]
    inv_id = ref["invoice_id"]
    ctx.touch("payment", pay)
    if variant == "missing":
        pay.applied_override = {}
    else:
        applied = ref["amount_minor"] * ctx.rng.randint(20, 80) // 100
        pay.applied_override = {inv_id: max(1, min(applied, ref["amount_minor"] - 1))}
    ctx.lock(pay.payment_id, inv_id)

    def resolve(world, ledger):
        src = ("payment", pay.payment_id)
        row = ledger.row(src, "unapplied")
        return row.credit_minor, evidence_product([[pay.doc_id], [row.row_id]])

    return IssueSpec("payment_allocation", sorted([pay.payment_id, inv_id]), resolve,
                     [("payment", pay.payment_id)], variant, scenario)


def inject(ctx: InjectionContext, variant: Optional[str] = None) -> list:
    cands = [p for p in ctx.world.payments.values() if eligible(ctx, p)]
    pay = ctx.pick(cands, key=lambda p: p.payment_id)
    if pay is None:
        return []
    variant = variant or ctx.rng.choice(["missing", "partial"])
    return [apply(ctx, pay, variant)]
