"""Shared plan-walker for the code emitters.

Each emitter renders the same ``CodePlan`` walk — incidence matrices,
function signature, state unpack, parameter binds, then per level the
port gathers, equation blocks and algebraic loops — differing only in
surface syntax.  The walk lives here once; a :class:`Dialect` supplies
the per-language lines, so a new target is one dialect class rather
than a 200-line copy of the traversal.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from backend.equation.checker import check
from backend.equation.codegen import Renderer
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
    the solver vector ``u``: *every* state first, then the algebraic
    (non-state, non-pin) lhs vars in schedule order, then one
    ``d<state>`` derivative slot per state.  All states are unknowns
    unconditionally so the ``u`` layout is identical in both modes —
    only the residual set switches.

    ``residuals`` — (block, lhs-term) pairs for every runtime block
    (state lhs → its ``d`` slot, parameter/port lhs skipped, rhs-less
    blocks skipped); emitted in both modes.

    ``initials`` — the ``initialise`` blocks as (block, lhs-term) pairs;
    emitted only when ``not steady_state`` (steady state replaces the
    pin with ``der = 0``).

    ``dx`` — the ``d<state>`` names in ``cp.states`` order; a
    steady-state solve appends them as ``der = 0`` residuals.

    ``pins`` — states whose x0 is fixed, not solved: ``cells`` (literal)
    or ``par`` (``par["ic0_<name>"]``).  Emitted as ``pin - <state>``
    residuals when ``not steady_state``; under ``steady_state`` the pin
    is *released* — the state is solved for — which is what keeps the
    system square.

    ``guesses`` — blocks whose ``SolveRoot`` body seeds the nested
    solve's ``x0`` from the outer iterate."""

    unknowns: List[Tuple[str, int, Dict[str, List[str]]]] = \
        field(default_factory=list)
    residuals: List[Tuple[PlanBlock, str]] = field(default_factory=list)
    initials: List[Tuple[PlanBlock, str]] = field(default_factory=list)
    dx: List[str] = field(default_factory=list)
    pins: List[StateSlot] = field(default_factory=list)
    guesses: List[PlanBlock] = field(default_factory=list)


def t0_layout(cp: CodePlan) -> T0Layout:
    """Compute the emitted ``initial`` solve's unknowns and residuals.

    Every state is a ``u`` unknown; ``StateSlot.ic_source`` decides
    which residual pins it in a non-steady solve — an ``initialise``
    block, a value-cell literal or ``par["ic0_<name>"]``.  Every other
    bound lhs becomes an algebraic unknown.  Non-steady the system is
    square by construction (one pin/init residual per state, one
    runtime residual per block); ``steady_state`` drops the pin/init
    residuals and appends ``der = 0`` instead — again one per state."""
    spec = T0Layout()
    state_lhs = {(s.entity_type, s.var): s for s in cp.states}
    pinned = {p.name or inst_name(p.instance)
              for p in cp.params + cp.inputs}
    pinned |= {g.name or inst_name(g.instance) for g in cp.gathers}

    seen = set()
    for st in cp.states:
        nm = st.name or inst_name(st.instance)
        spec.unknowns.append((nm, st.size, st.indices))
        seen.add(nm)
        if st.ic_source != "initialise":
            spec.pins.append(st)
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
        spec.initials.append(
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
    #: Emitted identifiers bound to scipy.sparse literals — set by
    #: :func:`emit_plan` from ``cp.matrices``; the renderer uses it
    #: to pick sparse-safe op forms (python only).
    sparse_names = frozenset()
    #: §22 call-style: emit same-occurrence block runs as helper
    #: functions + call sites.
    occ_fns = False
    #: Matlab: local functions must follow the main function, so
    #: extracted helpers splice after the body instead of before it.
    occ_fns_at_end = False

    def render_rhs(self, block: PlanBlock, space: CompileSpace,
                   names: Dict[str, str]) -> str:
        """Parse → check → render one block's RHS, with the entity
        type's instance-name map as the override."""
        if not block.rhs:
            return self.no_rhs
        lhs = Var(inst_name(block.lhs_instance))
        checked = check(parse(block.rhs), space, lhs)
        rnd = Renderer(space, self.target, lhs=lhs.name,
                       names=names, sparse=self.sparse_names)
        src = rnd.render(checked)
        if rnd._is_sparse(checked):
            # A local bound to a sparse result is itself sparse —
            # downstream blocks may need the sparse-safe op forms.
            self.sparse_names = self.sparse_names | {
                block.lhs_name or inst_name(block.lhs_instance)}
        return src

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

    def occ_comment(self, label: str) -> str:
        """§22 call-style grouping marker — labels the contiguous run
        of blocks belonging to one referenced occurrence (or the
        host's own content) in the emitted source."""
        return "%s%s --- %s ---" % (self.indent, self.comment, label)

    def occ_fn_open(self, name: str, params: List[str],
                    returns: List[str]) -> List[str]:
        """Header lines of an extracted occurrence helper function.
        ``returns`` is needed up front for signature-style languages
        (Matlab ``function [a, b] = f(x)``)."""
        raise NotImplementedError

    def occ_fn_close(self, returns: List[str]) -> List[str]:
        """Return line of an occurrence helper (its produced locals)."""
        raise NotImplementedError

    def occ_fn_call(self, name: str, args: List[str],
                    returns: List[str]) -> str:
        """The call site inside the main function — binds the
        helper's produced locals."""
        raise NotImplementedError

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

    def output_tap(self, out: List[str], cp: CodePlan,
                   space: CompileSpace) -> None:
        """In-body lines recording each §21 ``cp.outputs`` slot into
        the dialect's observation channel — emitted just before the
        function's ``return``, so every local is already bound.
        No-op when the dialect exposes outputs differently (e.g. a
        second return value initialised in ``fn_open``)."""

    def outputs_fn(self, out: List[str], cp: CodePlan,
                   space: CompileSpace) -> None:
        """Optional observation wrapper after ``fn_close`` — calls
        the derivative once with the channel open and returns the
        recorded outputs (``outputs(t, y, par)``)."""
        return

    def footer(self, out: List[str], cp: CodePlan,
               space: CompileSpace) -> None:
        """Anything appended after the emitted functions — e.g. helper
        functions the rendered expressions reference."""
        return

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
    d.sparse_names = {mx.name or inst_name(mx.instance)
                      for mx in cp.matrices}

    for mx in cp.matrices:
        out.append(d.matrix(mx, space))
    if cp.matrices:
        out.append("")

    # §22: the referenced-model registry the plan was built from —
    # per-occurrence segment markers inside the body refer to these.
    for occ in cp.occurrences:
        frag = occ.get("comp", "").rsplit("/", 1)[-1] or occ["path"]
        out.append("%s occurrence %s -> %s" % (
            d.comment, frag, occ.get("refersTo") or occ["path"]))
    if cp.occurrences:
        out.append("")

    # main function prologue goes into ``body`` — extracted
    # occurrence helpers splice between the registry and the def.
    body: List[str] = list(d.fn_open(cp))
    for st in cp.states:
        body.append(d.state_unpack(st, space))
    for p in cp.params + cp.inputs:
        if p.kind == "constant" and p.value is not None:
            continue                      # inlined by the renderer
        body.append(d.param(p, space))

    state_lhs = {(s.entity_type, s.var): s for s in cp.states}
    emitted_gathers = set()

    # §22 call-style markers: contiguous block runs labelled by the
    # occurrence that owns them — the artefact boundary shows up in
    # the emitted source without constraining the global schedule.
    occ_label = {"": "host model"}
    for occ in cp.occurrences:
        frag = occ.get("comp", "").rsplit("/", 1)[-1] or occ["path"]
        occ_label[occ["path"]] = "occurrence %s (%s)" % (
            frag, occ.get("refersTo") or occ["path"])
    occ_paths = set(occ_label) - {""}
    current_occ: Any = None    # sentinel: no segment labelled yet
    occ_fns: List[str] = []    # extracted helpers, spliced pre-main

    # var IRI → emitted local name, so an occurrence helper's
    # signature can name the locals it consumes.
    var_name: Dict[str, str] = {}
    for slot in list(cp.params) + list(cp.inputs) + list(cp.gathers):
        var_name[slot.var] = slot.name or inst_name(slot.instance)
    for st in cp.states:
        var_name[st.var] = st.name or inst_name(st.instance)
    for lvl_ in cp.levels:
        for b_ in lvl_:
            var_name[b_.lhs] = b_.lhs_name or inst_name(b_.lhs_instance)

    def _name_of(b: PlanBlock, var: str) -> str:
        return (var_name.get(var)
                or cp.names.get(b.entity_type, {}).get(var)
                or inst_name(var))

    def _mark(path: str) -> None:
        nonlocal current_occ
        if path != current_occ:
            current_occ = path
            body.append(d.occ_comment(occ_label.get(path, path)))

    def _extract(level: int, occ: str,
                 members: List[PlanBlock]) -> None:
        """Lift one occurrence's same-level blocks into a helper
        function; emits the def into ``occ_fns`` and the call into
        ``body``.  Same-level blocks are mutually independent, so
        the call's placement within the level is free."""
        frag = re.sub(r"\W", "_",
                      occ.rsplit("/Composite_", 1)[-1] or occ)
        fn = "_occ_%s_L%d" % (frag, level)
        defined = [b.lhs_name or inst_name(b.lhs_instance)
                   for b in members]
        ext: List[str] = []
        for b in members:
            for v in b.inputs:
                nm = _name_of(b, v)
                if nm not in defined and nm not in ext:
                    ext.append(nm)
        occ_fns.append(d.comment + " " + occ_label.get(occ, occ))
        occ_fns.extend(d.occ_fn_open(fn, ext, defined))
        for b in members:
            rhs = d.render_rhs(b, space, cp.names.get(b.entity_type, {}))
            occ_fns.extend(d.assign(b, rhs))
        occ_fns.extend(d.occ_fn_close(defined))
        occ_fns.append("")
        _mark(occ)
        body.append(d.occ_fn_call(fn, ext, defined))

    extractable = d.occ_fns and bool(occ_paths)
    for level, lvl in enumerate(cp.levels):
        body.append(d.level_comment(level))
        consumed = {v for b in lvl for v in b.inputs}
        for g in cp.gathers:
            if g.var in consumed and g.instance not in emitted_gathers:
                emitted_gathers.add(g.instance)
                body.append(d.gather(g, space))
        loops_here: Dict[int, List[PlanBlock]] = {}
        groups: Dict[str, List[PlanBlock]] = {}
        for b in lvl:
            if b.loop >= 0:
                loops_here.setdefault(b.loop, []).append(b)
                continue
            # loop-free non-state blocks of a referenced occurrence
            # lift into a helper function; state/loop blocks stay
            # inline (dy writes and global solves are not cones).
            if (extractable and b.occurrence
                    and (b.entity_type, b.lhs) not in state_lhs):
                groups.setdefault(b.occurrence, []).append(b)
                continue
            if occ_paths:
                _mark(b.occurrence)
            rhs = d.render_rhs(b, space, cp.names.get(b.entity_type, {}))
            st = state_lhs.get((b.entity_type, b.lhs))
            if st is not None:
                body.extend(d.state_assign(st, b, rhs, space))
            else:
                body.extend(d.assign(b, rhs))
        for occ, members in groups.items():
            _extract(level, occ, members)
        for loop_id, blocks in sorted(loops_here.items()):
            if occ_paths:
                span = sorted({b.occurrence for b in blocks})
                if len(span) == 1:
                    _mark(span[0])
                else:
                    body.append(d.occ_comment(
                        "coupling loop across " + " + ".join(
                            occ_label.get(p, p) for p in span)))
                    current_occ = None
            d.loop(body, loop_id, blocks, space, cp)
    if cp.outputs:
        d.output_tap(body, cp, space)
    body.extend(d.fn_close())
    if d.occ_fns_at_end:
        out.extend(body)
        out.extend(occ_fns)
    else:
        out.extend(occ_fns)
        out.extend(body)
    if cp.outputs:
        d.outputs_fn(out, cp, space)
    if cp.states:
        d.initial(out, cp, t0_layout(cp), space)
    d.footer(out, cp, space)
    return "\n".join(out)


def data_kinds(cp: CodePlan) -> set:
    """Which ``model_data.json`` sections are populated — dialects
    emit only the matching loader helpers."""
    kinds = set()
    if cp.matrices:
        kinds.add("matrices")
    if any(p.values is not None for p in cp.params + cp.inputs):
        kinds.add("values")
    if any(s.ic_source == "cells" and s.ic_values is not None
           for s in cp.states):
        kinds.add("ics")
    return kinds


def emit_data(cp: CodePlan, space: CompileSpace) -> str:
    """The shared ``model_data.json`` — the language-neutral half of
    the data/code split: incidence matrices plus the value and IC
    tables, keyed by the emitted identifiers the generated code
    references (``_mx``/``_tab``/``_ictab``)."""
    out: Dict[str, Any] = {"matrices": {}, "values": {}, "ics": {}}
    for mx in cp.matrices:
        nm = mx.name or inst_name(mx.instance)
        out["matrices"][nm] = {"m": len(mx.rows), "n": len(mx.cols),
                               "i": [r for r, _, _ in mx.entries],
                               "j": [c for _, c, _ in mx.entries],
                               "v": [s for _, _, s in mx.entries]}
    for p in cp.params + cp.inputs:
        if p.values is None:
            continue
        nm = p.name or inst_name(p.instance)
        out["values"][nm] = {"flat": p.values,
                             "dims": bound_dims(p.indices)}
    for st in cp.states:
        if st.ic_source != "cells" or st.ic_values is None:
            continue
        nm = st.name or inst_name(st.instance)
        out["ics"][nm] = {"flat": st.ic_values,
                          "dims": bound_dims(st.indices)}
    return json.dumps(out, indent=1)
