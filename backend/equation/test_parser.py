"""Tests for the recursive-descent ProMo expression parser."""

import pytest

from .parser import ParseError, parse
from .syntax import (
    Add, Expand, Group, Hadamard, Instantiate, Integral, MaxMin, ParDiff,
    Power, Product, Reduce, ReduceSum, Root, TotalDiff, UFunc, Var,
)


def _name(n):
    """Small helper to fetch a Var's name or node class."""
    if isinstance(n, Var):
        return n.name
    return n.__class__.__name__


def test_variable():
    assert parse("x") == Var("x")


def test_network_variable():
    assert parse("physical!S") == Var("physical!S")


def test_add():
    assert parse("x + y") == Add("+", Var("x"), Var("y"))


def test_subtract():
    assert parse("x - y") == Add("-", Var("x"), Var("y"))


def test_sum_left_associative():
    assert parse("a + b - c") == Add("-", Add("+", Var("a"), Var("b")), Var("c"))


def test_expand():
    assert parse("a : b") == Expand(Var("a"), Var("b"))


def test_hadamard():
    assert parse("a . b") == Hadamard(Var("a"), Var("b"))


def test_reduce():
    assert parse("a * b") == Reduce(Var("a"), Var("b"))


def test_reduce_with_index():
    assert parse("a * N b") == Reduce(Var("a"), Var("b"), Var("N"))


def test_term_left_associative():
    # a . b * c -> (a . b) * c
    assert parse("a . b * c") == Reduce(
        Hadamard(Var("a"), Var("b")), Var("c")
    )


def test_power_right_associative():
    assert parse("a ^ b ^ c") == Power(
        Var("a"), Power(Var("b"), Var("c"))
    )


def test_power_precedence():
    # a * b ^ c -> a * (b ^ c)
    assert parse("a * b ^ c") == Reduce(
        Var("a"), Power(Var("b"), Var("c"))
    )


def test_brackets():
    node = parse("(x + y)")
    assert isinstance(node, Group)
    assert node.body == Add("+", Var("x"), Var("y"))


def test_brackets_affect_precedence():
    # (a + b) * c is not a * b + c
    assert parse("(a + b) * c") == Reduce(
        Group(Add("+", Var("a"), Var("b"))), Var("c")
    )


def test_ufunc():
    assert parse("sin(x)") == UFunc("sin", Var("x"))


def test_ufunc_nested():
    assert parse("exp(x + y)") == UFunc(
        "exp", Add("+", Var("x"), Var("y"))
    )


def test_max_min():
    assert parse("max(a, b)") == MaxMin("max", Var("a"), Var("b"))
    assert parse("min(a, b)") == MaxMin("min", Var("a"), Var("b"))


def test_instantiate():
    # ADR-008: Instantiate(proto) — single Var argument, whole RHS only.
    assert parse("Instantiate(t)") == Instantiate(Var("t"))


def test_instantiate_qualified_proto():
    assert parse("Instantiate(physical!t)") == Instantiate(Var("physical!t"))


def test_instantiate_rejects_expression_arg():
    with pytest.raises(ParseError):
        parse("Instantiate(x + y)")


def test_instantiate_rejects_two_args():
    with pytest.raises(ParseError):
        parse("Instantiate(t, value)")


def test_instantiate_rejects_nested():
    # A declaration, not a subexpression — never inside brackets, calls,
    # or infix operands.
    for text in (
        "( Instantiate(t) )",
        "sin(Instantiate(t))",
        "x + Instantiate(t)",
        "Instantiate(t) + x",
        "x * Instantiate(t)",
    ):
        with pytest.raises(ParseError):
            parse(text)


def test_integral():
    assert parse("Integral(U :: t in [t0, te])") == Integral(
        Var("U"), Var("t"), Var("t0"), Var("te")
    )


def test_product():
    assert parse("Product(F, N)") == Product(Var("F"), Var("N"))


def test_root():
    assert parse("Root(x)") == Root(Var("x"))


def test_total_diff():
    assert parse("TotalDiff(x, y)") == TotalDiff(Var("x"), Var("y"))


def test_par_diff():
    assert parse("ParDiff(U, n)") == ParDiff(Var("U"), Var("n"))


def test_reduce_sum():
    assert parse("reduceSum(F, N)") == ReduceSum(Var("F"), Var("N"))


def test_complex_expression():
    # U - p . V
    node = parse("U - p . V")
    assert isinstance(node, Add)
    assert node.op == "-"
    assert node.left == Var("U")
    assert isinstance(node.right, Hadamard)
    assert node.right.left == Var("p")
    assert node.right.right == Var("V")


def test_integral_inside_sum():
    node = parse("Integral(U :: t in [t0, te]) - p . V")
    assert isinstance(node, Add)
    assert node.op == "-"
    assert isinstance(node.left, Integral)


def test_error_unexpected_token():
    try:
        parse("x +")
    except ParseError:
        return
    raise AssertionError("expected ParseError")


def test_error_mismatched_paren():
    try:
        parse("(x + y")
    except ParseError:
        return
    raise AssertionError("expected ParseError")


def test_error_unknown_char():
    try:
        parse("x @ y")
    except ParseError:
        return
    raise AssertionError("expected ParseError")


def test_no_numbers():
    # numbers are not part of the language
    try:
        parse("x + 1")
    except ParseError:
        return
    raise AssertionError("expected ParseError for numeric literal")


if __name__ == "__main__":
    import sys

    for name, fn in globals().items():
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as e:
                print(f"FAIL {name}: {e}")
                sys.exit(1)
    print("All tests passed")
