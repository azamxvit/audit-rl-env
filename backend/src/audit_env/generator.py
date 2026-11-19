"""world -> clean documents/ledger -> error injection -> public files + private truth.

``generate_episode(seed, config)`` is a pure function of (seed, config, ENV_VERSION).
"""
from __future__ import annotations

import copy
import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import ENV_VERSION, SCHEMA_VERSION
from .errors import InjectionContext, plan_and_inject
from .errors.base import booking_params
from .errors.distractors import summarize
from .util import IdFactory, derive_rng, dumps, sha256_text, tz_label
from .world import (WorldBuilder, World, build_ledger, render_fx, render_invoice, render_payment,
                    render_policy, render_row)

TOLERANCE_MINOR = 1

DEFAULT_CONFIG: dict = {
    "schema_version": SCHEMA_VERSION,
    "config_id": "default",
    "period": "quarter",
    "base_currencies": ["USD", "EUR", "GBP", "KZT"],
    "foreign_currencies": ["USD", "EUR", "GBP", "CHF", "JPY", "KZT"],
    "foreign_customer_share": 0.35,
    "n_customers": [8, 16],
    "n_invoices": [30, 60],
    "n_prior_period_invoices": [3, 6],
    "n_next_period_invoices": [2, 5],
    "ledger_rows": [300, 600],
    "errors": {
        "duplicate_invoice": {"count": [0, 2]},
        "payment_allocation": {"count": [0, 2]},
        "fx_error": {"count": [0, 2]},
        "period_cutoff": {"count": [0, 2]},
    },
    "scenarios": {
        "fx_partial_boundary": {"count": [0, 1]},
        "cutoff_fx": {"count": [0, 1]},
    },
    "distractors": {
        "split_payments": 0.15,
        "multi_invoice_payments": 0.25,
        "overpayments": [1, 2],
        "unidentified_receipts": [0, 2],
        "subscriptions": 0.3,
        "booking_delay": 0.3,
        "boundary_documents": [1, 3],
        "boundary_partial_payments": [1, 2],
    },
}

PUBLIC_TABLES = ("ledger", "invoices", "payments", "fx")
LEDGER_COLUMNS = ["row_id", "timestamp", "account", "debit_minor", "credit_minor", "currency",
                  "entity_id", "invoice_id", "payment_id", "entry_id"]
FX_COLUMNS = ["date", "source_currency", "target_currency", "rate", "rate_id"]
LEDGER_INT = {"debit_minor", "credit_minor"}


def merge_config(config: Optional[dict]) -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    for key, value in (config or {}).items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key] = {**cfg[key], **copy.deepcopy(value)}
        else:
            cfg[key] = copy.deepcopy(value)
    return cfg


@dataclass
class Episode:
    public: dict
    truth: dict
    provenance: dict
    clean_public: dict  # same world before error injection (for invariant checks)

    @property
    def episode_id(self) -> str:
        return self.public["manifest"]["episode_id"]


def render_public(world: World, ledger) -> dict:
    invoices = sorted(world.invoices.values(), key=lambda i: (i.issued_at.timestamp(), i.doc_id))
    payments = sorted(world.payments.values(), key=lambda p: (p.timestamp.timestamp(), p.doc_id))
    rows = sorted(ledger.rows(), key=lambda r: (r.timestamp.timestamp(), r.entry_id, r.row_id))
    fx = sorted(world.fx.rates, key=lambda r: (r.day, r.source, r.rate_id))
    public = {
        "ledger": [render_row(world, r) for r in rows],
        "invoices": [render_invoice(world, i) for i in invoices],
        "payments": [render_payment(world, p) for p in payments],
        "fx": [render_fx(r) for r in fx],
        "policy": render_policy(world),
    }
    public["manifest"] = {
        "schema_version": SCHEMA_VERSION,
        "env_version": ENV_VERSION,
        "episode_id": world.episode_id,
        "company_name": world.company_name,
        "base_currency": world.base,
        "period_start": world.period_start.isoformat(),
        "period_end": world.period_end.isoformat(),
        "timezone": tz_label(world.tz_minutes),
        "counts": {
            "ledger_rows": len(public["ledger"]),
            "invoices": len(public["invoices"]),
            "payments": len(public["payments"]),
            "fx_rates": len(public["fx"]),
            "documents": len(public["invoices"]) + len(public["payments"]),
        },
        "rounding": {"mode": world.rounding, "scope": "once per converted amount"},
    }
    return public


def _entry_dump(world: World, ledger, source) -> Optional[list]:
    e = ledger.by_source.get(source)
    if e is None:
        return None
    return [render_row(world, r) for r in sorted(e.rows, key=lambda r: r.row_id)]


def generate_episode(seed: object, config: Optional[dict] = None) -> Episode:
    cfg = merge_config(config)
    builder = WorldBuilder(seed, cfg)
    world = builder.build()
    clean_ledger = build_ledger(world)
    clean_public = render_public(world, clean_ledger)

    ctx = InjectionContext(world, derive_rng(seed, "inject"), IdFactory(derive_rng(seed, "inject-ids"), world.used_ids))
    specs = plan_and_inject(ctx, cfg)
    ledger = build_ledger(world)
    public = render_public(world, ledger)

    issue_ids = IdFactory(derive_rng(seed, "issue-ids"), set(world.used_ids))
    issues = []
    for spec in specs:
        amount, evidence = spec.resolve(world, ledger)
        issues.append({
            "issue_id": issue_ids.new("ISS"),
            "type": spec.type,
            "affected_ids": sorted(spec.affected_ids),
            "expected_amount_minor": amount,
            "currency": world.base,
            "evidence_sets": evidence,
            "variant": spec.variant,
            "scenario": spec.scenario,
            "_targets": spec.targets,
        })
    issues.sort(key=lambda i: (i["type"], i["affected_ids"], i["issue_id"]))

    changes = []
    by_target: dict = {}
    for iss in issues:
        for t in iss["_targets"]:
            by_target.setdefault(tuple(t), []).append(iss["issue_id"])
    for n, (target, ids) in enumerate(sorted(by_target.items())):
        kind, bid = target
        obj = world.invoices[bid] if kind == "invoice" else world.payments[bid]
        added = target in ctx.added
        doc = render_invoice(world, obj) if kind == "invoice" else render_payment(world, obj)
        changes.append({
            "change_id": f"CHG-{n + 1:03d}",
            "issue_ids": sorted(ids),
            "target": [kind, bid],
            "op": "add_document_and_booking" if added else "change_booking",
            "document_added": doc if added else None,
            "booking_before": None if added else ctx.snapshots.get(target),
            "booking_after": booking_params(obj),
            "ledger_before": None if added else _entry_dump(world, clean_ledger, target),
            "ledger_after": _entry_dump(world, ledger, target),
        })
    for iss in issues:
        del iss["_targets"]

    truth = {
        "schema_version": SCHEMA_VERSION,
        "episode_id": world.episode_id,
        "base_currency": world.base,
        "tolerance_minor": TOLERANCE_MINOR,
        "issues": issues,
    }
    provenance = {
        "schema_version": SCHEMA_VERSION,
        "env_version": ENV_VERSION,
        "episode_id": world.episode_id,
        "config_id": cfg.get("config_id"),
        "config_sha256": sha256_text(dumps(cfg)),
        "pipeline": ["world_history", "render_clean", "inject_errors", "rebuild_ledger", "render_public"],
        "clean_counts": clean_public["manifest"]["counts"],
        "distractors": summarize(world),
        "changes": changes,
    }
    return Episode(public, truth, provenance, clean_public)


# --------------------------------------------------------------------------- files

def _csv_text(rows: list, columns: list) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for r in rows:
        writer.writerow(["" if r[c] is None else r[c] for c in columns])
    return buf.getvalue()


def _jsonl_text(rows: list) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows)


def _json_text(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def public_files(public: dict) -> dict:
    return {
        "manifest.json": _json_text(public["manifest"]),
        "policy.json": _json_text(public["policy"]),
        "ledger.csv": _csv_text(public["ledger"], LEDGER_COLUMNS),
        "invoices.jsonl": _jsonl_text(public["invoices"]),
        "payments.jsonl": _jsonl_text(public["payments"]),
        "fx.csv": _csv_text(public["fx"], FX_COLUMNS),
    }


def write_episode(episode: Episode, directory: Path) -> None:
    """``<dir>/public/*`` is what an agent-side loader may read; ``<dir>/private/*`` is grader-only."""
    directory = Path(directory)
    (directory / "public").mkdir(parents=True, exist_ok=True)
    (directory / "private").mkdir(parents=True, exist_ok=True)
    for name, text in public_files(episode.public).items():
        (directory / "public" / name).write_text(text, encoding="utf-8")
    (directory / "private" / "truth.json").write_text(_json_text(episode.truth), encoding="utf-8")
    (directory / "private" / "provenance.json").write_text(_json_text(episode.provenance), encoding="utf-8")


def _read_csv(path: Path, int_cols: set) -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        out = []
        for rec in csv.DictReader(fh):
            row = {}
            for k, v in rec.items():
                if v == "":
                    row[k] = None
                elif k in int_cols:
                    row[k] = int(v)
                else:
                    row[k] = v
            out.append(row)
        return out


def load_public(directory: Path) -> dict:
    d = Path(directory) / "public"
    return {
        "manifest": json.loads((d / "manifest.json").read_text(encoding="utf-8")),
        "policy": json.loads((d / "policy.json").read_text(encoding="utf-8")),
        "ledger": _read_csv(d / "ledger.csv", LEDGER_INT),
        "invoices": [json.loads(x) for x in (d / "invoices.jsonl").read_text(encoding="utf-8").splitlines() if x],
        "payments": [json.loads(x) for x in (d / "payments.jsonl").read_text(encoding="utf-8").splitlines() if x],
        "fx": _read_csv(d / "fx.csv", set()),
    }


def load_private(directory: Path) -> tuple:
    d = Path(directory) / "private"
    return (json.loads((d / "truth.json").read_text(encoding="utf-8")),
            json.loads((d / "provenance.json").read_text(encoding="utf-8")))


def load_config(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
