"""Shared machinery for error injection.

An injector never edits ledger rows directly. It changes the *booking
parameters* of a document (booking timestamp, rate used, amounts applied) or adds
a document that the bookkeeper booked, then the ledger is rebuilt. Each injector
returns ``IssueSpec`` objects whose ``resolve`` computes the ground-truth amount
and the admissible evidence sets from the rebuilt ledger.
"""
from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from ..util import IdFactory
from ..world import Invoice, Ledger, Payment, World

ISSUE_TYPES = ("duplicate_invoice", "payment_allocation", "fx_error", "period_cutoff")


@dataclass
class IssueSpec:
    type: str
    affected_ids: list
    resolve: Callable  # (world, ledger) -> (amount_minor, evidence_sets)
    targets: list  # [("invoice"|"payment", business_id)]
    variant: str = ""
    scenario: Optional[str] = None


@dataclass
class InjectionContext:
    world: World
    rng: object
    ids: IdFactory
    locked: set = field(default_factory=set)
    snapshots: dict = field(default_factory=dict)
    added: set = field(default_factory=set)

    def lock(self, *keys: str) -> None:
        self.locked.update(keys)

    def is_free(self, *keys: str) -> bool:
        return not any(k in self.locked for k in keys)

    def touch(self, kind: str, obj) -> None:
        """Remember booking parameters before the first change (for provenance)."""
        key = (kind, obj.invoice_id if kind == "invoice" else obj.payment_id)
        if key not in self.snapshots and key not in self.added:
            self.snapshots[key] = booking_params(obj)

    def pick(self, items: list, key: Callable):
        items = sorted(items, key=key)
        return self.rng.choice(items) if items else None


def booking_params(obj) -> dict:
    out = {
        "booking_ts": obj.booking_ts.isoformat() if obj.booking_ts else None,
        "rate_override": obj.rate_override,
        "rate_date_override": obj.rate_date_override.isoformat() if obj.rate_date_override else None,
    }
    if isinstance(obj, Payment):
        out["applied_override"] = copy.deepcopy(obj.applied_override)
    return out


def evidence_product(slots: list) -> list:
    """Each slot is a list of interchangeable record IDs; every combination is admissible."""
    combos = {tuple(sorted(set(c))) for c in itertools.product(*slots)}
    return [list(c) for c in sorted(combos)]


def min_material_diff(correct_minor: int) -> int:
    """Injected FX misstatements are at least 0.2% and at least 5 minor units (well above tolerance)."""
    return max(5, abs(correct_minor) // 500)


def random_time_on(world: World, rng, day: date, lo_h: int = 9, hi_h: int = 18) -> datetime:
    from datetime import time

    base = datetime.combine(day, time(0, 0), tzinfo=world.tz)
    return base + timedelta(seconds=rng.randint(lo_h * 3600, hi_h * 3600))


def printed_date(obj) -> date:
    from ..util import tz_from_minutes

    ts = obj.issued_at if isinstance(obj, Invoice) else obj.timestamp
    return ts.astimezone(tz_from_minutes(obj.render_tz)).date()


def ledger_row_id(ledger: Ledger, source: tuple, slot: str) -> str:
    return ledger.row(source, slot).row_id
