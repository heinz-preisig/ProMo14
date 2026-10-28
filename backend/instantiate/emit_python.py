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

from typing import List

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


class _Python(Dialect):
    """NumPy surface syntax: 0-based slicing, ``par["X"]`` lookups,
    dense ``np.array`` incidence literals, ``fsolve`` loop residuals."""

    target = "python"
    no_rhs = "None  # no rhs"


    def header(self, cp: CodePlan) -> List[str]:
        kinds = data_kinds(cp)
        out = ["import numpy as np"]
        if cp.matrices:
            out.append("import scipy.sparse")
        if cp.loops or cp.states:
            # fsolve: algebraic loops + the t=0 solve; the module import
            # backs ``scipy.optimize.fsolve`` inside root!() bodies.
            out.append("import scipy.optimize")
            out.append("from scipy.optimize import fsolve")
        if kinds:
            # the shared data file — matrices + value/IC tables live
            # in model_data.json next to this file (the language-
            # neutral half of the data/code split).
            out += ["import json as _json", "import os.path as _osp", "",
                    "_DIR = (_osp.dirname(_osp.abspath(__file__))"
                    " if '__file__' in globals() else '')",
                    "if '_DATA' not in globals():",
                    '    _DATA = _json.load(open(_osp.join('
                    '_DIR, "model_data.json")))']
        if "matrices" in kinds:
            out += ["", "def _mx(n):",
                    "    e = _DATA['matrices'][n]",
                    "    return scipy.sparse.coo_array("
                    "        (e['v'], (e['i'], e['j'])),"
                    "        shape=(e['m'], e['n']))"]
        if "values" in kinds:
            out += ["", "def _tab(n):",
                    "    e = _DATA['values'][n]",
                    "    return np.array(e['flat']).reshape(e['dims'])"]
        if "ics" in kinds:
            out += ["", "def _ictab(n):",
                    "    e = _DATA['ics'][n]",
                    "    return np.array(e['flat']).reshape(e['dims'])"]
        out.append("")
        return out

    def matrix(self, mx, space: CompileSpace) -> str:
        nm = mx.name or inst_name(mx.instance)
        return '%s = _mx("%s")  # F over [%d x %d]' % (
            nm, nm, len(mx.rows), len(mx.cols))

    def fn_open(self, cp: CodePlan) -> List[str]:
        total = sum(s.size for s in cp.states)
        sig = ("def derivative(t, y, par, out=None):" if cp.outputs
               else "def derivative(t, y, par):")
        return [sig, "    dy = np.zeros(%d)" % total]

    def state_unpack(self, st, space: CompileSpace) -> str:
        return "    %s = y[%d:%d]" % (
            st.name or inst_name(st.instance), st.offset,
            st.offset + st.size)

    def param(self, p, space: CompileSpace) -> str:
        nm = p.name or inst_name(p.instance)
        if p.values is not None:
            return '    %s = _tab("%s")  # value cells' % (nm, nm)
        return '    %s = par["%s"]' % (nm, nm)

    def gather(self, g, space: CompileSpace) -> str:
        gn = g.name or inst_name(g.instance)
        pn = g.peer_name or inst_name(g.peer_instance)
        if g.scalar:
            return "    %s = %s[%d]  # port gather" % (gn, pn, g.map[0])
        return "    %s = %s[%s]  # port gather" % (gn, pn, g.map)

    def _den(self, expr: str) -> str:
        """``_d(expr)`` when sparse values can reach this file —
        identity otherwise (no helper emitted then)."""
        return "_d(%s)" % expr if self.sparse_names else expr

    def state_assign(self, st, b, rhs, space: CompileSpace) -> List[str]:
        """``dy[...] = rhs`` — a sparse rhs must be densified for the
        packed derivative slice."""
        return ["%sdy[%d:%d] = %s" % (
            self.indent, st.offset, st.offset + st.size,
            self._den(rhs))]

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
            out.append("        _r_%s = (%s) - %s"
                       % (nm, self._den(rhs), nm))
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

    def output_tap(self, out, cp: CodePlan, space: CompileSpace
                   ) -> None:
        """``out["name"] = name`` per §21 output — the optional
        ``out`` dict is populated as a side channel without breaking
        the ODE signature (``derivative(t, y, par)`` still works)."""
        out.append("    if out is not None:  # §21 outputs")
        for o in cp.outputs:
            nm = o.name or inst_name(o.instance)
            out.append('        out["%s"] = %s'
                       % (nm, self._den(nm)))

    def outputs_fn(self, out, cp: CodePlan, space: CompileSpace
                   ) -> None:
        """``outputs(t, y, par)`` — one derivative call, returns the
        recorded outputs dict (dy is discarded)."""
        out.append("def outputs(t, y, par):")
        out.append("    _o = {}")
        out.append("    derivative(t, y, par, out=_o)")
        out.append("    return _o")
        out.append("")

    def footer(self, out: List[str], cp: CodePlan,
               space: CompileSpace) -> None:
        """``_d`` — the densify shim used at residual/dy/output
        assign points (sparse results unwrap, denses pass through)."""
        if not cp.matrices:
            return
        out += ["",
                "def _d(x):",
                "    return x.toarray() if scipy.sparse.issparse(x) "
                "else x"]

    def pin_term(self, st, space: CompileSpace) -> str:
        """The IC pin expression — a cells literal or a ``par`` lookup,
        used as the residual's rhs term in a non-steady solve."""
        nm = st.name or inst_name(st.instance)
        if st.ic_source == "cells":
            return '_ictab("%s")' % nm
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
            out.append("        _r%d = (%s) - %s"
                       % (i, self._den(rhs), term))
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
