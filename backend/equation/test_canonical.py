import pytest

from .canonical import (
    ADD, Expression, VariableReference, from_checked, to_source,
)
from .checker import check
from .parser import parse
from .test_checker import _space


def _canonical(source, space=None, lhs=None):
    context = space or _space()
    left = parse(lhs) if lhs else None
    return from_checked(check(parse(source), context, left), context)


def test_add_uses_operation_and_variable_iris():
    assert _canonical("rho + rho") == Expression(
        ADD,
        (
            VariableReference("http://promo.example/var/rho"),
            VariableReference("http://promo.example/var/rho"),
        ),
    )


def test_group_is_not_semantic():
    assert _canonical("( rho + rho )") == _canonical("rho + rho")


def test_source_regeneration_uses_current_variable_label():
    space = _space()
    canonical = _canonical("rho + rho", space)
    space.variables["http://promo.example/var/rho"].label = "density"
    assert to_source(canonical, space) == "( density + density )"


def test_source_regeneration_qualifies_foreign_variable():
    space = _space()
    space.expression_definition_network = "other"
    reference = VariableReference("http://promo.example/var/rho")
    assert to_source(reference, space) == "thermo!rho"


@pytest.mark.parametrize(
    ("source", "lhs"),
    [
        ("rho + rho", None),
        ("rho . x", None),
        ("rho * v", None),
        ("one ^ one", None),
        ("Product(N, N)", None),
        ("reduceSum(rho, N)", None),
        ("Integral(M :: M in [one, one])", None),
        ("TotalDiff(A, x)", None),
        ("ParDiff(A, x)", None),
        ("Root(rho + rho)", "rho"),
        ("Instantiate(M)", "one"),
        ("sqrt(one)", None),
        ("inv(M)", None),
        ("max(M, M)", None),
    ],
)
def test_semantic_round_trip(source, lhs):
    space = _space()
    canonical = _canonical(source, space, lhs)
    regenerated = to_source(canonical, space)
    assert _canonical(regenerated, space, lhs) == canonical
