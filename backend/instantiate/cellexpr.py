"""Expression-valued value cells — docs/value-expression.md.

A ``promo:ValueCell`` / ``promo:ValueFill`` may carry
``promo:valueExpression`` instead of a literal ``promo:value``.  The
expression is evaluated numerically at ``plan()`` time over a
*params-only, scalar* symbol environment: emitted names of scalar
bindings that resolve to a number (constants, literal cells, earlier
expression cells).

Only the scalar fragment of the AST evaluates; with scalar operands
the product operators ``*`` / ``.`` / ``:`` all degenerate to plain
multiplication.  The language has no numeric literals — numbers enter
through named constants or parameter cells.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Set, Tuple

from backend.equation.parser import ParseError, parse
from backend.equation.syntax import (
    Add, Call, Expand, Group, IndexPreservingProduct, MaxMin, Node, Power,
    Reduce, UFunc, Var,
)


class CellExprError(Exception):
    """An expression outside the scalar-evaluable subset, or a
    numeric failure (domain error, division by zero)."""


def _sign(x: float) -> float:
    return float((x > 0) - (x < 0))


_UFUNCS: Dict[str, Callable[[float], float]] = {
    "abs": abs, "neg": lambda x: -x,
    "exp": math.exp, "ln": math.log, "log": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sqrt": math.sqrt, "inv": lambda x: 1.0 / x, "sign": _sign,
}

_PRODUCTS = (Reduce, IndexPreservingProduct, Expand)


def parse_cell(text: str) -> Node:
    """Parse a cell expression; raises ``CellExprError`` on syntax
    errors or constructs outside the scalar subset."""
    try:
        node = parse(text)
    except ParseError as e:
        raise CellExprError(e.message) from e
    symbols(node)       # validates the subset
    return node


def symbols(node: Node) -> Set[str]:
    """The free ``Var`` names of a scalar-subset expression."""
    if isinstance(node, Var):
        return {node.name}
    if isinstance(node, Group):
        return symbols(node.body)
    if isinstance(node, (Add,) + _PRODUCTS):
        return symbols(node.left) | symbols(node.right)
    if isinstance(node, Power):
        return symbols(node.base) | symbols(node.exponent)
    if isinstance(node, UFunc):
        if node.name not in _UFUNCS:
            raise CellExprError(
                "function %r is not scalar-evaluable" % node.name)
        return symbols(node.arg)
    if isinstance(node, MaxMin):
        return symbols(node.a) | symbols(node.b)
    if isinstance(node, Call):
        raise CellExprError(
            "function %r is not scalar-evaluable" % node.name.name)
    raise CellExprError(
        "%s is not allowed in a value cell" % type(node).__name__)


def evaluate(node: Node, env: Dict[str, float]) -> float:
    """Evaluate a scalar-subset expression; every symbol must be in
    ``env`` (callers check ``symbols(node) <= env`` first)."""
    try:
        return float(_eval(node, env))
    except (ArithmeticError, ValueError, TypeError) as e:
        raise CellExprError(str(e) or type(e).__name__) from e


def _eval(node: Node, env: Dict[str, float]) -> float:
    if isinstance(node, Var):
        return env[node.name]
    if isinstance(node, Group):
        return _eval(node.body, env)
    if isinstance(node, Add):
        a, b = _eval(node.left, env), _eval(node.right, env)
        return a + b if node.op == "+" else a - b
    if isinstance(node, _PRODUCTS):
        return _eval(node.left, env) * _eval(node.right, env)
    if isinstance(node, Power):
        return _eval(node.base, env) ** _eval(node.exponent, env)
    if isinstance(node, UFunc):
        return _UFUNCS[node.name](_eval(node.arg, env))
    if isinstance(node, MaxMin):
        f = max if node.which == "max" else min
        return f(_eval(node.a, env), _eval(node.b, env))
    raise CellExprError(
        "%s is not allowed in a value cell" % type(node).__name__)


def resolve(exprs: Set[str],
            env: Dict[str, float],
            provides: Dict[str, str],
            ) -> Tuple[Dict[str, float], Dict[str, Tuple[str, str]]]:
    """Fixpoint over expression strings.

    ``env`` holds the already-numeric scalar symbols; ``provides``
    maps a scalar symbol to the expression string its single cell
    carries — resolving that expression defines the symbol.  Returns
    ``(results, failures)``: expression → value, and expression →
    ``(problem kind, message)`` with kind ``bad-cell`` /
    ``unresolved-cell`` / ``cell-cycle``."""
    env = dict(env)
    results: Dict[str, float] = {}
    failures: Dict[str, Tuple[str, str]] = {}
    parsed: Dict[str, Node] = {}
    free: Dict[str, Set[str]] = {}
    for text in sorted(exprs | set(provides.values())):
        try:
            parsed[text] = parse_cell(text)
            free[text] = symbols(parsed[text])
        except CellExprError as e:
            failures[text] = ("bad-cell", "%r: %s" % (text, e))

    pending = [t for t in sorted(parsed)]
    progress = True
    while pending and progress:
        progress = False
        for text in list(pending):
            if not free[text] <= env.keys():
                continue
            pending.remove(text)
            progress = True
            try:
                results[text] = evaluate(parsed[text], env)
            except CellExprError as e:
                failures[text] = ("bad-cell", "%r: %s" % (text, e))
                continue
            for sym, src in provides.items():
                if src == text:
                    env[sym] = results[text]

    # leftovers: unknown symbols vs. a reference loop among provided
    # scalars (docs/value-expression.md).
    waiting = {sym for sym, src in provides.items() if src in pending}
    deps = {sym: free[provides[sym]] - env.keys() for sym in waiting}
    for text in pending:
        missing = free[text] - env.keys()
        unknown = sorted(missing - waiting)
        if unknown:
            failures[text] = (
                "unresolved-cell",
                "%r: unknown or non-scalar symbol(s) %s"
                % (text, ", ".join(unknown)))
            continue
        loop = _find_cycle(sorted(missing), deps)
        if loop:
            failures[text] = (
                "cell-cycle",
                "%r: cyclic cell references %s"
                % (text, " -> ".join(loop)))
        else:
            failures[text] = (
                "unresolved-cell",
                "%r: depends on unresolved symbol(s) %s"
                % (text, ", ".join(sorted(missing))))
    return results, failures


def _find_cycle(starts: List[str],
                deps: Dict[str, Set[str]]) -> Optional[List[str]]:
    """A reference loop reachable from ``starts`` in ``deps``, as the
    symbol path closing on itself; ``None`` if none."""
    done: Set[str] = set()

    def dfs(sym: str, path: List[str]) -> Optional[List[str]]:
        if sym in path:
            return path[path.index(sym):] + [sym]
        if sym in done or sym not in deps:
            return None
        for nxt in sorted(deps[sym]):
            found = dfs(nxt, path + [sym])
            if found:
                return found
        done.add(sym)
        return None

    for s in starts:
        found = dfs(s, [])
        if found:
            return found
    return None
