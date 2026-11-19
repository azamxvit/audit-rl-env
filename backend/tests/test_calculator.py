import pytest

from audit_env.calculator import CalculatorError, evaluate


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("1+2", "3"),
        ("0.1 + 0.2", "0.3"),
        ("10845 - 10831", "14"),
        ("100.00 * 1.084512", "108.4512"),
        ("(1 + 2) * 3", "9"),
        ("-5 + +2", "-3"),
        ("7 // 2", "3"),
        ("7 % 4", "3"),
        ("2 ** 10", "1024"),
        ("1 / 4", "0.25"),
        ("1_000 + 1", "1001"),
        ("1e3", "1000"),
        ("0 * -1", "0"),
    ],
)
def test_arithmetic(expr, expected):
    assert evaluate(expr) == expected


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('ls')",
        "open('/etc/passwd')",
        "x + 1",
        "abs(-1)",
        "(1).real",
        "[1, 2][0]",
        "'a' * 3",
        "1 if 1 else 2",
        "1 < 2",
        "lambda: 1",
        "True + 1",
        "None",
        "2 ** 1000",
        "9 ** 9 ** 9",
        "10 ** 0.5",
        "1 / 0",
        "1 % 0",
        "0 ** -1",
        "1e400",
        "",
        "   ",
        "1 +",
        "1;2",
        "import os",
        "1" * 300,
        "-" * 40 + "1",
        "{1: 2}",
        "f'{1}'",
        "1 @ 2",
        "~1",
        "1 << 2",
    ],
)
def test_rejects_non_arithmetic(expr):
    with pytest.raises(CalculatorError):
        evaluate(expr)


def test_rejects_non_string():
    with pytest.raises(CalculatorError):
        evaluate(123)


def test_error_messages_are_bounded():
    try:
        evaluate("__import__('secret_truth_path')")
    except CalculatorError as exc:
        assert "secret" not in str(exc)
        assert len(str(exc)) < 80
