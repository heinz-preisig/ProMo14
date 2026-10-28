"""Julia emitter — render a ``CodePlan`` as an in-place derivative
function for OrdinaryDiffEq (``f(du, u, p, t)``).

The walk lives in ``emit_common.emit_plan``; this file supplies only
the Julia surface syntax (the ``_Julia`` dialect):

- **1-based indexing** — state slices, gather maps and matrix COO
  entries are shifted by one;
- **sparse literals** — incidence matrices emit as
  ``sparse(I, J, V, m, n)`` (``SparseArrays``);
- **broadcast dots** — the renderer emits ``.*``/``.^``/``f.(x)``;
  the matrix·vector contraction pattern is plain ``*``;
- **parameters** read from a NamedTuple (``par.V_5``).

Generated shape::

    using SparseArrays

    V_4 = sparse([1, 2], [1, 2], [-1, 1], 2, 2)   # incidence

    function derivative!(dy, y, par, t)
        V_1 = @view y[1:2]                        # state unpack
        V_5 = par.V_5                             # parameter
        # level 0
        V_2 = <rhs>
        # level 1
        V_6 = V_2[[1, 2]]                         # port gather
        V_3 = <rhs>
        # level 2
        dy[1:2] = <rhs>                           # balance → dy
        return nothing
    end

Limitations (milestone 1): algebraic-loop blocks are emitted inline
with a marker comment, not wrapped in a solver (NonlinearSolve /
MTK tearing is the follow-up); multi-axis states are packed flat
without reshape.
"""

from __future__ import annotations

from typing import List, Tuple

from backend.equation.compile_space import CompileSpace

from .emit_common import (
    Dialect,
    T0Layout,
    data_kinds,
    emit_plan,
    inst_name,
    loop_layout,
)
from .plan import CodePlan


class _Julia(Dialect):
    """Julia surface syntax: 1-based indexing, ``@view`` state
    slices, NamedTuple params, ``sparse`` incidence literals,
    in-place ``nlsolve!`` loop residuals."""

    target = "julia"
    index_base = 1
    no_rhs = "nothing  # no rhs"


    def header(self, cp: CodePlan) -> List[str]:
        kinds = data_kinds(cp)
        out = ["using SparseArrays"]
        if kinds:
            # the shared data file — matrices + value/IC tables live
            # in model_data.json next to this file (the language-
            # neutral half of the data/code split).
            out += ["using JSON", "",
                    '_DATA = JSON.parsefile(joinpath(@__DIR__, '
                    '"model_data.json"))']
        if "matrices" in kinds:
            out += ["", "function _mx(n)",
                    "    e = _DATA[\"matrices\"][n]",
                    "    return sparse(e[\"i\"] .+ 1, e[\"j\"] .+ 1, "
                    "e[\"v\"], e[\"m\"], e[\"n\"])",
                    "end"]
        if {"values", "ics"} & kinds:
            out += ["", "function _shape(e)",
                    "    d = Int.(e[\"dims\"])",
                    "    length(d) <= 1 && return e[\"flat\"]",
                    "    # C-order flat → column-major: reshape the "
                    "    # reversed dims, permute back",
                    "    return permutedims(reshape(e[\"flat\"], "
                    "        reverse(d)...), reverse(1:length(d)))",
                    "end"]
        if "values" in kinds:
            out += ["", '_tab(n) = _shape(_DATA["values"][n])']
        if "ics" in kinds:
            out += ["", '_ictab(n) = _shape(_DATA["ics"][n])']
        out.append("")
        return out

    def matrix(self, mx, space: CompileSpace) -> str:
        nm = mx.name or inst_name(mx.instance)
        return '%s = _mx("%s")  # F over [%d x %d]' % (
            nm, nm, len(mx.rows), len(mx.cols))

    def fn_open(self, cp: CodePlan) -> List[str]:
        if cp.outputs:
            return ["function derivative!(dy, y, par, t; "
                    "outs=nothing)"]
        return ["function derivative!(dy, y, par, t)"]

    def state_unpack(self, st, space: CompileSpace) -> str:
        return "    %s = @view y[%d:%d]" % (
            st.name or inst_name(st.instance),
            st.offset + 1, st.offset + st.size)

    def param(self, p, space: CompileSpace) -> str:
        nm = p.name or inst_name(p.instance)
        if p.values is not None:
            return '    %s = _tab("%s")  # value cells' % (nm, nm)
        return "    %s = par.%s" % (nm, nm)

    def gather(self, g, space: CompileSpace) -> str:
        gn = g.name or inst_name(g.instance)
        pn = g.peer_name or inst_name(g.peer_instance)
        if g.scalar:
            return "    %s = %s[%d]  # port gather" % (gn, pn,
                                                       g.map[0] + 1)
        return "    %s = %s[%s]  # port gather" % (
            gn, pn, [i + 1 for i in g.map])

    def loop(self, out: List[str], loop_id: int, blocks, space,
             cp: CodePlan) -> None:
        """One algebraic loop as an in-place ``nlsolve`` residual
        block: ``_loopN!(r, x)`` writes ``rhs - lhs`` into ``r``
        slices, the guesses unpack 1-based."""
        names, sizes = loop_layout(blocks)
        total = sum(sizes)
        out.append("    function _loop%d!(r, x)  # algebraic loop %d"
                   % (loop_id, loop_id))
        off = 0
        for nm, sz in zip(names, sizes):
            out.append("        %s = x[%d:%d]"
                       % (nm, off + 1, off + sz))
            off += sz
        off = 0
        for b, nm, sz in zip(blocks, names, sizes):
            rhs = self.render_rhs(b, space,
                                  cp.names.get(b.entity_type, {}))
            out.append("        r[%d:%d] = (%s) .- %s"
                       % (off + 1, off + sz, rhs, nm))
            off += sz
        out.append("        return nothing")
        out.append("    end")
        out.append("    _x%d = nlsolve(_loop%d!, zeros(%d))"
                   % (loop_id, loop_id, total))
        off = 0
        for nm, sz in zip(names, sizes):
            out.append("    %s = _x%d[%d:%d]"
                       % (nm, loop_id, off + 1, off + sz))
            off += sz

    def fn_close(self) -> List[str]:
        return ["    return nothing", "end", ""]

    def output_tap(self, out, cp: CodePlan, space: CompileSpace
                   ) -> None:
        """``outs[:name] = name`` per §21 output — the optional
        ``outs`` kwarg is a side channel; the OrdinaryDiffEq call
        signature stays ``derivative!(dy, y, par, t)``."""
        out.append("    if outs !== nothing  # §21 outputs")
        for o in cp.outputs:
            nm = o.name or inst_name(o.instance)
            out.append("        outs[:%s] = %s" % (nm, nm))
        out.append("    end")

    def outputs_fn(self, out, cp: CodePlan, space: CompileSpace
                   ) -> None:
        """``outputs(y, par, t)`` — one derivative! call into a
        scratch dy, returns the recorded outputs Dict."""
        out.append("function outputs(y, par, t)")
        out.append("    outs = Dict{Symbol,Any}()")
        out.append("    derivative!(zeros(length(y)), y, par, t; "
                   "outs=outs)")
        out.append("    return outs")
        out.append("end")
        out.append("")

    def pin_term(self, st, space: CompileSpace) -> str:
        """The IC pin expression — a cells literal or a ``par`` lookup,
        used as the residual's rhs term in a non-steady solve."""
        nm = st.name or inst_name(st.instance)
        if st.ic_source == "cells":
            return '_ictab("%s")' % nm
        return "par.ic0_%s" % nm

    def initial(self, out: List[str], cp: CodePlan, spec: T0Layout,
                space: CompileSpace) -> None:
        """``initial(par; steady_state=false)`` → ``y0``: one
        out-of-place ``nlsolve`` over the states, the algebraic lhs
        vars and the ``d<state>`` slots — every runtime block
        contributes an ``rhs .- lhs`` residual.  Non-steady appends
        one pin residual per state (``initialise`` block, value-cell
        literal or ``par.ic0_<name>``); ``steady_state`` zeroes
        ``total_diff`` and swaps the pins for ``der = 0`` — the states
        are then the solved-for unknowns, keeping the system square."""
        out.append("function initial(par; steady_state=false)")
        for p in cp.params + cp.inputs:
            if p.kind == "constant" and p.value is not None:
                continue
            out.append(self.param(p, space))
        y0 = "; ".join(s.name or inst_name(s.instance)
                      for s in cp.states)
        out.append("    function _t0(u)  # t=0 residual system")
        off = 0
        for nm, sz, _idx in spec.unknowns:
            out.append("        %s = u[%d:%d]" % (nm, off + 1, off + sz))
            off += sz
        out.append("        if steady_state")
        out.append("            total_diff = (x, y) -> x .* 0  "
                   "# der = 0")
        out.append("        end")
        for g in cp.gathers:
            out.append("    " + self.gather(g, space))
        for b in spec.guesses:
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("        x0 = %s  # root! guess" % nm)
        for i, (b, term) in enumerate(spec.residuals):
            rhs = self.render_rhs(b, space,
                                  cp.names.get(b.entity_type, {}))
            out.append("        _r%d = (%s) .- %s" % (i, rhs, term))
        out.append("        _rs = Any[%s]" % ", ".join(
            "_r%d" % i for i in range(len(spec.residuals))))
        out.append("        if steady_state")
        out.append("            append!(_rs, Any[%s])  # der = 0"
                   % ", ".join(spec.dx))
        out.append("        else")
        ne = 0
        for b, term in spec.initials:
            rhs = self.render_rhs(b, space,
                                  cp.names.get(b.entity_type, {}))
            out.append("            _e%d = (%s) .- %s  # initialise"
                       % (ne, rhs, term))
            ne += 1
        for st in spec.pins:
            nm = st.name or inst_name(st.instance)
            out.append("            _e%d = (%s) .- %s  # IC pin"
                       % (ne, self.pin_term(st, space), nm))
            ne += 1
        out.append("            append!(_rs, Any[%s])" % ", ".join(
            "_e%d" % i for i in range(ne)))
        out.append("        end")
        out.append("        return isempty(_rs) ? zeros(length(u)) : "
                   "vcat(_rs...)")
        out.append("    end")
        out.append("    _u = nlsolve(_t0, zeros(%d)).zero"
                   % sum(sz for _, sz, _ in spec.unknowns))
        y_names = {s.name or inst_name(s.instance) for s in cp.states}
        off = 0
        for nm, sz, _idx in spec.unknowns:
            if nm in y_names:
                out.append("    %s = _u[%d:%d]" % (nm, off + 1,
                                                  off + sz))
            off += sz
        out.append("    return [%s]" % y0)
        out.append("end")
        out.append("")


def emit_julia(cp: CodePlan, space: CompileSpace) -> str:
    """Emit the in-place derivative function for a code plan."""
    return emit_plan(cp, space, _Julia())
