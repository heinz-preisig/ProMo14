"""Semantic checker — walk a ``syntax.Node`` tree and infer units / indices.

The checker is a second pass after parsing. It takes a plain AST and a
``CompileSpace`` (the variable/index context from the ontology) and produces
a checked tree in which every subexpression carries:

- ``units`` — the inferred SI unit vector;
- ``indices`` — the sorted list of index IRIs the subexpression has after
  the operation;
- ``incidence`` — the set of variable IRIs referenced;
- ``label`` — a temporary variable label for codegen.

Ported from ProMo13 ``variable_framework.*Operator.__init__``. The rules are
kept; the old class hierarchy (operator as PhysicalVariable) is replaced by
a plain recursive dispatch on ``syntax.Node``.

Differences / fixes:

- No side effects: the ontology is read-only (ADR-006); ``diffSpace`` no
  longer mints indices, it looks them up and errors if missing.
- Rendering state removed: no ``language`` attribute, no ``__str__``.
- ``Product`` and ``ReduceSum`` raise ``IndexStructureError`` if the index
  is not present in the argument, instead of the old silent ``ValueError``.
- ``Root`` performs the shallow incidence check (the LHS variable must appear
  in the RHS). The old code also searched dependent equations through the
  bipartite graph; that remains a future enhancement once the full var/expr
  graph is available.
- ``Hadamard`` no longer silently discards empty-index errors — the old code
  constructed ``IndexStructureError`` without ``raise``. We keep the rule
  permissive: scalars are allowed; the result is the union of index sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional, Set

from .compile_space import CompileSpace
from .errors import IndexStructureError, UnitError, VarError
from .syntax import (
    Add, Call, Expand, Group, Hadamard, Instantiate, Integral, MaxMin, Node,
    ParDiff, Power, Product, Reduce, ReduceSum, Root, TotalDiff, UFunc, Var,
)
from .units import Units


@dataclass
class Checked:
    """A type-checked / unit-checked subexpression."""

    node: Node
    units: Units
    indices: List[str]
    label: str
    incidence: FrozenSet[str] = field(default_factory=frozenset)
    children: List["Checked"] = field(default_factory=list)

    def index_set(self) -> Set[str]:
        return set(self.indices)


def check(node: Node, space: CompileSpace, lhs: Optional[Var] = None) -> Checked:
    """Check ``node`` in ``space``. ``lhs`` is the equation's LHS variable,
    needed by ``Root``.
    """
    if isinstance(node, Var):
        resolved = space.resolve(node.name)
        var = resolved.variable
        return Checked(
            node=node,
            units=var.units,
            indices=sorted(var.index_structures),
            label=node.name,
            incidence=frozenset([var.iri]) if var.iri else frozenset(),
        )

    if isinstance(node, Group):
        inner = check(node.body, space, lhs)
        return Checked(
            node=node,
            units=inner.units,
            indices=inner.indices,
            label=space.new_temp(),
            incidence=inner.incidence,
            children=[inner],
        )

    if isinstance(node, Add):
        left = check(node.left, space, lhs)
        right = check(node.right, space, lhs)
        units = left.units + right.units  # UnitError on mismatch (old order)
        if left.indices != right.indices:
            raise IndexStructureError(
                "add incompatible index structures %s %s %s"
                % (
                    space.pretty_index_list(left.indices),
                    node.op,
                    space.pretty_index_list(right.indices),
                )
            )
        return Checked(
            node=node,
            units=units,
            indices=left.indices,
            label=space.new_temp(),
            incidence=left.incidence | right.incidence,
            children=[left, right],
        )

    if isinstance(node, Expand):
        left = check(node.left, space, lhs)
        right = check(node.right, space, lhs)
        common = left.index_set() & right.index_set()
        if common:
            raise IndexStructureError(
                "ExpandProduct -- the two operands must not have any common index"
                "\n first argument indices : %s"
                "\n second argument indices: %s"
                % (
                    space.pretty_index_list(left.indices),
                    space.pretty_index_list(right.indices),
                )
            )
        return Checked(
            node=node,
            units=left.units * right.units,
            indices=sorted(left.index_set() | right.index_set()),
            label=space.new_temp(),
            incidence=left.incidence | right.incidence,
            children=[left, right],
        )

    if isinstance(node, Hadamard):
        left = check(node.left, space, lhs)
        right = check(node.right, space, lhs)
        return Checked(
            node=node,
            units=left.units * right.units,
            indices=sorted(left.index_set() | right.index_set()),
            label=space.new_temp(),
            incidence=left.incidence | right.incidence,
            children=[left, right],
        )

    if isinstance(node, Reduce):
        left = check(node.left, space, lhs)
        right = check(node.right, space, lhs)
        common = left.index_set() & right.index_set()
        n_common = len(common)

        reduce_iri: Optional[str] = None
        if node.index:
            reduce_iri = space.get_index(node.index.name)
            if reduce_iri is None:
                raise VarError(
                    "no such index %s defined" % node.index.name
                )

        if n_common == 0:
            raise IndexStructureError(
                "ReduceProduct -- there must be exactly one common index "
                "over which one reduces"
                "\n first argument indices : %s"
                "\n second argument indices: %s"
                % (
                    space.pretty_index_list(left.indices),
                    space.pretty_index_list(right.indices),
                )
            )

        if n_common == 1:
            # Exactly one common index; reduce over it.
            reduced_iri = list(common)[0]
            result_indices = sorted(left.index_set() ^ right.index_set())
        else:
            # More than one common index — an explicit reduce index is required
            # so the rule is unambiguous.
            if reduce_iri is None:
                raise IndexStructureError(
                    "ReduceProduct -- there are more than one common index; "
                    "use an explicit reduce index"
                    "\n first argument indices : %s"
                    "\n second argument indices: %s"
                    % (
                        space.pretty_index_list(left.indices),
                        space.pretty_index_list(right.indices),
                    )
                )
            reduced_iri = reduce_iri
            result_indices = sorted(
                (left.index_set() | right.index_set()) - {reduced_iri}
            )

        return Checked(
            node=node,
            units=left.units * right.units,
            indices=result_indices,
            label=space.new_temp(),
            incidence=left.incidence | right.incidence,
            children=[left, right],
        )

    if isinstance(node, Power):
        base = check(node.base, space, lhs)
        exp = check(node.exponent, space, lhs)
        if not (base.units.is_dimensionless() and exp.units.is_dimensionless()):
            raise UnitError(
                "units of basis and exponent must be zero",
                base.units.pretty(),
                exp.units.pretty(),
            )
        return Checked(
            node=node,
            units=base.units,
            indices=base.indices,
            label=space.new_temp(),
            incidence=base.incidence | exp.incidence,
            children=[base, exp],
        )

    if isinstance(node, MaxMin):
        a = check(node.a, space, lhs)
        b = check(node.b, space, lhs)
        units = a.units + b.units  # UnitError on mismatch (old order)
        if a.indices != b.indices:
            raise IndexStructureError(
                "add incompatible index structures %s %s %s"
                % (
                    space.pretty_index_list(a.indices),
                    node.which,
                    space.pretty_index_list(b.indices),
                )
            )
        return Checked(
            node=node,
            units=units,
            indices=a.indices,
            label=space.new_temp(),
            incidence=a.incidence | b.incidence,
            children=[a, b],
        )

    if isinstance(node, UFunc):
        arg = check(node.arg, space, lhs)
        rule = space.table.ufunc_unit_rule(node.name)
        if rule is None:
            raise VarError(
                "there is no unitary function rule for : %s" % node.name
            )

        if rule == "retain":
            units = arg.units
        elif rule == "none":
            if not arg.units.is_dimensionless():
                raise UnitError(
                    "%s expression must have no units" % node.name,
                    arg.units.pretty(),
                    "-",
                )
            units = arg.units
        elif rule == "inverse":
            units = arg.units.inverse()
        elif rule == "loose":
            units = Units()
        else:
            raise VarError(
                "unknown ufunc unit rule %r for %s" % (rule, node.name)
            )

        indices = list(arg.indices)
        if node.name == "diffSpace":
            diff_label = "d%s" % arg.label
            diff_iri = space.get_index(diff_label)
            if diff_iri is None:
                raise VarError(
                    "differential index %s not declared in ontology "
                    "(diffSpace requires a pre-declared index)" % diff_label
                )
            indices = sorted(set(indices) | {diff_iri})

        return Checked(
            node=node,
            units=units,
            indices=indices,
            label=space.new_temp(),
            incidence=arg.incidence,
            children=[arg],
        )

    if isinstance(node, Instantiate):
        # ``Instantiate(expr, shape)`` — ``lhs := expr`` where ``shape``
        # supplies the units and index structure.  The left-hand side is
        # the declared variable being defined, not part of the expression.
        expr = check(node.expr, space, lhs)
        shape = check(node.shape, space, lhs)
        return Checked(
            node=node,
            units=shape.units,
            indices=shape.indices,
            label=space.new_temp(),
            incidence=expr.incidence | shape.incidence,
            children=[expr, shape],
        )

    if isinstance(node, Integral):
        y = check(node.body, space, lhs)
        x = check(node.var, space, lhs)
        xl = check(node.lower, space, lhs)
        xu = check(node.upper, space, lhs)
        if not (x.indices == xl.indices == xu.indices):
            raise IndexStructureError(
                "interval -- incompatible index structures %s != %s != %s"
                % (
                    space.pretty_index_list(x.indices),
                    space.pretty_index_list(xl.indices),
                    space.pretty_index_list(xu.indices),
                )
            )
        return Checked(
            node=node,
            units=y.units * x.units,
            indices=y.indices,
            label=space.new_temp(),
            incidence=y.incidence | x.incidence | xl.incidence | xu.incidence,
            children=[y, x, xl, xu],
        )

    if isinstance(node, Product):
        arg = check(node.body, space, lhs)
        if not arg.units.is_dimensionless():
            raise UnitError(
                "Product expression must have no units", arg.units.pretty(), "-"
            )
        index_iri = space.get_index(node.index.name)
        if index_iri is None:
            raise VarError(
                "no such index %s defined" % node.index.name
            )
        if index_iri not in arg.index_set():
            raise IndexStructureError(
                "Product -- index %s not in argument indices %s"
                % (node.index.name, space.pretty_index_list(arg.indices))
            )
        return Checked(
            node=node,
            units=arg.units,
            indices=sorted(arg.index_set() - {index_iri}),
            label=space.new_temp(),
            incidence=arg.incidence,
            children=[arg],
        )

    if isinstance(node, Root):
        if lhs is None:
            raise VarError(
                "Root requires the equation's LHS variable"
            )
        lhs_resolved = space.resolve(lhs.name)
        body = check(node.body, space, lhs)
        if lhs_resolved.variable.iri not in body.incidence:
            raise VarError(
                "root error -- no dependency on the variable to be solved for"
            )
        return Checked(
            node=node,
            units=lhs_resolved.variable.units,
            indices=lhs_resolved.variable.index_structures,
            label=space.new_temp(),
            incidence=body.incidence,
            children=[body],
        )

    if isinstance(node, TotalDiff):
        x = check(node.x, space, lhs)
        y = check(node.y, space, lhs)
        return Checked(
            node=node,
            units=x.units - y.units,
            indices=sorted(x.index_set() | y.index_set()),
            label=space.new_temp(),
            incidence=x.incidence | y.incidence,
            children=[x, y],
        )

    if isinstance(node, ParDiff):
        x = check(node.x, space, lhs)
        y = check(node.y, space, lhs)
        return Checked(
            node=node,
            units=x.units - y.units,
            indices=sorted(x.index_set() | y.index_set()),
            label=space.new_temp(),
            incidence=x.incidence | y.incidence,
            children=[x, y],
        )

    if isinstance(node, ReduceSum):
        arg = check(node.body, space, lhs)
        index_iri = space.get_index(node.index.name)
        if index_iri is None:
            raise VarError(
                "no such index %s defined" % node.index.name
            )
        return Checked(
            node=node,
            units=arg.units,
            indices=sorted(arg.index_set() - {index_iri}),
            label=space.new_temp(),
            incidence=arg.incidence,
            children=[arg],
        )

    if isinstance(node, Call):
        args = [check(a, space, lhs) for a in node.args]
        # Generic function calls have no unit rule yet. Treat as dimensionless
        # with the union of argument indices; this is provisional.
        indices: Set[str] = set()
        incidence: Set[str] = set()
        for a in args:
            indices |= a.index_set()
            incidence |= a.incidence
        return Checked(
            node=node,
            units=Units(),
            indices=sorted(indices),
            label=space.new_temp(),
            incidence=frozenset(incidence),
            children=args,
        )

    raise VarError("unknown node type: %s" % type(node).__name__)
