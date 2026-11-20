"""Hidden "true" history of a fictional company and the bookkeeping rules.

The world is generated first and is internally consistent (balanced entries,
payments allocated exactly as remitted, FX per policy, revenue in the right
period). Errors are injected later (see ``errors/``) by changing *booking
parameters* of specific documents; the ledger is then rebuilt from those
parameters, so every injected error is a causal change with a before/after.
"""

from __future__ import annotations

import bisect
import calendar
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional

from .money import CURRENCY_EXPONENTS, DEFAULT_ROUNDING, convert
from .util import IdFactory, derive_rng, hashed_token, iso, local_date, tz_from_minutes, tz_label

ACCOUNTS = {
    "1000": "Bank (functional currency)",
    "1100": "Accounts receivable",
    "2200": "Unapplied customer cash",
    "4000": "Revenue",
    "6100": "Rent expense",
    "6200": "Payroll expense",
    "6300": "Utilities expense",
    "6400": "Software subscriptions",
    "6500": "Bank fees",
    "6600": "Office supplies",
    "7900": "FX gain/loss",
}

# Approximate USD value of one major unit; only used to make amounts/rates plausible.
USD_VALUE = {
    "USD": Decimal("1"),
    "EUR": Decimal("1.08"),
    "GBP": Decimal("1.27"),
    "CHF": Decimal("1.12"),
    "JPY": Decimal("0.0067"),
    "KZT": Decimal("0.0021"),
}

COMPANY_TZ_CHOICES = [-300, -180, 0, 60, 180, 300, 360, 540]
CUSTOMER_TZ_CHOICES = [-480, -300, -180, 0, 60, 120, 180, 300, 330, 360, 480, 540, 600]

SYLLABLES = [
    "vel",
    "tra",
    "nor",
    "qui",
    "lum",
    "dax",
    "ori",
    "sen",
    "kal",
    "mir",
    "zen",
    "pol",
    "tek",
    "var",
    "ost",
    "bri",
    "neo",
    "cor",
    "fen",
    "ula",
    "rax",
    "ion",
    "ter",
    "sol",
]
SUFFIXES = [
    "Systems",
    "Trading",
    "Logistics",
    "Analytics",
    "Foods",
    "Labs",
    "Works",
    "Partners",
    "Retail",
    "Energy",
    "Media",
    "Holdings",
    "Studio",
    "Supply",
]
LEGAL = ["LLP", "LLC", "Ltd", "GmbH", "SA", "JSC"]

CATALOG = [
    "Consulting services",
    "Software license",
    "Support plan",
    "Implementation work",
    "Training session",
    "Equipment rental",
    "Data migration",
    "Maintenance visit",
    "Cloud hosting",
    "Audit preparation",
    "Design services",
    "Logistics handling",
]


# --------------------------------------------------------------------------- entities


@dataclass
class Customer:
    entity_id: str
    name: str
    currency: str
    tz_minutes: int
    plan: Optional[dict] = None  # recurring subscription line item, if any


@dataclass
class Invoice:
    doc_id: str
    invoice_id: str
    entity_id: str
    currency: str
    issued_at: datetime
    due_at: datetime
    render_tz: int
    line_items: list
    total_minor: int
    period_class: str  # prior | current | next
    booking_ts: Optional[datetime] = None  # None => not booked in this period's ledger
    rate_override: Optional[str] = None
    rate_date_override: Optional[date] = None


@dataclass
class Payment:
    doc_id: str
    payment_id: str
    entity_id: Optional[str]
    kind: str  # receipt | refund
    timestamp: datetime
    render_tz: int
    currency: str
    amount_minor: int
    invoice_refs: Optional[list]  # [{"invoice_id", "amount_minor"}] or None
    booking_ts: Optional[datetime] = None
    rate_override: Optional[str] = None
    rate_date_override: Optional[date] = None
    applied_override: Optional[dict] = None  # invoice_id -> amount actually applied


@dataclass
class Expense:
    key: str
    ts: datetime
    account: str
    amount_minor: int
    entity_id: str


@dataclass
class FxRate:
    rate_id: str
    day: date
    source: str
    target: str
    rate: str


class FxTable:
    """Published rates source->target (1 source = rate target), business days only."""

    def __init__(self, rates: list):
        self.rates = rates
        self._by_ccy: dict[str, list] = {}
        for r in sorted(rates, key=lambda r: (r.source, r.day)):
            self._by_ccy.setdefault(r.source, []).append(r)
        self._days = {c: [r.day for r in lst] for c, lst in self._by_ccy.items()}

    def lookup(self, source: str, day: date) -> FxRate:
        """Latest published rate on or before ``day`` (policy fallback rule)."""
        days = self._days[source]
        i = bisect.bisect_right(days, day) - 1
        if i < 0:
            raise KeyError("no rate on or before date")
        return self._by_ccy[source][i]

    def all_for(self, source: str) -> list:
        return list(self._by_ccy.get(source, []))


@dataclass
class Row:
    row_id: str
    entry_id: str
    timestamp: datetime
    account: str
    debit_minor: int
    credit_minor: int
    currency: str
    entity_id: Optional[str]
    invoice_id: Optional[str]
    payment_id: Optional[str]
    slot: str


@dataclass
class Entry:
    entry_id: str
    source: tuple  # ("invoice", id) | ("payment", id) | ("expense", key)
    timestamp: datetime
    rows: list


@dataclass
class Ledger:
    entries: list
    by_source: dict

    def row(self, source: tuple, slot: str) -> Row:
        for r in self.by_source[source].rows:
            if r.slot == slot:
                return r
        raise KeyError(slot)

    def rows(self) -> list:
        return [r for e in self.entries for r in e.rows]


@dataclass
class World:
    company_name: str
    base: str
    tz_minutes: int
    period_start: date
    period_end: date
    fx: FxTable
    customers: list
    vendors: dict
    invoices: dict = field(default_factory=dict)
    payments: dict = field(default_factory=dict)
    expenses: list = field(default_factory=list)
    id_salt: str = ""
    episode_id: str = ""
    used_ids: set = field(default_factory=set)
    rounding: str = DEFAULT_ROUNDING

    @property
    def tz(self) -> timezone:
        return tz_from_minutes(self.tz_minutes)

    def local(self, dt: datetime) -> date:
        return local_date(dt, self.tz)

    def in_period(self, dt: datetime) -> bool:
        return self.period_start <= self.local(dt) <= self.period_end

    # -- FX ---------------------------------------------------------------
    def policy_rate(self, currency: str, dt: datetime) -> Optional[FxRate]:
        if currency == self.base:
            return None
        return self.fx.lookup(currency, self.local(dt))

    def used_rate(self, currency: str, dt: datetime, rate_override, rate_date_override) -> str:
        if currency == self.base:
            return "1"
        if rate_override is not None:
            return rate_override
        if rate_date_override is not None:
            return self.fx.lookup(currency, rate_date_override).rate
        return self.policy_rate(currency, dt).rate

    def to_base(self, amount_minor: int, currency: str, rate: str) -> int:
        return convert(amount_minor, currency, self.base, rate, self.rounding)

    def invoice_rate(self, inv: Invoice) -> str:
        return self.used_rate(inv.currency, inv.issued_at, inv.rate_override, inv.rate_date_override)

    def payment_rate(self, pay: Payment) -> str:
        return self.used_rate(pay.currency, pay.timestamp, pay.rate_override, pay.rate_date_override)

    def invoice_base_correct(self, inv: Invoice) -> int:
        rate = "1" if inv.currency == self.base else self.policy_rate(inv.currency, inv.issued_at).rate
        return self.to_base(inv.total_minor, inv.currency, rate)


# --------------------------------------------------------------------------- ledger build


def _row_id(world: World, kind: str, key: str, slot: str) -> str:
    return "LR-" + hashed_token(world.id_salt, "row", kind, key, slot)


def build_ledger(world: World) -> Ledger:
    """Book every document according to its (possibly overridden) booking parameters."""
    entries: list = []
    booked_ar: dict = {}
    base = world.base

    def make_entry(kind: str, key: str, ts: datetime, specs: list) -> Entry:
        entry_id = "JE-" + hashed_token(world.id_salt, "entry", kind, key)
        rows = []
        for slot, account, debit, credit, entity, inv_id, pay_id in specs:
            rows.append(
                Row(
                    _row_id(world, kind, key, slot),
                    entry_id,
                    ts,
                    account,
                    debit,
                    credit,
                    base,
                    entity,
                    inv_id,
                    pay_id,
                    slot,
                )
            )
        e = Entry(entry_id, (kind, key), ts, rows)
        entries.append(e)
        return e

    for inv in sorted(world.invoices.values(), key=lambda i: (i.issued_at, i.invoice_id)):
        if inv.booking_ts is None:
            continue
        amount = world.to_base(inv.total_minor, inv.currency, world.invoice_rate(inv))
        booked_ar[inv.invoice_id] = amount
        make_entry(
            "invoice",
            inv.invoice_id,
            inv.booking_ts,
            [
                ("ar", "1100", amount, 0, inv.entity_id, inv.invoice_id, None),
                ("rev", "4000", 0, amount, inv.entity_id, inv.invoice_id, None),
            ],
        )

    for pay in sorted(world.payments.values(), key=lambda p: (p.timestamp, p.payment_id)):
        if pay.booking_ts is None:
            continue
        rate = world.payment_rate(pay)
        bank = world.to_base(pay.amount_minor, pay.currency, rate)
        if pay.kind == "refund":
            make_entry(
                "payment",
                pay.payment_id,
                pay.booking_ts,
                [
                    ("unapplied", "2200", bank, 0, pay.entity_id, None, pay.payment_id),
                    ("bank", "1000", 0, bank, pay.entity_id, None, pay.payment_id),
                ],
            )
            continue
        specs = [("bank", "1000", bank, 0, pay.entity_id, None, pay.payment_id)]
        if pay.applied_override is not None:
            applied = [(k, v) for k, v in pay.applied_override.items()]
        else:
            applied = [(r["invoice_id"], r["amount_minor"]) for r in (pay.invoice_refs or [])]
        credits = 0
        for inv_id, amt in applied:
            if amt <= 0:
                continue
            inv = world.invoices[inv_id]
            if inv.currency == base:
                carrying = amt
            elif amt == inv.total_minor:
                carrying = booked_ar.get(inv_id, world.to_base(inv.total_minor, inv.currency, world.invoice_rate(inv)))
            else:
                carrying = world.to_base(amt, inv.currency, world.invoice_rate(inv))
            specs.append((f"ar:{inv_id}", "1100", 0, carrying, pay.entity_id, inv_id, pay.payment_id))
            credits += carrying
        unapplied = pay.amount_minor - sum(a for _, a in applied)
        if unapplied > 0:
            u = world.to_base(unapplied, pay.currency, rate)
            specs.append(("unapplied", "2200", 0, u, pay.entity_id, None, pay.payment_id))
            credits += u
        diff = bank - credits
        if diff > 0:
            specs.append(("fx", "7900", 0, diff, pay.entity_id, None, pay.payment_id))
        elif diff < 0:
            specs.append(("fx", "7900", -diff, 0, pay.entity_id, None, pay.payment_id))
        make_entry("payment", pay.payment_id, pay.booking_ts, specs)

    for exp in world.expenses:
        make_entry(
            "expense",
            exp.key,
            exp.ts,
            [
                ("exp", exp.account, exp.amount_minor, 0, exp.entity_id, None, None),
                ("bank", "1000", 0, exp.amount_minor, exp.entity_id, None, None),
            ],
        )

    seen: set = set()
    for e in entries:
        for r in e.rows:
            if r.row_id in seen:  # pragma: no cover - 40-bit hash collision
                raise RuntimeError("row id collision")
            seen.add(r.row_id)
    entries.sort(key=lambda e: (e.timestamp.astimezone(timezone.utc), e.entry_id))
    return Ledger(entries, {e.source: e for e in entries})


# --------------------------------------------------------------------------- generation


def _name(rng, words: int = 2) -> str:
    stem = "".join(rng.choice(SYLLABLES) for _ in range(words)).capitalize()
    return f"{stem} {rng.choice(SUFFIXES)} {rng.choice(LEGAL)}"


def _fmt_rate(value: Decimal) -> str:
    q = value.quantize(Decimal(1).scaleb(value.adjusted() - 5))
    return format(q, "f")


def _price_minor(rng, currency: str, usd_lo: int, usd_hi: int) -> int:
    usd = Decimal(rng.randint(usd_lo, usd_hi))
    major = usd / USD_VALUE[currency]
    exp = CURRENCY_EXPONENTS[currency]
    if exp == 0 or currency == "KZT":
        major = (major / 10).quantize(Decimal(1)) * 10  # round amounts in "small" currencies
        return int(major) * 10**exp
    return int((major * 10**exp).quantize(Decimal(1)))


def _month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _rand_range(rng, pair) -> int:
    lo, hi = pair
    return rng.randint(int(lo), int(hi))


LEDGER_ROWS_MAX = 2000
INJECTION_HEADROOM = 30


def _content_key(items: list) -> str:
    """Line-item content (the part a duplicate copies), independent of IDs and dates of issue."""
    return json.dumps(sorted(json.dumps(li, sort_keys=True) for li in items))


class WorldBuilder:
    """Builds a consistent company history from (seed, config)."""

    def __init__(self, seed: object, cfg: dict):
        self.cfg = cfg
        self.rng = derive_rng(seed, "world")
        self.ids = IdFactory(derive_rng(seed, "world-ids"))
        self.salt = hashed_token(str(seed), "salt", cfg.get("config_id", ""), n=16)

    # -- helpers --------------------------------------------------------
    def _local_dt(self, day: date, seconds: int) -> datetime:
        return datetime.combine(day, time(0, 0), tzinfo=self.w.tz) + timedelta(seconds=seconds)

    def _business_dt(self, day: date) -> datetime:
        rng = self.rng
        secs = rng.randint(8 * 3600, 19 * 3600) if rng.random() < 0.9 else rng.randint(0, 86399)
        return self._local_dt(day, secs)

    def _day_in(self, start: date, end: date) -> date:
        return start + timedelta(days=self.rng.randint(0, (end - start).days))

    def _line_items(self, currency: str, issued: date) -> list:
        rng = self.rng
        items = []
        svc_start, svc_end = issued.replace(day=1), _month_end(issued)
        for desc in rng.sample(CATALOG, rng.randint(1, 4)):
            qty = rng.randint(1, 12)
            unit = _price_minor(rng, currency, 40, 2500)
            items.append(
                {
                    "description": desc,
                    "quantity": qty,
                    "unit_price_minor": unit,
                    "amount_minor": qty * unit,
                    "service_period_start": svc_start.isoformat(),
                    "service_period_end": svc_end.isoformat(),
                }
            )
        return items

    def _distinct_content(self, cust: Customer, items: list) -> list:
        """A legitimate invoice never repeats another invoice of the same customer line for line.

        Random line items can coincide (same catalogue item, quantity, price and service
        month); that would be indistinguishable from an injected ``duplicate_invoice``.
        On a collision the first line's quantity is raised by one until the content is
        unique. No randomness is consumed, so episodes without a collision are unchanged.
        """
        seen = {
            _content_key(i.line_items)
            for i in self.w.invoices.values()
            if i.entity_id == cust.entity_id and i.currency == cust.currency
        }
        items = [dict(li) for li in items]
        while _content_key(items) in seen:
            first = items[0]
            first["quantity"] += 1
            first["amount_minor"] = first["quantity"] * first["unit_price_minor"]
        return items

    def _new_invoice(
        self, cust: Customer, issued: datetime, items: list, period_class: str, render_tz: Optional[int] = None
    ) -> Invoice:
        w = self.w
        items = self._distinct_content(cust, items)
        due = issued + timedelta(days=self.rng.choice([14, 30, 30, 45]))
        inv = Invoice(
            doc_id=self.ids.new("DOC"),
            invoice_id=self.ids.new("INV"),
            entity_id=cust.entity_id,
            currency=cust.currency,
            issued_at=issued,
            due_at=due,
            render_tz=cust.tz_minutes if render_tz is None else render_tz,
            line_items=items,
            total_minor=sum(i["amount_minor"] for i in items),
            period_class=period_class,
        )
        if period_class == "current":
            inv.booking_ts = issued
            if self.rng.random() < self.cfg["distractors"].get("booking_delay", 0.0):
                cand = issued + timedelta(days=self.rng.randint(1, 2), hours=self.rng.randint(0, 5))
                if w.in_period(cand):
                    inv.booking_ts = cand
        w.invoices[inv.invoice_id] = inv
        return inv

    def _new_payment(
        self, entity_id, ts: datetime, currency: str, amount: int, refs, kind="receipt", render_tz: Optional[int] = None
    ) -> Payment:
        w = self.w
        cust_tz = next((c.tz_minutes for c in w.customers if c.entity_id == entity_id), w.tz_minutes)
        pay = Payment(
            doc_id=self.ids.new("DOC"),
            payment_id=self.ids.new("PAY"),
            entity_id=entity_id,
            kind=kind,
            timestamp=ts,
            render_tz=cust_tz if render_tz is None else render_tz,
            currency=currency,
            amount_minor=amount,
            invoice_refs=refs,
        )
        pay.booking_ts = ts
        if self.rng.random() < self.cfg["distractors"].get("booking_delay", 0.0):
            cand = ts + timedelta(days=1)
            if w.in_period(cand):
                pay.booking_ts = cand
        w.payments[pay.payment_id] = pay
        return pay

    # -- main -----------------------------------------------------------
    def build(self) -> World:
        cfg, rng = self.cfg, self.rng
        base = rng.choice(cfg["base_currencies"])
        tz_minutes = rng.choice(COMPANY_TZ_CHOICES)
        year = rng.choice([2025, 2026])
        if cfg.get("period", "quarter") == "quarter":
            q = rng.randint(0, 3)
            start = date(year, 3 * q + 1, 1)
            end = _month_end(_add_months(start, 2))
        else:
            start = date(year, rng.randint(1, 12), 1)
            end = _month_end(start)
        foreign_pool = sorted(c for c in cfg["foreign_currencies"] if c != base)
        n_foreign = min(len(foreign_pool), rng.randint(1, 3))
        foreign = rng.sample(foreign_pool, n_foreign)
        fx = self._build_fx(base, foreign, start - timedelta(days=60), end + timedelta(days=12))
        vendors = {k: self.ids.new("VEN") for k in ["rent", "payroll", "utilities", "software", "bank", "supplies"]}
        self.w = World(_name(rng, 2), base, tz_minutes, start, end, fx, [], vendors, id_salt=self.salt)
        self.w.episode_id = self.ids.new("EP")
        self.w.used_ids = self.ids.used
        self._customers(foreign)
        self._invoices()
        self._payments()
        self._expenses()
        return self.w

    def _build_fx(self, base: str, foreign: list, d0: date, d1: date) -> FxTable:
        rng = self.rng
        rates = []
        for ccy in foreign:
            value = USD_VALUE[ccy] / USD_VALUE[base] * (1 + Decimal(rng.randint(-500, 500)) / 10000)
            d = d0
            while d <= d1:
                value = value * (1 + Decimal(rng.randint(-70, 70)) / 10000)
                if d.weekday() < 5:
                    rates.append(FxRate(self.ids.new("FXR"), d, ccy, base, _fmt_rate(value)))
                d += timedelta(days=1)
        return FxTable(rates)

    def _customers(self, foreign: list) -> None:
        cfg, rng, w = self.cfg, self.rng, self.w
        n = _rand_range(rng, cfg["n_customers"])
        share = cfg.get("foreign_customer_share", 0.3)
        for i in range(n):
            wants_foreign = rng.random() < share or i == 0
            # a pool with no currency other than the base means a single-currency company
            ccy = rng.choice(foreign) if (wants_foreign and foreign) else w.base
            cust = Customer(self.ids.new("CUS"), _name(rng, 2), ccy, rng.choice(CUSTOMER_TZ_CHOICES))
            if rng.random() < cfg["distractors"].get("subscriptions", 0.0):
                cust.plan = {
                    "description": f"Subscription plan {rng.choice(['Basic', 'Team', 'Pro', 'Scale'])}",
                    "quantity": 1,
                    "unit_price_minor": _price_minor(rng, ccy, 100, 1500),
                }
            w.customers.append(cust)

    def _invoices(self) -> None:
        cfg, rng, w = self.cfg, self.rng, self.w
        start, end = w.period_start, w.period_end
        # recurring subscriptions: legitimately identical amounts, different service periods
        for cust in w.customers:
            if not cust.plan:
                continue
            day_of_month = rng.randint(1, 5)
            secs = rng.randint(9 * 3600, 11 * 3600)
            m = start
            while m <= end:
                issued = self._local_dt(m.replace(day=day_of_month), secs)
                item = dict(cust.plan)
                item["amount_minor"] = item["unit_price_minor"]
                item["service_period_start"] = m.isoformat()
                item["service_period_end"] = _month_end(m).isoformat()
                self._new_invoice(cust, issued, [item], "current")
                m = _add_months(m, 1)
        n_current = _rand_range(rng, cfg["n_invoices"])
        for _ in range(n_current):
            cust = rng.choice(w.customers)
            issued = self._business_dt(self._day_in(start, end))
            self._new_invoice(cust, issued, self._line_items(cust.currency, w.local(issued)), "current")
        # boundary distractors: in-period documents whose printed (customer-offset) date falls outside
        for _ in range(_rand_range(rng, cfg["distractors"].get("boundary_documents", [0, 0]))):
            cust = rng.choice(w.customers)
            if rng.random() < 0.5:
                issued = self._local_dt(end, rng.randint(22 * 3600, 23 * 3600 + 3000))
                render = min(840, w.tz_minutes + rng.randint(3, 6) * 60)
            else:
                issued = self._local_dt(start, rng.randint(60, 2 * 3600))
                render = max(-720, w.tz_minutes - rng.randint(3, 6) * 60)
            self._new_invoice(cust, issued, self._line_items(cust.currency, w.local(issued)), "current", render)
        # prior-period invoices (booked last period, paid in this one)
        for _ in range(_rand_range(rng, cfg["n_prior_period_invoices"])):
            cust = rng.choice(w.customers)
            issued = self._business_dt(self._day_in(start - timedelta(days=40), start - timedelta(days=1)))
            self._new_invoice(cust, issued, self._line_items(cust.currency, w.local(issued)), "prior")
        # next-period invoices (documents available, not booked in this period)
        foreign_custs = [c for c in w.customers if c.currency != w.base]
        n_next = _rand_range(rng, cfg["n_next_period_invoices"])
        for k in range(n_next):
            cust = foreign_custs[k % len(foreign_custs)] if (k == 0 and foreign_custs) else rng.choice(w.customers)
            if k == 1:  # boundary trap: printed date in period, local date already next period
                issued = self._local_dt(end + timedelta(days=1), rng.randint(0, 2 * 3600))
                render = max(-720, w.tz_minutes - rng.randint(4, 7) * 60)
            else:
                issued = self._business_dt(self._day_in(end + timedelta(days=1), end + timedelta(days=7)))
                render = None
            self._new_invoice(cust, issued, self._line_items(cust.currency, w.local(issued)), "next", render)

    def _payments(self) -> None:
        cfg, rng, w = self.cfg, self.rng, self.w
        d = cfg["distractors"]
        start, end = w.period_start, w.period_end
        pending_full: dict = {}
        invoices = sorted(w.invoices.values(), key=lambda i: (i.issued_at, i.invoice_id))
        for inv in invoices:
            if inv.period_class == "next":
                continue
            cust = next(c for c in w.customers if c.entity_id == inv.entity_id)
            if inv.period_class == "prior":
                day = self._day_in(start, start + timedelta(days=25))
                self._new_payment(
                    cust.entity_id,
                    self._business_dt(day),
                    inv.currency,
                    inv.total_minor,
                    [{"invoice_id": inv.invoice_id, "amount_minor": inv.total_minor}],
                )
                continue
            r = rng.random()
            pay_day = w.local(inv.issued_at) + timedelta(days=rng.randint(3, 45))
            if pay_day > end:
                continue
            if inv.currency != w.base:
                if r < 0.65:
                    self._new_payment(
                        cust.entity_id,
                        self._business_dt(pay_day),
                        inv.currency,
                        inv.total_minor,
                        [{"invoice_id": inv.invoice_id, "amount_minor": inv.total_minor}],
                    )
                elif r < 0.8:
                    part = inv.total_minor * rng.randint(30, 70) // 100
                    self._new_payment(
                        cust.entity_id,
                        self._business_dt(pay_day),
                        inv.currency,
                        part,
                        [{"invoice_id": inv.invoice_id, "amount_minor": part}],
                    )
                continue
            if r < d.get("split_payments", 0.0):
                n_tr = rng.randint(2, 3)
                remaining = inv.total_minor
                day = pay_day
                for t in range(n_tr):
                    amt = remaining if t == n_tr - 1 else remaining * rng.randint(25, 60) // 100
                    if day > end or amt <= 0:
                        break
                    self._new_payment(
                        cust.entity_id,
                        self._business_dt(day),
                        inv.currency,
                        amt,
                        [{"invoice_id": inv.invoice_id, "amount_minor": amt}],
                    )
                    remaining -= amt
                    day = day + timedelta(days=rng.randint(2, 15))
            elif r < 0.8:
                pending_full.setdefault(cust.entity_id, []).append((pay_day, inv))
        # full single payments; some customers pay several invoices with one transfer
        for entity_id in sorted(pending_full):
            items = pending_full[entity_id]
            i = 0
            while i < len(items):
                day, inv = items[i]
                if i + 1 < len(items) and rng.random() < d.get("multi_invoice_payments", 0.0):
                    day2, inv2 = items[i + 1]
                    refs = [
                        {"invoice_id": inv.invoice_id, "amount_minor": inv.total_minor},
                        {"invoice_id": inv2.invoice_id, "amount_minor": inv2.total_minor},
                    ]
                    self._new_payment(
                        entity_id,
                        self._business_dt(max(day, day2)),
                        inv.currency,
                        inv.total_minor + inv2.total_minor,
                        refs,
                    )
                    i += 2
                    continue
                self._new_payment(
                    entity_id,
                    self._business_dt(day),
                    inv.currency,
                    inv.total_minor,
                    [{"invoice_id": inv.invoice_id, "amount_minor": inv.total_minor}],
                )
                i += 1
        # overpayments (excess held as unapplied cash) and their refunds
        singles = sorted(
            (
                p
                for p in w.payments.values()
                if p.currency == w.base
                and p.invoice_refs
                and len(p.invoice_refs) == 1
                and p.amount_minor == p.invoice_refs[0]["amount_minor"]
            ),
            key=lambda p: p.payment_id,
        )
        for pay in rng.sample(singles, min(len(singles), _rand_range(rng, d.get("overpayments", [0, 0])))):
            extra = max(100, pay.amount_minor * rng.randint(2, 12) // 100)
            pay.amount_minor += extra
            refund_day = w.local(pay.timestamp) + timedelta(days=rng.randint(3, 12))
            if refund_day <= end:
                self._new_payment(pay.entity_id, self._business_dt(refund_day), pay.currency, extra, None, "refund")
        # receipts without remittance information (legitimately unapplied)
        base_custs = [c for c in w.customers if c.currency == w.base] or w.customers[:1]
        for _ in range(_rand_range(rng, d.get("unidentified_receipts", [0, 0]))):
            cust = rng.choice(base_custs)
            self._new_payment(
                cust.entity_id,
                self._business_dt(self._day_in(start, end)),
                cust.currency,
                _price_minor(rng, cust.currency, 100, 3000),
                None,
            )
        # foreign partial payments received late on the last day of the period, remitted from a
        # timezone where the printed date is already the next day (legit; host for interacting errors)
        for _ in range(_rand_range(rng, d.get("boundary_partial_payments", [0, 0]))):
            self._boundary_partial_payment()

    def _boundary_partial_payment(self) -> Optional[Payment]:
        rng, w = self.rng, self.w
        paid = {r["invoice_id"] for p in w.payments.values() for r in (p.invoice_refs or [])}
        cands = sorted(
            (
                i
                for i in w.invoices.values()
                if i.period_class == "current"
                and i.currency != w.base
                and i.invoice_id not in paid
                and w.local(i.issued_at) < w.period_end - timedelta(days=3)
            ),
            key=lambda i: i.invoice_id,
        )
        if not cands:
            return None
        inv = rng.choice(cands)
        ts = self._local_dt(w.period_end, rng.randint(22 * 3600 + 600, 23 * 3600 + 3000))
        render = min(840, w.tz_minutes + rng.randint(3, 5) * 60)
        part = inv.total_minor * rng.randint(30, 70) // 100
        pay = self._new_payment(
            inv.entity_id,
            ts,
            inv.currency,
            part,
            [{"invoice_id": inv.invoice_id, "amount_minor": part}],
            render_tz=render,
        )
        pay.booking_ts = ts
        return pay

    def _expenses(self) -> None:
        cfg, rng, w = self.cfg, self.rng, self.w
        start, end = w.period_start, w.period_end
        rent = _price_minor(rng, w.base, 2000, 9000)
        software = _price_minor(rng, w.base, 200, 1500)
        payroll = _price_minor(rng, w.base, 15000, 60000)
        m = start
        while m <= end:
            self._expense("rent", self._local_dt(m, 10 * 3600), "6100", rent)
            self._expense("software", self._local_dt(m.replace(day=3), 9 * 3600), "6400", software)
            self._expense("payroll", self._local_dt(m.replace(day=15), 12 * 3600), "6200", payroll)
            self._expense("payroll", self._local_dt(_month_end(m), 12 * 3600), "6200", payroll)
            self._expense(
                "utilities",
                self._business_dt(self._day_in(m, _month_end(m))),
                "6300",
                _price_minor(rng, w.base, 150, 900),
            )
            m = _add_months(m, 1)
        # the case allows 200..2000 ledger rows; injections run later and add up to 2 rows per issue
        # (<= 12 issues), so the noise filler stops early enough to stay within the limit
        target = min(_rand_range(rng, cfg["ledger_rows"]), LEDGER_ROWS_MAX - INJECTION_HEADROOM)
        current = len(build_ledger(w).rows())
        while current < target:
            if rng.random() < 0.3:
                self._expense(
                    "bank", self._business_dt(self._day_in(start, end)), "6500", _price_minor(rng, w.base, 2, 40)
                )
            else:
                self._expense(
                    "supplies", self._business_dt(self._day_in(start, end)), "6600", _price_minor(rng, w.base, 10, 600)
                )
            current += 2

    def _expense(self, vendor: str, ts: datetime, account: str, amount: int) -> None:
        key = self.ids.new("EXP")
        self.w.expenses.append(Expense(key, ts, account, amount, self.w.vendors[vendor]))


def generate_world(seed: object, cfg: dict) -> World:
    return WorldBuilder(seed, cfg).build()


# --------------------------------------------------------------------------- rendering


def render_invoice(w: World, inv: Invoice) -> dict:
    tz = tz_from_minutes(inv.render_tz)
    return {
        "doc_id": inv.doc_id,
        "invoice_id": inv.invoice_id,
        "entity_id": inv.entity_id,
        "issued_at": iso(inv.issued_at.astimezone(tz)),
        "due_at": iso(inv.due_at.astimezone(tz)),
        "currency": inv.currency,
        "total_minor": inv.total_minor,
        "line_items": [dict(i) for i in inv.line_items],
    }


def render_payment(w: World, pay: Payment) -> dict:
    tz = tz_from_minutes(pay.render_tz)
    return {
        "doc_id": pay.doc_id,
        "payment_id": pay.payment_id,
        "entity_id": pay.entity_id,
        "kind": pay.kind,
        "timestamp": iso(pay.timestamp.astimezone(tz)),
        "currency": pay.currency,
        "amount_minor": pay.amount_minor,
        "invoice_refs": [dict(r) for r in pay.invoice_refs] if pay.invoice_refs is not None else None,
    }


def render_row(w: World, r: Row) -> dict:
    return {
        "row_id": r.row_id,
        "timestamp": iso(r.timestamp.astimezone(w.tz)),
        "account": r.account,
        "debit_minor": r.debit_minor,
        "credit_minor": r.credit_minor,
        "currency": r.currency,
        "entity_id": r.entity_id,
        "invoice_id": r.invoice_id,
        "payment_id": r.payment_id,
        "entry_id": r.entry_id,
    }


def render_fx(r: FxRate) -> dict:
    return {
        "date": r.day.isoformat(),
        "source_currency": r.source,
        "target_currency": r.target,
        "rate": r.rate,
        "rate_id": r.rate_id,
    }


def render_policy(w: World) -> dict:
    return {
        "functional_currency": w.base,
        "ledger_currency": "All ledger rows are in the functional currency (minor units).",
        "period": {
            "start": w.period_start.isoformat(),
            "end": w.period_end.isoformat(),
            "timezone": tz_label(w.tz_minutes),
            "membership": "A timestamp belongs to the period if its local calendar date in the company "
            "timezone is within [start, end] inclusive. Printed offsets on documents vary.",
        },
        "revenue_recognition": "An invoice is recognised (Dr 1100 / Cr 4000, payment_id null) in the period "
        "that contains its issued_at; booking may lag issuance but never crosses a period.",
        "fx": {
            "direction": "1 unit of source_currency = rate units of target_currency",
            "rate_date": "Invoice bookings use the rate for the local date of issued_at; payment bookings use "
            "the rate for the local date of the payment timestamp (company timezone).",
            "fallback": "Rates are published Monday-Friday only; use the latest published date on or before the "
            "rate date.",
            "conversion": "base_minor = round(amount_minor * rate * 10^(exp_base - exp_source))",
        },
        "rounding": {"mode": w.rounding, "scope": "once per converted amount"},
        "payments": {
            "application": "A receipt is applied (Cr 1100 with invoice_id and payment_id) to every invoice listed "
            "in invoice_refs for the referenced amount. Only the part of a receipt not covered by "
            "invoice_refs (or the whole receipt when invoice_refs is null) goes to 2200.",
            "carrying_amount": "AR relieved = referenced amount converted at the invoice's booking rate; a "
            "reference that settles the invoice in full relieves its booked AR amount.",
            "fx_difference": "Bank debit minus credits is posted to 7900.",
            "refunds": "kind=refund returns previously unapplied cash: Dr 2200 / Cr 1000.",
        },
        "accounts": dict(ACCOUNTS),
        "currency_exponents": dict(CURRENCY_EXPONENTS),
    }
