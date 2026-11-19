"""Deterministic helpers: derived RNG streams, opaque IDs, time handling, JSON."""
from __future__ import annotations

import hashlib
import json
import random
from datetime import date, datetime, timedelta, timezone

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ID_LEN = 8


def derive_seed(seed: object, stream: str) -> int:
    digest = hashlib.sha256(f"{seed!r}|{stream}".encode("utf-8")).digest()
    return int.from_bytes(digest[:16], "big")


def derive_rng(seed: object, stream: str) -> random.Random:
    """Independent, reproducible RNG stream. ``random.Random`` is the only source of randomness."""
    return random.Random(derive_seed(seed, stream))


def hashed_token(salt: str, *parts: str, n: int = ID_LEN) -> str:
    digest = hashlib.sha256("|".join((salt,) + parts).encode("utf-8")).digest()
    value = int.from_bytes(digest[:10], "big")
    out = []
    for _ in range(n):
        value, r = divmod(value, 32)
        out.append(CROCKFORD[r])
    return "".join(out)


class IdFactory:
    """Random opaque IDs ``PREFIX-XXXXXXXX``; the format never encodes error status or order."""

    def __init__(self, rng: random.Random, used: set[str] | None = None):
        self.rng = rng
        self.used = used if used is not None else set()

    def new(self, prefix: str) -> str:
        while True:
            token = f"{prefix}-" + "".join(self.rng.choice(CROCKFORD) for _ in range(ID_LEN))
            if token not in self.used:
                self.used.add(token)
                return token


def tz_from_minutes(minutes: int) -> timezone:
    return timezone(timedelta(minutes=minutes))


def tz_label(minutes: int) -> str:
    sign = "+" if minutes >= 0 else "-"
    m = abs(minutes)
    return f"{sign}{m // 60:02d}:{m % 60:02d}"


def parse_tz_label(label: str) -> timezone:
    sign = 1 if label[0] == "+" else -1
    hh, mm = label[1:].split(":")
    return tz_from_minutes(sign * (int(hh) * 60 + int(mm)))


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def parse_iso(text: str) -> datetime:
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("timestamp without offset")
    return dt


def local_date(dt: datetime, tz: timezone) -> date:
    return dt.astimezone(tz).date()


def dumps(obj: object) -> str:
    """Canonical JSON (stable key order, no whitespace variance)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
