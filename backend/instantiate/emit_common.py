"""Shared plan-walker for the code emitters.

Each emitter renders the same ``CodePlan`` walk — incidence matrices,
function signature, state unpack, parameter binds, then per level the
port gathers, equation blocks and algebraic loops — differing only in
surface syntax.  The walk lives here once; a :class:`Dialect` supplies
the per-language lines, so a new target is one dialect class rather
than a 200-line copy of the traversal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from backend.equation.checker import check
from backend.equation.codegen import render
from backend.equation.compile_space import CompileSpace
from backend.equation.parser import parse
from backend.equation.syntax import Var

from .plan import CodePlan, PlanBlock, StateSlot


def inst_name(instance: str) -> str:
    """Fallback emitted name — the internal_id part, sanitised."""
    return re.sub(r"\W", "_", instance.split("@")[0])


def block_size(b: PlanBlock) -> int:
    """Flat size of a block's lhs — product of bound index sizes."""
    n = 1
    for els in b.lhs_indices.values():
        n *= max(1, len(els or []))
    return n


def loop_layout(blocks: List[PlanBlock]) -> Tuple[List[str], List[int]]:
    """Names + flat sizes of an algebraic loop's unknowns."""
    names = [b.lhs_name or inst_name(b.lhs_instance) for b in blocks]
    return names, [block_size(b) for b in blocks]


def bound_dims(indices: Dict[str, List[str]]) -> List[int]:
    """Bound index map → per-axis sizes (min 1) for array literals."""
    return [max(1, len(els or [])) for els in indices.values()]


@dataclass
class T0Layout:
    """The t=0 solve layout shared by the dialects.

    ``unknowns`` — (emitted name, flat size, bound index map) slices of
    the solver vector ``u``: init-covered x0 states first, then the
    algebraic (non-state, non-pin) lhs vars in schedule order, then one
    ``d<state>`` derivative slot per state.

    ``residuals`` — (block, lhs-term) pairs in order: the ``initialise``
    blocks first, then every runtime block (state lhs → its ``d`` slot,
    parameter/port lhs skipped, rhs-less blocks skipped).

    ``dx`` — the ``d<state>`` names in ``cp.states`` order; a
    steady-state solve appends them as ``der = 0`` residuals.

    ``pins`` — states whose x0 is fixed, not solved: ``cells`` (literal)
    or ``par`` (``par["ic0_<name>"]``).

    ``guesses`` — blocks whose ``SolveRoot`` body seeds the nested
    solve's ``x0`` from the outer iterate."""

    unknowns: List[Tuple[str, int, Dict[str, List[str]]]] = \
        field(default_factory=list)
    residuals: List[Tuple[PlanBlock, str]] = field(default_factory=list)
    dx: List[str] = field(default_factory=list)
    pins: List[StateSlot] = field(default_factory=list)
    guesses: List[PlanBlock] = field(default_factory=list)


def t0_layout(cp: CodePlan) -> T0Layout:
    """Compute the emitted ``initial`` solve's unknowns and residuals.

    States with value cells or an ``initialise`` pin are treated as
    pins/unknowns per ``StateSlot.ic_source``; every other bound lhs
    becomes an algebraic unknown.  The system is square-ish by
    construction — ``fsolve`` tolerates extra residuals (a supplied IC
    on an init-covered state is an over-determination the values must
    satisfy consistently)."""
    spec = T0Layout()
    state_lhs = {(s.entity_type, s.var): s for s in cp.states}
    pinned = {p.name or inst_name(p.instance)
              for p in cp.params + cp.inputs}
    pinned |= {g.name or inst_name(g.instance) for g in cp.gathers}

    seen = set()
    for st in cp.states:
        if st.ic_source != "initialise":
            spec.pins.append(st)
            continue
        nm = st.name or inst_name(st.instance)
        spec.unknowns.append((nm, st.size, st.indices))
        seen.add(nm)
    for lvl in cp.levels:
        for b in lvl:
            if not b.rhs or (b.entity_type, b.lhs) in state_lhs:
                continue
            nm = b.lhs_name or inst_name(b.lhs_instance)
            if nm in pinned or nm in seen:
                continue
            seen.add(nm)
            spec.unknowns.append((nm, block_size(b), b.lhs_indices))
            if b.guess:
                spec.guesses.append(b)
    for st in cp.states:
        nm = "d%s" % (st.name or inst_name(st.instance))
        spec.dx.append(nm)
        spec.unknowns.append((nm, st.size, st.indices))

    for b in cp.initials:
        spec.residuals.append(
            (b, b.lhs_name or inst_name(b.lhs_instance)))
    for lvl in cp.levels:
        for b in lvl:
            if not b.rhs:
                continue
            nm = b.lhs_name or inst_name(b.lhs_instance)
            st = state_lhs.get((b.entity_type, b.lhs))
            if st is not None:
                term = "d%s" % (st.name or inst_name(st.instance))
            elif nm in pinned:
                continue
            else:
                term = nm
            spec.residuals.append((b, term))
    return spec


class Dialect:
    """Per-language surface syntax for :func:`emit_plan`.

    Class attributes: ``target`` (the renderer's target name),
    ``index_base`` (0 for C-style NumPy indexing, 1 for Julia/Matlab),
    ``indent``/``comment``/``stmt_end`` dress emitted lines, and
    ``no_rhs`` is the literal emitted when a block has no RHS.
    """

    target: str = "python"
    index_base: int = 0
    indent: str = "    "
    comment: str = "#"
    stmt_end: str = ""
    no_rhs: str = "None"

    def render_rhs(self, block: PlanBlock, space: CompileSpace,
                   names: Dict[str, str]) -> str:
        """Parse → check → render one block's RHS, with the entity
        type's instance-name map as the override."""
        if not block.rhs:
            return self.no_rhs
        lhs = Var(inst_name(block.lhs_instance))
        checked = check(parse(block.rhs), space, lhs)
        return render(checked, space, self.target, lhs=lhs.name,
                      names=names)

    # -- whole-function shape -----------------------------------------

    def header(self, cp: CodePlan) -> List[str]:
        """Module prelude (imports etc.) emitted before the matrices."""
        return []

    def matrix(self, mx, space: CompileSpace) -> str:
        """One incidence-matrix literal line."""
        raise NotImplementedError

    def fn_open(self, cp: CodePlan) -> List[str]:
        """Function signature plus any prologue (``dy = zeros``)."""
        raise NotImplementedError

    def fn_close(self) -> List[str]:
        """Return statement and ``end`` equivalents."""
        raise NotImplementedError

    # -- body lines ----------------------------------------------------

    def level_comment(self, level: int) -> str:
        return "%s%s level %d" % (self.indent, self.comment, level)

    def state_unpack(self, st, space: CompileSpace) -> str:
        """Slice a state variable out of the packed state vector."""
        raise NotImplementedError

    def param(self, p, space: CompileSpace) -> str:
        """Bind a parameter — a ``par`` lookup or a value-cell literal."""
        raise NotImplementedError

    def gather(self, g, space: CompileSpace) -> str:
        """One port gather (the peer indexed by the gather map)."""
        raise NotImplementedError

    def assign(self, b: PlanBlock, rhs: str) -> List[str]:
        """A non-state block: ``name = rhs``."""
        return ["%s%s = %s%s" % (self.indent,
                                 b.lhs_name or inst_name(b.lhs_instance),
                                 rhs, self.stmt_end)]

    def state_assign(self, st, b: PlanBlock, rhs: str,
                     space: CompileSpace) -> List[str]:
        """A balance block writing into the derivative vector."""
        return ["%sdy[%d:%d] = %s%s" % (self.indent,
                                      st.offset + self.index_base,
                                      st.offset + st.size, rhs,
                                      self.stmt_end)]

    def loop(self, out: List[str], loop_id: int,
             blocks: List[PlanBlock], space: CompileSpace,
             cp: CodePlan) -> None:
        """Emit one algebraic loop (solver-specific)."""
        raise NotImplementedError

    def initial(self, out: List[str], cp: CodePlan, spec: T0Layout,
                space: CompileSpace) -> None:
        """Emit the ``initial(par, steady_state)`` t=0 solve —
        Modelica-style: pinned ICs, then one nonlinear solve over
        x0 (init-covered), the algebraic lhs vars and the ``d<state>``
        derivative slots, with every runtime + initialise block as a
        residual.  ``steady_state`` zeroes ``total_diff`` and appends
        ``der = 0`` residuals."""
        raise NotImplementedError


def emit_plan(cp: CodePlan, space: CompileSpace, d: Dialect) -> str:
    """Walk a ``CodePlan`` once, asking ``d`` for each emitted line."""
    out: List[str] = list(d.header(cp))

    for mx in cp.matrices:
        out.append(d.matrix(mx, space))
    if cp.matrices:
        out.append("")

    out.extend(d.fn_open(cp))
    for st in cp.states:
        out.append(d.state_unpack(st, space))
    for p in cp.params + cp.inputs:
        if p.kind == "constant" and p.value is not None:
            continue                      # inlined by the renderer
        out.append(d.param(p, space))

    state_lhs = {(s.entity_type, s.var): s for s in cp.states}
    emitted_gathers = set()
    for level, lvl in enumerate(cp.levels):
        out.append(d.level_comment(level))
        consumed = {v for b in lvl for v in b.inputs}
        for g in cp.gathers:
            if g.var in consumed and g.instance not in emitted_gathers:
                emitted_gathers.add(g.instance)
                out.append(d.gather(g, space))
        loops_here: Dict[int, List[PlanBlock]] = {}
        for b in lvl:
            if b.loop >= 0:
                loops_here.setdefault(b.loop, []).append(b)
                continue
            rhs = d.render_rhs(b, space, cp.names.get(b.entity_type, {}))
            st = state_lhs.get((b.entity_type, b.lhs))
            if st is not None:
                out.extend(d.state_assign(st, b, rhs, space))
            else:
                out.extend(d.assign(b, rhs))
        for loop_id, blocks in sorted(loops_here.items()):
            d.loop(out, loop_id, blocks, space, cp)
    out.extend(d.fn_close())
    if cp.states:
        d.initial(out, cp, t0_layout(cp), space)
    return "\n".join(out)
