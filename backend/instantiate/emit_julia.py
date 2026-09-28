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
    bound_dims,
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

    @staticmethod
    def _num(v) -> str:
        """One cell value as a literal; missing cells are NaN."""
        return "NaN" if v is None else repr(v)

    @classmethod
    def _array_lit(cls, flat: List, dims: List[int]) -> str:
        """A flat C-order value table as a Julia array literal shaped
        to the bound index sizes.  Julia is column-major: an n-D table
        is reshaped to the reversed dims and permuted back so element
        order matches the C-order coordinate enumeration
        (convention: docs/value-cells.md)."""
        items = ", ".join(cls._num(v) for v in flat)
        if not dims:
            return items or "NaN"
        if len(dims) == 1:
            return "[%s]" % items
        n = len(dims)
        rev = ", ".join(str(d) for d in reversed(dims))
        perm = ", ".join(str(i) for i in range(n, 0, -1))
        return ("permutedims(reshape([%s], %s), (%s))"
                % (items, rev, perm))

    @classmethod
    def _sparse(cls, entries: List[Tuple[int, int, int]],
                rows: int, cols: int) -> str:
        """A COO entry list as a ``sparse(I, J, V, m, n)`` literal —
        indices shifted to Julia's 1-based convention."""
        ii = [str(r + 1) for r, _, _ in entries]
        jj = [str(c + 1) for _, c, _ in entries]
        vv = [str(s) for _, _, s in entries]
        return ("sparse([%s], [%s], [%s], %d, %d)"
                % (", ".join(ii), ", ".join(jj), ", ".join(vv),
                   rows, cols))

    def header(self, cp: CodePlan) -> List[str]:
        return ["using SparseArrays", ""]

    def matrix(self, mx, space: CompileSpace) -> str:
        return "%s = %s  # F over [%d x %d]" % (
            mx.name or inst_name(mx.instance),
            self._sparse(mx.entries, len(mx.rows), len(mx.cols)),
            len(mx.rows), len(mx.cols))

    def fn_open(self, cp: CodePlan) -> List[str]:
        return ["function derivative!(dy, y, par, t)"]

    def state_unpack(self, st, space: CompileSpace) -> str:
        return "    %s = @view y[%d:%d]" % (
            st.name or inst_name(st.instance),
            st.offset + 1, st.offset + st.size)

    def param(self, p, space: CompileSpace) -> str:
        nm = p.name or inst_name(p.instance)
        if p.values is not None:
            return "    %s = %s  # value cells" % (
                nm, self._array_lit(p.values, bound_dims(p.indices)))
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

    def pin_term(self, st, space: CompileSpace) -> str:
        """The IC pin expression — a cells literal or a ``par`` lookup,
        used as the residual's rhs term in a non-steady solve."""
        nm = st.name or inst_name(st.instance)
        if st.ic_source == "cells":
            return self._array_lit(st.ic_values or [],
                                   bound_dims(st.indices))
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
