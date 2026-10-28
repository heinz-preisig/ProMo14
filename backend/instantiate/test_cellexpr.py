"""Expression-valued value cells — docs/value-expression.md."""

import pytest

from backend.instantiate.cellexpr import (
    CellExprError,
    evaluate,
    parse_cell,
    resolve,
    symbols,
)


def test_scalar_subset_evaluates():
    env = {"a": 2.0, "b": 3.0}
    for text, want in [
        ("a + b", 5.0), ("a - b", -1.0), ("a * b", 6.0),
        ("a . b", 6.0), ("a : b", 6.0), ("a ^ b", 8.0),
        ("(a + b) * a", 10.0), ("inv(a)", 0.5), ("neg(a)", -2.0),
        ("max(a, b)", 3.0), ("min(a, b)", 2.0), ("ln(exp(a))", 2.0),
    ]:
        assert evaluate(parse_cell(text), env) == pytest.approx(want), text
    assert symbols(parse_cell("a * sqrt(b)")) == {"a", "b"}


def test_out_of_subset_rejected():
    for text in ["reduceSum(a, i)", "Root(a)", "Instantiate(a)",
                 "TotalDiff(a, b)", "left(a)", "a + 1"]:
        with pytest.raises(CellExprError):
            parse_cell(text)


def test_numeric_failure_is_cell_error():
    with pytest.raises(CellExprError):
        evaluate(parse_cell("inv(a)"), {"a": 0.0})
    with pytest.raises(CellExprError):
        evaluate(parse_cell("sqrt(a)"), {"a": -1.0})


def test_resolve_chain_unknown_cycle():
    # y := x * x (chained through provided scalar x := a + a)
    results, failures = resolve(
        {"x * x", "u", "p + q"},
        {"a": 1.5},
        {"x": "a + a", "p": "q", "q": "p"})
    assert results["a + a"] == 3.0
    assert results["x * x"] == 9.0
    assert failures["u"][0] == "unresolved-cell"
    assert failures["p + q"][0] == "cell-cycle"
    assert failures["q"][0] == "cell-cycle"
    assert "p -> q -> p" in failures["q"][1] or \
        "q -> p -> q" in failures["q"][1]
