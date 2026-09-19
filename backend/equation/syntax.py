"""Plain syntax tree for the ProMo expression language.

These nodes are produced by ``parser.py`` and carry no semantic information.
Unit/index checking and variable resolution happen in a separate pass
(``compile_space.py`` / ``ast.py``) against the var/expr graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union


@dataclass(frozen=True)
class Var:
    """Identifier, optionally network-qualified: ``label`` or ``network!label``."""
    name: str


@dataclass(frozen=True)
class Group:
    """Parenthesised expression — kept so token streams round-trip exactly."""
    body: "Node"


@dataclass(frozen=True)
class Add:
    """``left + right`` or ``left - right``."""
    op: str  # '+' | '-'
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class Expand:
    """Expand product ``left : right``."""
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class Hadamard:
    """Hadamard (element-wise) product ``left . right``."""
    left: "Node"
    right: "Node"


@dataclass(frozen=True)
class Reduce:
    """Reduce product ``left * right``, optionally ``left * index right``."""
    left: "Node"
    right: "Node"
    index: Optional[Var] = None


@dataclass(frozen=True)
class Power:
    """``base ^ exponent`` — right-associative."""
    base: "Node"
    exponent: "Node"


@dataclass(frozen=True)
class Instantiate:
    """``Instantiate(proto)`` — declares the LHS variable as a new instance
    of the prototype variable ``proto``: it inherits ``proto``'s units and
    index structure but is a distinct bound-value variable (a parameter
    slot).  Only valid as the entire right-hand side of an equation —
    never nested inside another expression (ADR-008)."""
    var: Var


@dataclass(frozen=True)
class Integral:
    """``Integral(body :: var in [lower, upper])``."""
    body: "Node"
    var: Var
    lower: Var
    upper: Var


@dataclass(frozen=True)
class Product:
    """``Product(expr, index)`` — product over a running index."""
    body: "Node"
    index: Var


@dataclass(frozen=True)
class Root:
    """``Root(expr)`` — implicit equation / solve-for."""
    body: "Node"


@dataclass(frozen=True)
class MaxMin:
    """``max(a, b)`` or ``min(a, b)``."""
    which: str  # 'max' | 'min'
    a: "Node"
    b: "Node"


@dataclass(frozen=True)
class TotalDiff:
    """``TotalDiff(x, y)`` — total differential."""
    x: "Node"
    y: "Node"


@dataclass(frozen=True)
class ParDiff:
    """``ParDiff(x, y)`` — partial differential."""
    x: "Node"
    y: "Node"


@dataclass(frozen=True)
class ReduceSum:
    """``reduceSum(expr, index)`` — sum over a running index."""
    body: "Node"
    index: Var


@dataclass(frozen=True)
class UFunc:
    """Unitary function application, e.g. ``sin(x)``, ``inv(x)``."""
    name: str
    arg: "Node"


@dataclass(frozen=True)
class Call:
    """Generic function call, e.g. ``userFunc(a, b)`` or registered multi-arg functions.

    Built-in unitary functions are represented as ``UFunc`` for clarity, but
    user-defined and newly registered functions use ``Call``.
    """
    name: Var
    args: "Tuple[Node, ...]"


Node = Union[
    Var, Group, Add, Expand, Hadamard, Reduce, Power, Instantiate,
    Integral, Product, Root, MaxMin, TotalDiff, ParDiff, ReduceSum, UFunc, Call,
]
