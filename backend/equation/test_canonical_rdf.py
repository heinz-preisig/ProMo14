import pytest
from rdflib import Graph, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF

from backend.core.vocab import PROMO

from .canonical import (
    PRODUCT_OVER_INDEX,
    Expression,
    IndexReference,
    VariableReference,
    from_checked,
)
from .canonical_rdf import (
    EXPRESSION,
    HAS_ARGUMENTS,
    HAS_OPERATION,
    attach_rhs_expression,
    read_expression,
    read_rhs_expression,
)
from .checker import check
from .errors import VarError
from .parser import parse
from .test_checker import N, _space


BASE = "http://promo.example"


def _canonical(source, lhs=None):
    space = _space()
    left = parse(lhs) if lhs else None
    return from_checked(check(parse(source), space, left), space)


def test_rdf_round_trip_preserves_nested_canonical_expression():
    graph = Graph()
    canonical = _canonical("(rho . x) + (rho . x)")
    root = attach_rhs_expression(graph, URIRef(f"{BASE}/eq/E_1"), canonical)

    assert (root, RDF.type, EXPRESSION) in graph
    assert read_rhs_expression(graph, URIRef(f"{BASE}/eq/E_1")) == canonical


def test_rdf_round_trip_preserves_index_reference():
    graph = Graph()
    canonical = _canonical("Product(N, N)")
    root = attach_rhs_expression(graph, URIRef(f"{BASE}/eq/E_2"), canonical)

    operation = graph.value(root, HAS_OPERATION)
    args_node = graph.value(root, HAS_ARGUMENTS)
    args = list(Collection(graph, args_node))
    assert str(operation) == PRODUCT_OVER_INDEX
    assert args[1] == URIRef(N)
    assert read_expression(graph, root) == canonical


def test_rdf_round_trip_preserves_variable_reference_roles():
    graph = Graph()
    canonical = _canonical("Instantiate(M)", lhs="one")
    root = attach_rhs_expression(graph, URIRef(f"{BASE}/eq/E_3"), canonical)

    assert read_expression(graph, root) == canonical


def test_rdf_rejects_wrong_argument_kind():
    bad = Expression(
        PRODUCT_OVER_INDEX,
        (
            VariableReference(f"{BASE}/var/N"),
            VariableReference(N),
        ),
    )
    with pytest.raises(VarError, match="index"):
        attach_rhs_expression(graph := Graph(), URIRef(f"{BASE}/eq/bad"), bad)
    assert len(graph) == 0


def test_replacing_rhs_clears_nested_expression_graph():
    graph = Graph()
    equation = URIRef(f"{BASE}/eq/E_4")
    root = URIRef(f"{BASE}/eq/E_4/expression")

    first = _canonical("rho + rho")
    second = _canonical("rho . x")
    attach_rhs_expression(graph, equation, first, root)
    attach_rhs_expression(graph, equation, second, root)

    expressions = list(graph.subjects(RDF.type, EXPRESSION))
    assert len(expressions) == 1
    assert read_rhs_expression(graph, equation) == second
