"""§40 product-notation migration — regression tests.

Legacy ``a . b`` (index-preserving product) respells to ``a * b``;
legacy ``a * b`` (implicit reduce) becomes
``reduceSum( (a * b), i )`` with ``i`` the operands' shared index.
"""

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from backend.core.vocab import PROMO
from backend.equation.canonical import (
    INDEX_PRESERVING_PRODUCT, REDUCE_PRODUCT, SUM_OVER_INDEX,
    Expression, IndexReference, VariableReference, from_checked, to_source,
)
from backend.equation.canonical_rdf import (
    attach_rhs_expression, read_rhs_expression,
)
from backend.equation.checker import check
from backend.equation.compile_space import CompileSpace, Index, Variable
from backend.equation.migrate_products import (
    MigrationAnomaly, rewrite_canonical, rewrite_literal,
)
from backend.equation.parser import parse

N = "http://promo.example/index/N"
S = "http://promo.example/index/S"


def _space():
    n_idx = Index(iri=N, label="species", network="thermo",
                  aliases={"internal_code": "N"})
    s_idx = Index(iri=S, label="reaction", network="thermo",
                  aliases={"internal_code": "S"})
    variables = {
        "http://promo.example/var/rho": Variable(
            iri="http://promo.example/var/rho", label="rho",
            network="thermo", type="state", index_structures=[N]),
        "http://promo.example/var/v": Variable(
            iri="http://promo.example/var/v", label="v",
            network="thermo", type="state", index_structures=[N]),
        "http://promo.example/var/M": Variable(
            iri="http://promo.example/var/M", label="M",
            network="thermo", type="parameter", index_structures=[N, S]),
        "http://promo.example/var/mass": Variable(
            iri="http://promo.example/var/mass", label="mass",
            network="thermo", type="state", index_structures=[N]),
    }
    return CompileSpace(
        variables, {N: n_idx, S: s_idx},
        variable_definition_network="thermo",
        expression_definition_network="thermo")


def test_literal_dot_respells_to_star():
    source, changed = rewrite_literal("rho . v", _space())
    assert source == "rho * v"
    assert changed


def test_literal_star_becomes_reduce_sum():
    source, changed = rewrite_literal("rho * v", _space())
    assert source == "reduceSum( ( rho * v ), N )"
    assert changed


def test_literal_mixed_operators():
    source, changed = rewrite_literal(
        "( mass * ( rho . v ) )", _space())
    # mass[N] contracts the shared N of rho . v
    assert source == "( reduceSum( ( mass * ( rho * v ) ), N ) )"
    assert changed


def test_literal_star_ambiguous_shared_index_raises():
    # M[N,S] * M[N,S] share N *and* S — no unique contraction
    with pytest.raises(MigrationAnomaly):
        rewrite_literal("M * M", _space())


def test_literal_no_product_ops_is_untouched():
    source, changed = rewrite_literal("missing + rho", _space())
    assert source == "missing + rho"   # verbatim — no reformat churn
    assert not changed


def test_literal_rewrite_is_idempotent():
    once, _ = rewrite_literal("rho * v", _space())
    twice, changed = rewrite_literal(once, _space())
    # re-parsed under the legacy table the inner `*` looks like a
    # reduce again — but its shared index N is bound by the enclosing
    # reduceSum, so the text is recognised as already-migrated.
    assert twice == "reduceSum( ( rho * v ), N )"
    assert not changed


def test_canonical_product_regenerates_as_star():
    space = _space()
    canonical = from_checked(check(parse("rho * v"), space), space)
    assert to_source(canonical, space) == "( rho * v )"


def _reduce_product_tree():
    """The stored pre-§40 shape: ReduceProduct(rho, v)."""
    return Expression(
        REDUCE_PRODUCT,
        (VariableReference("http://promo.example/var/rho"),
         VariableReference("http://promo.example/var/v")))


def test_rewrite_canonical_reduce_product():
    space = _space()
    arg, touched = rewrite_canonical(_reduce_product_tree(), space)
    assert touched
    assert arg == Expression(
        SUM_OVER_INDEX,
        (Expression(
            INDEX_PRESERVING_PRODUCT,
            (VariableReference("http://promo.example/var/rho"),
             VariableReference("http://promo.example/var/v"))),
         IndexReference(N)))
    assert to_source(arg, space) == "reduceSum( ( rho * v ), N )"


def test_rewrite_canonical_is_idempotent():
    space = _space()
    arg, _ = rewrite_canonical(_reduce_product_tree(), space)
    again, touched = rewrite_canonical(arg, space)
    assert again == arg
    assert not touched


def test_rewrite_canonical_unknown_var_is_anomaly():
    tree = Expression(
        REDUCE_PRODUCT,
        (VariableReference("http://promo.example/var/ghost"),
         VariableReference("http://promo.example/var/v")))
    with pytest.raises(MigrationAnomaly):
        rewrite_canonical(tree, _space())


def test_reduce_product_rdf_round_trip_is_readable():
    """Stored ReduceProduct trees must stay readable for migration —
    the retired op keeps a read-side signature only."""
    space = _space()
    graph = Graph()
    equation = URIRef("http://promo.example/eq/E_1")
    root = attach_rhs_expression(graph, equation, _reduce_product_tree())
    arg = read_rhs_expression(graph, equation)
    assert arg == _reduce_product_tree()
    migrated, touched = rewrite_canonical(arg, space)
    assert touched
    assert to_source(migrated, space) == "reduceSum( ( rho * v ), N )"
