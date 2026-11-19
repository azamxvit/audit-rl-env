"""Plausible *correct* look-alikes generated as part of the clean history.

They are produced by :mod:`audit_env.world` (they belong to the true history,
not to the injection stage) and are controlled by ``config["distractors"]``:

=========================== ===============================================================
key                         what it creates (all legitimate, never in truth.json)
=========================== ===============================================================
split_payments              invoice settled by 2-3 tranches, each remittance referencing it
multi_invoice_payments      one transfer settling two invoices of the same customer
overpayments                receipt above the referenced amount -> excess in 2200 (correct),
                            usually followed by a ``kind=refund`` (Dr 2200 / Cr 1000)
unidentified_receipts       receipt with ``invoice_refs = null`` -> whole amount in 2200
subscriptions               monthly invoices with identical amount/description but a
                            different service period (not duplicates)
booking_delay               booking timestamp 1-2 days after issuance (same period; the FX
                            rate is still the one of the document date)
boundary_documents          in-period invoices whose printed date (customer offset) is in the
                            previous/next period
boundary_partial_payments   foreign partial receipt late on the last day, printed next day
(always)                    weekend document dates -> FX fallback to the last business day;
                            next-period invoices present but unbooked; prior-period invoices
                            paid in the period without a booking in this ledger
=========================== ===============================================================
"""
from __future__ import annotations

from ..world import World


def summarize(world: World) -> dict:
    """Counts of distractor patterns present in a world (recorded in provenance)."""
    pays = list(world.payments.values())
    refs_count: dict = {}
    for p in pays:
        for r in p.invoice_refs or []:
            refs_count[r["invoice_id"]] = refs_count.get(r["invoice_id"], 0) + 1
    return {
        "split_payment_invoices": sum(1 for v in refs_count.values() if v > 1),
        "multi_invoice_payments": sum(1 for p in pays if p.invoice_refs and len(p.invoice_refs) > 1),
        "overpayments": sum(1 for p in pays if p.invoice_refs and p.kind == "receipt"
                            and p.amount_minor > sum(r["amount_minor"] for r in p.invoice_refs)),
        "refunds": sum(1 for p in pays if p.kind == "refund"),
        "unidentified_receipts": sum(1 for p in pays if p.kind == "receipt" and p.invoice_refs is None),
        "subscription_customers": sum(1 for c in world.customers if c.plan),
        "next_period_documents": sum(1 for i in world.invoices.values() if i.period_class == "next"),
        "prior_period_documents": sum(1 for i in world.invoices.values() if i.period_class == "prior"),
    }
