import pytest

from audit_env.money import MoneyError, convert, exponent, format_major, parse_rate


def test_exponents():
    assert exponent("USD") == 2
    assert exponent("JPY") == 0
    with pytest.raises(MoneyError):
        exponent("XXX")


def test_convert_basic_and_exponent_shift():
    # 100.00 EUR at 1.084512 -> 108.4512 USD -> 108.45
    assert convert(10000, "EUR", "USD", "1.084512") == 10845
    # 1000 JPY (exp 0) at 0.0067 USD -> 6.70 USD
    assert convert(1000, "JPY", "USD", "0.0067") == 670
    # 1.00 USD -> JPY at 149.5 -> 149.5 -> half-even -> 150? 149.5 -> 150 (even is 150)
    assert convert(100, "USD", "JPY", "149.5") == 150
    assert convert(100, "USD", "JPY", "148.5") == 148  # banker's rounding


def test_convert_rounding_modes():
    assert convert(5, "EUR", "USD", "0.5", "half_even") == 2  # 2.5 -> 2
    assert convert(5, "EUR", "USD", "0.5", "half_up") == 3


def test_convert_same_currency_and_validation():
    assert convert(1234, "USD", "USD", "1") == 1234
    with pytest.raises(MoneyError):
        convert(1234, "USD", "USD", "1.1")
    with pytest.raises(MoneyError):
        convert(1.5, "EUR", "USD", "1.1")
    with pytest.raises(MoneyError):
        convert(True, "EUR", "USD", "1.1")
    for bad in ["abc", "-1", "0", "NaN", "Infinity", 1.1]:
        with pytest.raises(MoneyError):
            parse_rate(bad)


def test_convert_is_exact_decimal_not_float():
    # float math would give 0.30000000000000004 style artefacts
    assert convert(10, "EUR", "USD", "0.1") == 1
    assert convert(-10000, "EUR", "USD", "1.084512") == -10845


def test_format_major():
    assert format_major(123456, "USD") == "1234.56"
    assert format_major(-5, "EUR") == "-0.05"
    assert format_major(1500, "JPY") == "1500"
