"""Money helpers: integer minor units, currency exponents, Decimal FX conversion.

All amounts in the environment are ``int`` minor units (cents, tiyn, yen...).
FX rates are decimal *strings*; every conversion goes through ``Decimal`` with an
explicit rounding mode so results are bit-for-bit reproducible.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

# ISO-4217 exponents for the currencies the generator uses.
CURRENCY_EXPONENTS: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "CHF": 2,
    "KZT": 2,
    "JPY": 0,
}

ROUNDING_MODES = {
    "half_even": ROUND_HALF_EVEN,
    "half_up": ROUND_HALF_UP,
}

DEFAULT_ROUNDING = "half_even"


class MoneyError(ValueError):
    """Raised for unknown currencies, malformed rates or non-integer amounts."""


def exponent(currency: str) -> int:
    try:
        return CURRENCY_EXPONENTS[currency]
    except KeyError as exc:
        raise MoneyError(f"unknown currency {currency!r}") from exc


def parse_rate(rate: str) -> Decimal:
    """Parse an FX rate string. Rates must be positive finite decimals."""
    if not isinstance(rate, str):
        raise MoneyError("rate must be a decimal string")
    try:
        value = Decimal(rate)
    except InvalidOperation as exc:
        raise MoneyError(f"malformed rate {rate!r}") from exc
    if not value.is_finite() or value <= 0:
        raise MoneyError(f"rate must be positive: {rate!r}")
    return value


def _check_amount(amount_minor: int) -> None:
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        raise MoneyError("amount_minor must be int")


def convert(
    amount_minor: int,
    source: str,
    target: str,
    rate: str,
    rounding: str = DEFAULT_ROUNDING,
) -> int:
    """Convert ``amount_minor`` of ``source`` into minor units of ``target``.

    ``rate`` means: 1 major unit of ``source`` = ``rate`` major units of ``target``.
    The result is rounded once, at the end, to an integer number of target minor units.
    """
    _check_amount(amount_minor)
    if source == target:
        if rate is not None and parse_rate(rate) != 1:
            raise MoneyError("same-currency conversion requires rate 1")
        return amount_minor
    r = parse_rate(rate)
    shift = exponent(target) - exponent(source)
    with localcontext() as ctx:
        ctx.prec = 50
        value = Decimal(amount_minor) * r * (Decimal(10) ** shift)
        return int(value.quantize(Decimal(1), rounding=ROUNDING_MODES[rounding]))


def format_major(amount_minor: int, currency: str) -> str:
    """Human-readable major-unit string, e.g. 123456 USD -> '1234.56'."""
    _check_amount(amount_minor)
    exp = exponent(currency)
    sign = "-" if amount_minor < 0 else ""
    a = abs(amount_minor)
    if exp == 0:
        return f"{sign}{a}"
    return f"{sign}{a // 10**exp}.{a % 10**exp:0{exp}d}"
