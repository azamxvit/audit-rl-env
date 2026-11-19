"""Safe arithmetic calculator for the agent.

The expression is parsed with :mod:`ast` and only a small whitelist of nodes is
evaluated (numbers, + - * / // % **, unary +/-, parentheses). Every literal is
re-read from its source text as a ``Decimal`` so ``0.1 + 0.2 == 0.3``.
No names, calls, attributes, subscripts, strings, comprehensions or ``eval``.
"""
from __future__ import annotations

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow, localcontext

MAX_EXPRESSION_CHARS = 256
MAX_NODES = 128
MAX_DEPTH = 32
MAX_EXPONENT = 64
MAX_ABS_RESULT = Decimal("1e40")
PRECISION = 40


class CalculatorError(ValueError):
    """Bounded, implementation-free error message for the agent."""


_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_UNARY = (ast.UAdd, ast.USub)


def _literal(node: ast.Constant, source: str) -> Decimal:
    value = node.value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculatorError("only numbers are allowed")
    text = ast.get_source_segment(source, node)
    if text is None:
        raise CalculatorError("invalid number")
    text = text.replace("_", "")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise CalculatorError("invalid number") from exc
    if not number.is_finite():
        raise CalculatorError("invalid number")
    return _check(number)


def _check(value: Decimal) -> Decimal:
    if not value.is_finite() or abs(value) > MAX_ABS_RESULT:
        raise CalculatorError("result out of range")
    return value


def _eval(node: ast.AST, source: str, depth: int) -> Decimal:
    if depth > MAX_DEPTH:
        raise CalculatorError("expression too deep")
    if isinstance(node, ast.Constant):
        return _literal(node, source)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _UNARY):
        operand = _eval(node.operand, source, depth + 1)
        return _check(-operand if isinstance(node.op, ast.USub) else +operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, _BINOPS):
        left = _eval(node.left, source, depth + 1)
        right = _eval(node.right, source, depth + 1)
        op = node.op
        if isinstance(op, ast.Pow):
            if right != right.to_integral_value() or abs(right) > MAX_EXPONENT:
                raise CalculatorError("exponent must be an integer with |n| <= 64")
            if left == 0 and right < 0:
                raise CalculatorError("division by zero")
            return _check(left ** int(right))
        if isinstance(op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise CalculatorError("division by zero")
        if isinstance(op, ast.Add):
            return _check(left + right)
        if isinstance(op, ast.Sub):
            return _check(left - right)
        if isinstance(op, ast.Mult):
            return _check(left * right)
        if isinstance(op, ast.Div):
            return _check(left / right)
        if isinstance(op, ast.FloorDiv):
            return _check(left // right)
        return _check(left % right)
    raise CalculatorError("only arithmetic on decimal numbers is allowed")


def evaluate(expression: object) -> str:
    """Evaluate ``expression`` and return the result as a plain decimal string."""
    if not isinstance(expression, str):
        raise CalculatorError("expression must be a string")
    if len(expression) > MAX_EXPRESSION_CHARS:
        raise CalculatorError("expression too long")
    if not expression.strip():
        raise CalculatorError("empty expression")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise CalculatorError("syntax error") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise CalculatorError("expression too long")
    source = expression.strip()
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.traps[DivisionByZero] = True
        ctx.traps[Overflow] = True
        ctx.traps[InvalidOperation] = True
        try:
            result = _eval(tree.body, source, 0)
        except (DivisionByZero, Overflow, InvalidOperation, ZeroDivisionError) as exc:
            raise CalculatorError("arithmetic error") from exc
        except RecursionError as exc:  # pragma: no cover - guarded by MAX_DEPTH
            raise CalculatorError("expression too deep") from exc
    text = format(result.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text
