"""RDF persistence for canonical expressions.

Canonical expressions are stored as semantic RDF resources, not as an AST
serialisation.  An expression node has:

- ``rdf:type promo:Expression``
- ``promo:hasOperation`` — the language operation IRI
- ``promo:hasArguments`` — one RDF list containing ordered arguments

Variable and index arguments are their entity IRIs directly. Nested expressions
are normally blank nodes. An equation links to its root with
``promo:rhsExpression``; ``promo:rhs`` remains a regenerated source cache.
"""

from __future__ import annotations

from typing import Optional

from rdflib import BNode, Graph, URIRef
from rdflib.collection import Collection
from rdflib.namespace import RDF
from rdflib.term import Node

from backend.core.vocab import PROMO

from .canonical import (
    Argument,
    Expression,
    IndexReference,
    VariableReference,
    operation_arguments,
    validate_expression,
)
from .errors import VarError

EXPRESSION = PROMO["Expression"]
HAS_OPERATION = PROMO["hasOperation"]
HAS_ARGUMENTS = PROMO["hasArguments"]
RHS_EXPRESSION = PROMO["rhsExpression"]


def write_expression(
    graph: Graph,
    argument: Argument,
    subject: Optional[Node] = None,
) -> Node:
    """Write ``argument`` to ``graph`` and return its RDF node.

    ``subject`` may identify the root resource, for example
    ``<equation>/expression``. Nested expressions and RDF lists use blank
    nodes. Variable and index references remain their target IRIs.
    """
    validate_expression(argument)
    if subject is not None:
        clear_expression(graph, subject)
    if isinstance(argument, VariableReference):
        return URIRef(argument.iri)
    if isinstance(argument, IndexReference):
        return URIRef(argument.iri)

    node = subject or BNode()
    graph.add((node, RDF.type, EXPRESSION))
    graph.set((node, HAS_OPERATION, URIRef(argument.operation_iri)))

    args_node = BNode()
    Collection(
        graph,
        args_node,
        [write_expression(graph, value) for value in argument.arguments],
    )
    graph.set((node, HAS_ARGUMENTS, args_node))
    return node


def attach_rhs_expression(
    graph: Graph,
    equation: Node,
    argument: Argument,
    subject: Optional[Node] = None,
) -> Node:
    """Attach ``argument`` as ``equation``'s canonical RHS and return it."""
    old = graph.value(equation, RHS_EXPRESSION)
    if old is not None:
        clear_expression(graph, old)
    node = write_expression(graph, argument, subject)
    graph.set((equation, RHS_EXPRESSION, node))
    return node


def read_expression(graph: Graph, node: Node) -> Argument:
    """Read a canonical expression, variable reference or index reference."""
    if _is_expression(graph, node):
        operation = graph.value(node, HAS_OPERATION)
        args_node = graph.value(node, HAS_ARGUMENTS)
        if not isinstance(operation, URIRef):
            raise VarError("canonical RDF expression has no operation IRI")
        if args_node is None:
            raise VarError("canonical RDF expression has no argument list")

        signature = operation_arguments(str(operation))
        items = list(Collection(graph, args_node))
        if len(items) != len(signature):
            raise VarError(
                "canonical RDF %s requires %d arguments, got %d"
                % (operation, len(signature), len(items))
            )
        return Expression(
            str(operation),
            tuple(
                _read_argument(graph, item, kind)
                for item, kind in zip(items, signature)
            ),
        )
    if isinstance(node, URIRef):
        return VariableReference(str(node))
    raise VarError("canonical RDF node %r is not an expression or reference" % node)


def read_rhs_expression(graph: Graph, equation: Node) -> Optional[Argument]:
    """Return an equation's canonical RHS, or ``None`` for legacy text only."""
    node = graph.value(equation, RHS_EXPRESSION)
    if node is None:
        return None
    return read_expression(graph, node)


def clear_expression(graph: Graph, node: Node) -> None:
    """Remove an expression node, its nested expressions, and RDF list cells."""
    if not _is_expression(graph, node):
        return
    args_node = graph.value(node, HAS_ARGUMENTS)
    if args_node is not None:
        for item in Collection(graph, args_node):
            clear_expression(graph, item)
        Collection(graph, args_node).clear()
    graph.remove((node, None, None))


def _read_argument(graph: Graph, node: Node, kind: str) -> Argument:
    if _is_expression(graph, node):
        if kind != "expression":
            raise VarError(
                "canonical RDF %s argument cannot be an expression" % kind
            )
        return read_expression(graph, node)
    if not isinstance(node, URIRef):
        raise VarError("canonical RDF %s argument must be an IRI" % kind)
    if kind == "index":
        return IndexReference(str(node))
    if kind in ("expression", "variable"):
        return VariableReference(str(node))
    raise VarError("canonical RDF argument kind %r is unknown" % kind)


def _is_expression(graph: Graph, node: Node) -> bool:
    return (node, RDF.type, EXPRESSION) in graph
