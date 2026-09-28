"""NumPy emitter — render a ``CodePlan`` as a Python derivative
function.

The walk lives in ``emit_common.emit_plan``; this file supplies only
the NumPy surface syntax (the ``_Python`` dialect).

Generated shape::

    import numpy as np

    V_4 = np.array([...])            # incidence literals

    def derivative(t, y, par):
        V_1 = y[0:2]                 # state unpack
        V_5 = par["V_5"]             # parameter / external input
        # level 0
        V_2 = <rhs>
        # level 1
        V_6 = V_2[[0, 1]]            # port gather
        V_3 = <rhs>
        # level 2
        dy[0:2] = <rhs>              # balance → derivative slice
        return dy

Algebraic loops (scheduler SCCs) emit as ``fsolve`` residual
blocks: the loop's lhs vars are the unknowns, packed into a flat
guess vector, each residual is ``rhs - lhs``.

Limitations (milestone 1): multi-axis states are packed flat
without reshape; loop initial guesses are zeros.
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


class _Python(Dialect):
    """NumPy surface syntax: 0-based slicing, ``par["X"]`` lookups,
    dense ``np.array`` incidence literals, ``fsolve`` loop residuals."""

    target = "python"
    no_rhs = "None  # no rhs"

    @staticmethod
    def _num(v) -> str:
        """One cell value as a literal; missing cells are NaN."""
        return "np.nan" if v is None else repr(v)

    @classmethod
    def _array_lit(cls, flat: List, dims: List[int]) -> str:
        """A flat C-order value table as an ``np.array`` literal shaped
        to the bound index sizes — the ν channel's codegen form."""
        items = ", ".join(cls._num(v) for v in flat)
        if not dims:
            return items or "np.nan"
        arr = "np.array([%s])" % items
        if len(dims) > 1:
            arr += ".reshape((%s))" % ", ".join(str(d) for d in dims)
        return arr

    @staticmethod
    def _dense(rows: int, cols: int,
               entries: List[Tuple[int, int, int]]) -> str:
        """A COO entry list as a dense ``np.array`` literal."""
        m = [[0] * cols for _ in range(rows)]
        for r, c, s in entries:
            m[r][c] = s
        return "np.array([%s])" % ", ".join(str(r) for r in m)

    def header(self, cp: CodePlan) -> List[str]:
        out = ["import numpy as np"]
        if cp.loops or cp.states:
            # fsolve: algebraic loops + the t=0 solve; the module import
            # backs ``scipy.optimize.fsolve`` inside root!() bodies.
            out.append("import scipy.optimize")
            out.append("from scipy.optimize import fsolve")
        out.append("")
        return out

    def matrix(self, mx, space: CompileSpace) -> str:
        return "%s = %s  # F over [%d x %d]" % (
            mx.name or inst_name(mx.instance),
            self._dense(len(mx.rows), len(mx.cols), mx.entries),
            len(mx.rows), len(mx.cols))

    def fn_open(self, cp: CodePlan) -> List[str]:
        total = sum(s.size for s in cp.states)
        return ["def derivative(t, y, par):",
                "    dy = np.zeros(%d)" % total]

    def state_unpack(self, st, space: CompileSpace) -> str:
        return "    %s = y[%d:%d]" % (
            st.name or inst_name(st.instance), st.offset,
            st.offset + st.size)

    def param(self, p, space: CompileSpace) -> str:
        nm = p.name or inst_name(p.instance)
        if p.values is not None:
            return "    %s = %s  # value cells" % (
                nm, self._array_lit(p.values, bound_dims(p.indices)))
        return '    %s = par["%s"]' % (nm, nm)

    def gather(self, g, space: CompileSpace) -> str:
        gn = g.name or inst_name(g.instance)
        pn = g.peer_name or inst_name(g.peer_instance)
        if g.scalar:
            return "    %s = %s[%d]  # port gather" % (gn, pn, g.map[0])
        return "    %s = %s[%s]  # port gather" % (gn, pn, g.map)

    def loop(self, out: List[str], loop_id: int, blocks, space,
             cp: CodePlan) -> None:
        """One algebraic loop as an ``fsolve`` residual block: the
        loop's lhs vars are the unknowns (packed flat), each residual
        is ``rhs - lhs`` evaluated with the guesses bound."""
        names, sizes = loop_layout(blocks)
        total = sum(sizes)
        out.append("    def _loop%d(x):  # algebraic loop %d"
                   % (loop_id, loop_id))
        off = 0
        for nm, sz in zip(names, sizes):
            out.append("        %s = x[%d:%d]" % (nm, off, off + sz))
            off += sz
        for b, nm in zip(blocks, names):
            rhs = self.render_rhs(b, space,
                                  cp.names.get(b.entity_type, {}))
            out.append("        _r_%s = (%s) - %s" % (nm, rhs, nm))
        out.append("        return np.concatenate([%s])"
                   % ", ".join("np.atleast_1d(_r_%s)" % nm
                               for nm in names))
        out.append("    _x%d = fsolve(_loop%d, np.zeros(%d))"
                   % (loop_id, loop_id, total))
        off = 0
        for nm, sz in zip(names, sizes):
            out.append("    %s = _x%d[%d:%d]"
                       % (nm, loop_id, off, off + sz))
            off += sz

    def fn_close(self) -> List[str]:
        return ["    return dy", ""]

    def pin_term(self, st, space: CompileSpace) -> str:
        """The IC pin expression — a cells literal or a ``par`` lookup,
        used as the residual's rhs term in a non-steady solve."""
        nm = st.name or inst_name(st.instance)
        if st.ic_source == "cells":
            return self._array_lit(st.ic_values or [],
                                   bound_dims(st.indices))
        return 'par["ic0_%s"]' % nm

    def initial(self, out: List[str], cp: CodePlan, spec: T0Layout,
                space: CompileSpace) -> None:
        """``initial(par, steady_state=False)`` → ``y0``: one ``fsolve``
        whose unknowns are the states, the algebraic lhs vars and the
        ``d<state>`` slots — every runtime block contributes an
        ``rhs - lhs`` residual.  Non-steady appends one pin residual
        per state (``initialise`` block, value-cell literal or
        ``par["ic0_<name>"]``); ``steady_state`` zeroes ``total_diff``
        and swaps the pins for ``der = 0`` — the states are then the
        solved-for unknowns, which keeps the system square."""
        out.append("def initial(par, steady_state=False):")
        for p in cp.params + cp.inputs:
            if p.kind == "constant" and p.value is not None:
                continue
            out.append(self.param(p, space))
        y0 = "np.concatenate([%s])" % ", ".join(
            "np.atleast_1d(%s)" % (s.name or inst_name(s.instance))
            for s in cp.states)
        out.append("    def _t0(u):  # t=0 residual system")
        off = 0
        for nm, sz, _idx in spec.unknowns:
            out.append("        %s = u[%d:%d]" % (nm, off, off + sz))
            off += sz
        out.append("        if steady_state:")
        out.append("            total_diff = lambda x, y: "
                   "np.zeros_like(x)  # der = 0")
        for g in cp.gathers:
            out.append("    " + self.gather(g, space))
        for b in spec.guesses:
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("        x0 = np.atleast_1d(%s)  # root! guess"
                       % nm)
        for i, (b, term) in enumerate(spec.residuals):
            rhs = self.render_rhs(b, space,
                                  cp.names.get(b.entity_type, {}))
            out.append("        _r%d = (%s) - %s" % (i, rhs, term))
        out.append("        _rs = [%s]" % ", ".join(
            "np.atleast_1d(_r%d)" % i
            for i in range(len(spec.residuals))))
        out.append("        if steady_state:")
        out.append("            _rs += [%s]  # der = 0" % ", ".join(
            "np.atleast_1d(%s)" % n for n in spec.dx))
        out.append("        else:")
        ne = 0
        for b, term in spec.initials:
            rhs = self.render_rhs(b, space,
                                  cp.names.get(b.entity_type, {}))
            out.append("            _e%d = (%s) - %s  # initialise"
                       % (ne, rhs, term))
            ne += 1
        for st in spec.pins:
            nm = st.name or inst_name(st.instance)
            out.append("            _e%d = (%s) - %s  # IC pin"
                       % (ne, self.pin_term(st, space), nm))
            ne += 1
        out.append("            _rs += [%s]" % ", ".join(
            "np.atleast_1d(_e%d)" % i for i in range(ne)))
        out.append("        return np.concatenate(_rs) "
                   "if _rs else np.zeros_like(u)")
        out.append("    _u = fsolve(_t0, np.zeros(%d))"
                   % sum(sz for _, sz, _ in spec.unknowns))
        y_names = {s.name or inst_name(s.instance) for s in cp.states}
        off = 0
        for nm, sz, _idx in spec.unknowns:
            if nm in y_names:
                out.append("    %s = _u[%d:%d]" % (nm, off, off + sz))
            off += sz
        out.append("    return %s" % y0)
        out.append("")


def emit_python(cp: CodePlan, space: CompileSpace) -> str:
    """Emit the derivative function for a code plan."""
    return emit_plan(cp, space, _Python())
