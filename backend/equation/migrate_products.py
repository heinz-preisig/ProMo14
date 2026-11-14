"""§40 product-operator migration — legacy ``.``/``*`` → new spelling.

Pre-§40 the language had three product infixes:

- ``a : b``   expand (outer) product — unchanged,
- ``a . b``   index-preserving (elementwise) product — now spelt ``*``,
- ``a * b``   reduce product — contracted the single shared index.

Under §40 ``*`` is THE product (elementwise over shared indices,
ordered union otherwise) and every contraction is an explicit
``reduceSum(expr, index)`` — the summed index is *named*, not inferred
from operand shapes.

Two rewrites:

- **Canonical trees** (``promo:rhsExpression``): ``ReduceProduct(a,b)``
  becomes ``SumOverIndex(IndexPreservingProduct(a,b), i)`` where ``i``
  is the intersection of the operand index sets — recomputed
  bottom-up; the tree is semantic so the index lands as an
  ``IndexReference``, no surface-name guessing.
- **Literals** (``promo:rhs`` with no canonical tree): re-parsed under
  a *legacy* symbol table (``.``→IPP, ``*``→``_LegacyReduce``),
  transformed, and re-printed with :func:`unparse.node_source` — the
  printed text is already in §40 spelling.

An equation whose ``a * b`` operands do not share exactly one index
was never checkable; it is reported as an anomaly and left untouched
rather than silently re-interpreted as elementwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional, Set, Tuple

from .canonical import (
    ADD, DEFINITE_INTEGRAL, EXPAND_PRODUCT, INDEX_PRESERVING_PRODUCT,
    INSTANTIATE, PARTIAL_DERIVATIVE, POWER, PRODUCT_OVER_INDEX,
    SOLVE_ROOT, SUBTRACT, SUM_OVER_INDEX, TOTAL_DERIVATIVE, Argument,
    Expression, IndexReference, VariableReference,
)
from .compile_space import CompileSpace
from .errors import VarError
from .parser import Parser, ParseError, _tokenize
from .symbols import DEFAULT_TABLE, InfixEntry, SymbolTable
from .syntax import (
    Add, Call, Expand, Group, IndexPreservingProduct, Instantiate, Integral,
    MaxMin, Node, ParDiff, Power, Product, Root, ReduceSum, TotalDiff, UFunc,
    Var,
)
from .unparse import node_source


class MigrationAnomaly(Exception):
    """A stored expression that cannot be mapped mechanically."""


@dataclass(frozen=True)
class _LegacyReduce:
    """Pre-§40 ``left * right`` — migration-only parse node."""
    left: Node
    right: Node


LEGACY_TABLE = SymbolTable(
    keywords=set(DEFAULT_TABLE.keywords),
    ufuncs=set(DEFAULT_TABLE.ufuncs),
    maxmin=set(DEFAULT_TABLE.maxmin),
    functions=set(DEFAULT_TABLE.functions),
    ufunc_units=dict(DEFAULT_TABLE.ufunc_units),
    infix={
        "+": InfixEntry("+", 1, False, "add"),
        "-": InfixEntry("-", 1, False, "add"),
        ":": InfixEntry(":", 2, False, "expand"),
        ".": InfixEntry(".", 2, False, "index_preserving_product"),
        "*": InfixEntry("*", 2, False, "reduce"),
        "^": InfixEntry("^", 3, True, "power"),
    },
)


class _LegacyParser(Parser):
    """``*`` still parses to the legacy reduce node."""

    def _make_infix(self, info, left: Node, right: Node) -> Node:
        if info.factory == "reduce":
            return _LegacyReduce(left, right)  # type: ignore[return-value]
        return super()._make_infix(info, left, right)


def _legacy_parse(text: str) -> Node:
    return _LegacyParser(_tokenize(text, LEGACY_TABLE), LEGACY_TABLE).parse()


# ---------------------------------------------------------------------------
# Index-set evaluation — mirrors checker index semantics, set-valued only.
# ---------------------------------------------------------------------------

def _var_indices(name: str, space: CompileSpace) -> Optional[Set[str]]:
    try:
        return set(space.resolve(name).variable.index_structures)
    except VarError:
        return None


def _node_indices(node: Node, space: CompileSpace) -> Optional[Set[str]]:
    """Index set of a (legacy-)syntax subtree; ``None`` when unknowable."""
    if isinstance(node, Var):
        return _var_indices(node.name, space)
    if isinstance(node, Group):
        return _node_indices(node.body, space)
    if isinstance(node, Add):
        return _node_indices(node.left, space) or _node_indices(
            node.right, space)
    if isinstance(node, (Expand, IndexPreservingProduct)):
        l, r = _node_indices(node.left, space), _node_indices(
            node.right, space)
        return l | r if l is not None and r is not None else None
    if isinstance(node, _LegacyReduce):
        l, r = _node_indices(node.left, space), _node_indices(
            node.right, space)
        return (l | r) - (l & r) if l is not None and r is not None else None
    if isinstance(node, Power):
        return _node_indices(node.base, space)
    if isinstance(node, UFunc):
        return _node_indices(node.arg, space)
    if isinstance(node, (ParDiff, TotalDiff, MaxMin)):
        a = _node_indices(
            node.x if isinstance(node, (ParDiff, TotalDiff)) else node.a,
            space)
        b = _node_indices(
            node.y if isinstance(node, (ParDiff, TotalDiff)) else node.b,
            space)
        return a | b if a is not None and b is not None else a or b
    if isinstance(node, (ReduceSum, Product)):
        body = _node_indices(node.body, space)
        iri = space.get_index(node.index.name)
        if body is not None and iri is not None:
            return body - {iri}
        return body
    if isinstance(node, Integral):
        return _node_indices(node.body, space)
    if isinstance(node, Root):
        return _node_indices(node.body, space)
    if isinstance(node, Instantiate):
        return _var_indices(node.var.name, space)
    if isinstance(node, Call):
        out: Set[str] = set()
        for a in node.args:
            s = _node_indices(a, space)
            if s is None:
                return None
            out |= s
        return out
    return None


# ---------------------------------------------------------------------------
# Literal path — parse under the legacy table, transform, re-print.
# ---------------------------------------------------------------------------

def rewrite_literal(text: str, space: CompileSpace) -> Tuple[str, bool]:
    """Rewrite a stored ``promo:rhs`` literal to §40 spelling.

    Returns ``(new_text, changed)``.  Raises ``ParseError`` for text the
    legacy grammar cannot read and ``MigrationAnomaly`` for a reduce
    product whose operands do not share exactly one index.
    """
    tokens = _tokenize(text, LEGACY_TABLE)
    # Only literals that actually contain a product operator get a
    # rewrite — anything else keeps its stored surface form verbatim
    # (no whitespace/grouping normalisation churn).
    if not any(t.kind == "op" and t.value in (".", "*") for t in tokens):
        return text, False
    node = _LegacyParser(tokens, LEGACY_TABLE).parse()
    transformed, changed = _transform(node, space)
    new_text = node_source(transformed)
    # ``.``→``*`` spelling changes leave ``changed`` False even though
    # the rendered text differs — the flag tracks reductions only.
    return new_text, changed or new_text != text


def _transform(
    node: Node,
    space: CompileSpace,
    reduced: FrozenSet = frozenset(),
) -> Tuple[Node, bool]:
    """Rewrite a legacy-syntax tree.

    ``reduced`` carries the index IRIs bound by enclosing
    ``reduceSum``/``Product`` nodes: old data never placed a ``*``
    contraction inside an aggregator, so a ``_LegacyReduce`` whose
    single shared index is already bound can only come from
    already-migrated text — it stays an index-preserving product and
    the rewrite remains idempotent across loads.
    """
    if isinstance(node, _LegacyReduce):
        left, lc = _transform(node.left, space, reduced)
        right, rc = _transform(node.right, space, reduced)
        l_idx, r_idx = _node_indices(left, space), _node_indices(
            right, space)
        shared = (
            l_idx & r_idx
            if l_idx is not None and r_idx is not None else None)
        if shared is not None and len(shared) == 1 and (
                shared <= reduced):
            # already-migrated ``reduceSum( ( a * b ), i )`` text
            return IndexPreservingProduct(left, right), lc or rc
        if not shared or len(shared) != 1:
            raise MigrationAnomaly(
                "legacy `a * b` operands share %s indices — cannot "
                "determine the contracted index" % (
                    "unknown" if shared is None else len(shared)))
        reduced_iri = next(iter(shared))
        return ReduceSum(
            Group(IndexPreservingProduct(left, right)),
            Var(space.index_alias(reduced_iri)),
        ), True

    # Structural recursion — every case returns (new_node, changed).
    if isinstance(node, Group):
        b, c = _transform(node.body, space, reduced)
        return (Group(b), c)
    if isinstance(node, Add):
        l, lc = _transform(node.left, space, reduced)
        r, rc = _transform(node.right, space, reduced)
        return (Add(node.op, l, r), lc or rc)
    if isinstance(node, Expand):
        l, lc = _transform(node.left, space, reduced)
        r, rc = _transform(node.right, space, reduced)
        return (Expand(l, r), lc or rc)
    if isinstance(node, IndexPreservingProduct):
        l, lc = _transform(node.left, space, reduced)
        r, rc = _transform(node.right, space, reduced)
        return (IndexPreservingProduct(l, r), lc or rc)
    if isinstance(node, Power):
        b, bc = _transform(node.base, space, reduced)
        e, ec = _transform(node.exponent, space, reduced)
        return (Power(b, e), bc or ec)
    if isinstance(node, Integral):
        b, c = _transform(node.body, space, reduced)
        return (Integral(b, node.var, node.lower, node.upper), c)
    if isinstance(node, (Product, ReduceSum)):
        inner = reduced
        try:
            iri = space.get_index(node.index.name)
            inner = reduced | {iri}
        except VarError:
            pass
        b, c = _transform(node.body, space, inner)
        cls = type(node)
        return (cls(b, node.index), c)
    if isinstance(node, Root):
        b, c = _transform(node.body, space, reduced)
        return (Root(b), c)
    if isinstance(node, MaxMin):
        a, ac = _transform(node.a, space, reduced)
        b, bc = _transform(node.b, space, reduced)
        return (MaxMin(node.which, a, b), ac or bc)
    if isinstance(node, (ParDiff, TotalDiff)):
        x, xc = _transform(node.x, space, reduced)
        y, yc = _transform(node.y, space, reduced)
        cls = type(node)
        return (cls(x, y), xc or yc)
    if isinstance(node, UFunc):
        a, c = _transform(node.arg, space, reduced)
        return (UFunc(node.name, a), c)
    if isinstance(node, Call):
        args, changed = [], False
        for a in node.args:
            t, c = _transform(a, space, reduced)
            args.append(t)
            changed = changed or c
        return (Call(node.name, tuple(args)), changed)
    # Var, Instantiate — nothing to rewrite inside.
    return node, False


# ---------------------------------------------------------------------------
# Canonical path — semantic-tree rewrite of stored rhsExpression.
# ---------------------------------------------------------------------------

def _arg_indices(arg: Argument, space: CompileSpace) -> Optional[Set[str]]:
    """Index set of a canonical argument; ``None`` when unknowable."""
    if isinstance(arg, VariableReference):
        var = space.variables.get(arg.iri)
        return set(var.index_structures) if var is not None else None
    if isinstance(arg, IndexReference):
        return None
    op = arg.operation_iri
    if op in (ADD, SUBTRACT):
        return _arg_indices(arg.arguments[0], space) or _arg_indices(
            arg.arguments[1], space)
    if op == POWER:
        return _arg_indices(arg.arguments[0], space)
    if op in (EXPAND_PRODUCT, INDEX_PRESERVING_PRODUCT):
        l = _arg_indices(arg.arguments[0], space)
        r = _arg_indices(arg.arguments[1], space)
        return l | r if l is not None and r is not None else None
    if op in (SUM_OVER_INDEX, PRODUCT_OVER_INDEX):
        body = _arg_indices(arg.arguments[0], space)
        idx = arg.arguments[1]
        if body is not None and isinstance(idx, IndexReference):
            return body - {idx.iri}
        return body
    if op == DEFINITE_INTEGRAL:
        return _arg_indices(arg.arguments[0], space)
    if op in (TOTAL_DERIVATIVE, PARTIAL_DERIVATIVE):
        l = _arg_indices(arg.arguments[0], space)
        r = _arg_indices(arg.arguments[1], space)
        return l | r if l is not None and r is not None else l or r
    if op == SOLVE_ROOT:
        return _arg_indices(arg.arguments[0], space)
    if op == INSTANTIATE:
        return _arg_indices(arg.arguments[0], space)
    # Named ufunc/maxmin — index-preserving on the argument(s).
    l = _arg_indices(arg.arguments[0], space)
    for extra in arg.arguments[1:]:
        r = _arg_indices(extra, space)
        l = l | r if l is not None and r is not None else l or r
    return l


def rewrite_canonical(
    arg: Argument, space: CompileSpace
) -> Tuple[Argument, bool]:
    """Rewrite ``ReduceProduct`` operations inside a canonical tree.

    ``ReduceProduct(a,b)`` becomes
    ``SumOverIndex(IndexPreservingProduct(a,b), shared)``; raises
    ``MigrationAnomaly`` when the operand index sets do not intersect
    in exactly one index.  Returns ``(new_argument, changed)``.
    """
    if isinstance(arg, (VariableReference, IndexReference)):
        return arg, False
    op = arg.operation_iri
    if op == _legacy_reduce_iri():
        left, lc = rewrite_canonical(arg.arguments[0], space)
        right, rc = rewrite_canonical(arg.arguments[1], space)
        l_idx = _arg_indices(left, space)
        r_idx = _arg_indices(right, space)
        shared = (
            l_idx & r_idx
            if l_idx is not None and r_idx is not None else None)
        if not shared or len(shared) != 1:
            raise MigrationAnomaly(
                "stored ReduceProduct operands share %s indices — "
                "cannot determine the contracted index" % (
                    "unknown" if shared is None else len(shared)))
        return Expression(
            SUM_OVER_INDEX,
            (Expression(
                INDEX_PRESERVING_PRODUCT, (left, right)),
                IndexReference(next(iter(shared)))),
        ), True
    args, changed = [], False
    for a in arg.arguments:
        t, c = rewrite_canonical(a, space)
        args.append(t)
        changed = changed or c
    return (Expression(op, tuple(args)) if changed else arg), changed


def _legacy_reduce_iri() -> str:
    """The retired ``promolg:ReduceProduct`` operation IRI — kept as a
    migration predicate only, no longer a canonical operation."""
    from backend.core.vocab import PROMOLG
    return str(PROMOLG["ReduceProduct"])
