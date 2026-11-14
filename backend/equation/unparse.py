"""Render a ``syntax.Node`` back to source text in the current language.

``canonical.to_source`` regenerates text from the *semantic* tree —
variable references become IRIs and re-qualify through the compile
space.  ``node_source`` works on the parse tree itself and preserves
the surface tokens as typed: variable names stay verbatim
(``net!label`` included), so it can rewrite text that could never
resolve — stale network qualifiers, missing variables — faithfully.

Used by the §40 operator migration; generally useful wherever a
syntactic rewrite must round-trip without checking.
"""

from __future__ import annotations

from .syntax import (
    Add, Call, Expand, Group, IndexPreservingProduct, Instantiate, Integral,
    MaxMin, Node, ParDiff, Power, Product, Root, ReduceSum, TotalDiff, UFunc,
    Var,
)


def node_source(node: Node) -> str:
    if isinstance(node, Var):
        return node.name
    if isinstance(node, Group):
        return "( %s )" % node_source(node.body)
    # Infix ops print bare — precedence/associativity make the flat
    # spelling unambiguous on re-parse and ``Group`` nodes carry the
    # explicit parens where the operand order actually matters.
    if isinstance(node, Add):
        return "%s %s %s" % (
            node_source(node.left), node.op, node_source(node.right))
    if isinstance(node, Expand):
        return "%s : %s" % (node_source(node.left), node_source(node.right))
    if isinstance(node, IndexPreservingProduct):
        return "%s * %s" % (node_source(node.left), node_source(node.right))
    if isinstance(node, Power):
        return "%s ^ %s" % (
            node_source(node.base), node_source(node.exponent))
    if isinstance(node, Instantiate):
        return "Instantiate( %s )" % node_source(node.var)
    if isinstance(node, Integral):
        return "Integral( %s :: %s in [ %s, %s ] )" % (
            node_source(node.body), node_source(node.var),
            node_source(node.lower), node_source(node.upper))
    if isinstance(node, Product):
        return "Product( %s, %s )" % (
            node_source(node.body), node_source(node.index))
    if isinstance(node, Root):
        return "Root( %s )" % node_source(node.body)
    if isinstance(node, MaxMin):
        return "%s( %s, %s )" % (
            node.which, node_source(node.a), node_source(node.b))
    if isinstance(node, TotalDiff):
        return "TotalDiff( %s, %s )" % (
            node_source(node.x), node_source(node.y))
    if isinstance(node, ParDiff):
        return "ParDiff( %s, %s )" % (
            node_source(node.x), node_source(node.y))
    if isinstance(node, ReduceSum):
        return "reduceSum( %s, %s )" % (
            node_source(node.body), node_source(node.index))
    if isinstance(node, UFunc):
        return "%s( %s )" % (node.name, node_source(node.arg))
    if isinstance(node, Call):
        return "%s( %s )" % (
            node_source(node.name),
            ", ".join(node_source(a) for a in node.args))
    raise ValueError("unparse: unknown node %s" % type(node).__name__)
