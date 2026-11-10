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
    split_gathers,
    t0_layout,
    tear_loop,
)
from .plan import CodePlan, name_map


def _flat_size(indices) -> int:
    """Number of elements a binding's index dict spans."""
    n = 1
    for els in (indices or {}).values():
        n *= max(1, len(els or []))
    return n


class _Python(Dialect):
    """NumPy surface syntax: 0-based slicing, ``par["X"]`` lookups,
    dense ``np.array`` incidence literals, ``fsolve`` loop residuals."""

    target = "python"
    no_rhs = "None  # no rhs"
    occ_fns = True

    def occ_fn_open(self, name: str, params: List[str],
                    returns: List[str]) -> List[str]:
        return ["def %s(%s):" % (name, ", ".join(params))]

    def occ_fn_close(self, returns: List[str]) -> List[str]:
        if not returns:
            return ["    return None"]
        return ["    return %s" % ", ".join(returns)]

    def occ_fn_call(self, name: str, args: List[str],
                    returns: List[str]) -> str:
        if not returns:
            return "    %s(%s)" % (name, ", ".join(args))
        if len(returns) == 1:
            return "    %s, = %s(%s)" % (returns[0], name,
                                        ", ".join(args))
        return "    %s = %s(%s)" % (", ".join(returns), name,
                                    ", ".join(args))

    def header(self, cp: CodePlan) -> List[str]:
        kinds = data_kinds(cp)
        out = ["import numpy as np"]
        if cp.matrices:
            out.append("import scipy.sparse")
        if cp.loops or cp.states or cp.constraints:
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

    def permute(self, src: str, perm: List[int]) -> str:
        if len(perm) <= 1:
            return src
        return "(%s).transpose((%s))" % (
            src, ", ".join(str(p) for p in perm))

    def broadcast(self, src: str, mapped: List[int],
                  dims: List[int], lhs_indices=None,
                  space=None) -> str:
        if not dims:
            return src
        if mapped == dims:
            # every lhs-only axis is a singleton — a reshape alone
            # lands on the bound shape; nothing to broadcast.
            return "np.asarray(%s).reshape((%s))" % (
                src, ", ".join(str(d) for d in dims))
        return "np.broadcast_to(np.asarray(%s).reshape((%s)), (%s))" % (
            src,
            ", ".join(str(d) for d in mapped),
            ", ".join(str(d) for d in dims))

    @staticmethod
    def _shape(indices) -> str:
        """``.reshape((d1, d2))`` for a flat materialization — dims in
        declaration order so canonical axis positions hold (a
        ``tensordot`` over axis k must find that axis).  Empty for
        ≤1 index: the slice is already the right shape."""
        dims = [len(els or []) for els in (indices or {}).values()]
        if len(dims) <= 1:
            return ""
        return ".reshape((%s))" % ", ".join(str(d) for d in dims)

    def state_unpack(self, st, space: CompileSpace) -> str:
        return "    %s = y[%d:%d]%s" % (
            st.name or inst_name(st.instance), st.offset,
            st.offset + st.size, self._shape(st.indices))

    def param(self, p, space: CompileSpace) -> str:
        nm = p.name or inst_name(p.instance)
        if p.values is not None:
            return '    %s = _tab("%s")  # value cells' % (nm, nm)
        return '    %s = par["%s"]%s' % (nm, nm,
                                        self._shape(p.indices))

    def _fill(self, pairs, size: int, shape: str) -> str:
        """Positional flat gather for a coverage-mismatched binding —
        first-wins with right-pad up to the bound size, then reshape
        to the declared dims.  ``plan()`` records the coverage
        problem; this keeps the module runnable and deterministic."""
        if not pairs:
            return "np.zeros(%d)%s" % (size, shape)
        src = "np.concatenate([%s])" % ", ".join(
            "np.ravel(%s.flat[%d])" % (pn, m) for pn, m in pairs)
        if len(pairs) != size:
            src = "np.pad(%s, (0, %d))[:%d]" % (
                src, max(0, size - len(pairs)), size)
        return src + shape

    def gather(self, g, space: CompileSpace) -> str:
        gn = g.name or inst_name(g.instance)
        pn = g.peer_name or inst_name(g.peer_instance)
        if g.scalar:
            return "    %s = %s[%d]  # port gather" % (gn, pn, g.map[0])
        size = _flat_size(g.indices)
        if len(g.map) != size:
            return "    %s = %s  # port gather" % (
                gn, self._fill([(pn, m) for m in g.map], size,
                               self._shape(g.indices)))
        return "    %s = %s[%s]  # port gather" % (gn, pn, g.map)

    def gather_multi(self, pieces, space: CompileSpace) -> str:
        gn = pieces[0].name or inst_name(pieces[0].instance)
        size = _flat_size(pieces[0].indices)
        pairs = [(s.peer_name or inst_name(s.peer_instance), m)
                 for s in pieces for m in s.map]
        if len(pairs) != size:
            return "    %s = %s  # port gather" % (
                gn, self._fill(pairs, size,
                               self._shape(pieces[0].indices)))
        sel = ", ".join(
            "np.ravel(%s[%s])" % (
                s.peer_name or inst_name(s.peer_instance),
                [i for i in s.map])
            for s in pieces)
        return "    %s = np.concatenate([%s])%s  # port gather" % (
            gn, sel, self._shape(pieces[0].indices))

    def _den(self, expr: str) -> str:
        """``_d(expr)`` when sparse values can reach this file —
        identity otherwise (no helper emitted then)."""
        return "_d(%s)" % expr if self.sparse_names else expr

    def state_assign(self, st, b, rhs, space: CompileSpace) -> List[str]:
        """``dy[...] = rhs`` — a sparse rhs must be densified for the
        packed derivative slice."""
        return ["%sdy[%d:%d] = np.ravel(%s)" % (
            self.indent, st.offset, st.offset + st.size,
            self._den(rhs))]

    def loop(self, out: List[str], loop_id: int, blocks, space,
             cp: CodePlan) -> None:
        """One algebraic loop, cone-blocked: only the *torn* vars
        (boundary-crossing producers, then greedy feedback) are
        ``fsolve`` unknowns — interior blocks evaluate as a forward
        sweep inside the residual.  After the solve the sweep re-runs
        once at top level to bind the eliminated vars."""
        tears, sweep = tear_loop(blocks)
        names, sizes = loop_layout(tears)
        total = sum(sizes)
        out.append("    def _loop%d(x):  # algebraic loop %d"
                   % (loop_id, loop_id))
        tear_idx = {b.lhs_name or inst_name(b.lhs_instance):
                    b.lhs_indices for b in tears}
        off = 0
        for nm, sz in zip(names, sizes):
            out.append("        %s = x[%d:%d]%s" % (
                nm, off, off + sz, self._shape(tear_idx.get(nm))))
            off += sz
        for b in sweep:
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("        %s = %s" % (nm, rhs))
        for b, nm in zip(tears, names):
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            out.append("        _r_%s = (%s) - %s"
                       % (nm, self._den(rhs), nm))
        out.append("        return np.concatenate([%s])"
                   % ", ".join("np.ravel(_r_%s)" % nm
                               for nm in names))
        out.append("    _x%d = fsolve(_loop%d, np.zeros(%d))"
                   % (loop_id, loop_id, total))
        off = 0
        for nm, sz in zip(names, sizes):
            out.append("    %s = _x%d[%d:%d]%s"
                       % (nm, loop_id, off, off + sz,
                          self._shape(tear_idx.get(nm))))
            off += sz
        # bind eliminated vars at the solved tear values
        for b in sweep:
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("    %s = %s" % (nm, rhs))

    def constrained(self, out: List[str], cp: CodePlan,
                    space: CompileSpace) -> None:
        spec = t0_layout(cp)
        state_names = {s.name or inst_name(s.instance) for s in cp.states}
        unknowns = [u for u in spec.unknowns if u[0] not in state_names]
        invariant, dependent = split_gathers(
            cp, {n for n, _, _ in unknowns})
        for pieces in invariant:
            out.append(self.gather(pieces[0], space) if len(pieces) == 1
                       else self.gather_multi(pieces, space))
        out.append("    def _balance(u):")
        offset = 0
        for name, size, idx in unknowns:
            out.append("        %s = u[%d:%d]%s" % (
                name, offset, offset + size, self._shape(idx)))
            offset += size
        for pieces in dependent:
            out.append("    " + (self.gather(pieces[0], space)
                                 if len(pieces) == 1
                                 else self.gather_multi(pieces, space)))
        for i, (block, term) in enumerate(spec.residuals):
            rhs = self.render_rhs(block, space, name_map(cp, block.occurrence, block.entity_type))
            out.append("        _r%d = np.ravel((%s) - %s)" % (i, self._den(rhs), term))
        out.append("        return np.concatenate([%s])" % ", ".join(
            "_r%d" % i for i in range(len(spec.residuals))))
        out.append("    _u = _solve_balance(_balance, %d)" % offset)
        offset = 0
        for name, size, idx in unknowns:
            out.append("    %s = _u[%d:%d]%s" % (
                name, offset, offset + size, self._shape(idx)))
            offset += size
        for state, derivative in zip(cp.states, spec.dx):
            out.append("    dy[%d:%d] = np.ravel(%s)" % (
                state.offset, state.offset + state.size, derivative))

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
        if not cp.matrices and not cp.constraints:
            return
        out += ["",
                "def _d(x):",
                "    return x.toarray() if hasattr(x, 'toarray') "
                "else x"]
        if cp.constraints:
            out += self.balance_helpers()

    @staticmethod
    def balance_helpers() -> List[str]:
        return ["", "def _solve_balance(fun, size):",
                "    guess = np.zeros(size)",
                "    if size == 0:",
                "        if not np.allclose(fun(guess), 0, atol=1e-8):",
                "            raise ValueError('prescribed balance is inconsistent')",
                "        return guess",
                "    result = scipy.optimize.least_squares(fun, guess, ftol=1e-12, xtol=1e-12, gtol=1e-12)",
                "    if not result.success or not np.all(np.isfinite(result.fun)) or np.max(np.abs(result.fun), initial=0) > 1e-8:",
                "        raise ValueError('prescribed balance solve failed: ' + result.message)",
                "    if np.linalg.matrix_rank(result.jac) < size:",
                "        raise ValueError('prescribed balance system is underdetermined')",
                "    return result.x"]

    def pin_term(self, st, space: CompileSpace) -> str:
        """The IC pin expression — a cells literal or a ``par`` lookup,
        used as the residual's rhs term in a non-steady solve."""
        nm = st.name or inst_name(st.instance)
        if st.ic_source == "cells":
            return '_ictab("%s")' % nm
        return 'par["ic0_%s"]%s' % (nm, self._shape(st.indices))

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
        invariant, dependent = split_gathers(
            cp, {n for n, _, _ in spec.unknowns})
        for pieces in invariant:
            out.append(self.gather(pieces[0], space) if len(pieces) == 1
                       else self.gather_multi(pieces, space))
        y0 = "np.concatenate([%s])" % ", ".join(
            "np.ravel(%s)" % (s.name or inst_name(s.instance))
            for s in cp.states)
        out.append("    def _t0(u):  # t=0 residual system")
        off = 0
        for nm, sz, idx in spec.unknowns:
            out.append("        %s = u[%d:%d]%s" % (
                nm, off, off + sz, self._shape(idx)))
            off += sz
        out.append("        if steady_state:")
        out.append("            total_diff = lambda x, y: "
                   "np.zeros_like(x)  # der = 0")
        for pieces in dependent:
            out.append("    " + (self.gather(pieces[0], space)
                                 if len(pieces) == 1
                                 else self.gather_multi(pieces, space)))
        for b in spec.guesses:
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("        x0 = np.ravel(%s)  # root! guess"
                       % nm)
        for i, (b, term) in enumerate(spec.residuals):
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            out.append("        _r%d = (%s) - %s"
                       % (i, self._den(rhs), term))
        out.append("        _rs = [%s]" % ", ".join(
            "np.ravel(_r%d)" % i
            for i in range(len(spec.residuals))))
        out.append("        if steady_state:")
        out.append("            _rs += [%s]  # der = 0" % ", ".join(
            "np.ravel(%s)" % n for n in spec.dx))
        out.append("        else:")
        ne = 0
        for b, term in spec.initials:
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            out.append("            _e%d = (%s) - %s  # initialise"
                       % (ne, rhs, term))
            ne += 1
        for st in spec.pins:
            nm = st.name or inst_name(st.instance)
            out.append("            _e%d = (%s) - %s  # IC pin"
                       % (ne, self.pin_term(st, space), nm))
            ne += 1
        out.append("            _rs += [%s]" % ", ".join(
            "np.ravel(_e%d)" % i for i in range(ne)))
        out.append("        return np.concatenate(_rs) "
                   "if _rs else np.zeros_like(u)")
        if cp.constraints:
            out.append("    _u = _solve_balance(_t0, %d)"
                       % sum(sz for _, sz, _ in spec.unknowns))
        else:
            out.append("    _u = fsolve(_t0, np.zeros(%d))"
                       % sum(sz for _, sz, _ in spec.unknowns))
        y_names = {s.name or inst_name(s.instance) for s in cp.states}
        off = 0
        for nm, sz, idx in spec.unknowns:
            if nm in y_names:
                out.append("    %s = _u[%d:%d]%s" % (
                    nm, off, off + sz, self._shape(idx)))
            off += sz
        out.append("    return %s" % y0)
        out.append("")


def emit_python(cp: CodePlan, space: CompileSpace) -> str:
    """Emit the derivative function for a code plan."""
    return emit_plan(cp, space, _Python())


def python_run_script(name: str, cp: CodePlan) -> str:
    """A runnable driver emitted beside ``<name>.py``: sys.path the
    script's own directory so it imports the emitted module from any
    cwd, fill ``par`` (the comment lists the emitted parameter names),
    then the t=0 initialisation and a short solve_ivp run."""
    params = ", ".join(p.name for p in cp.params) or "none"
    lines = [
        '"""%s — generated driver (run: bash run_python.sh)."""' % name,
        "import os.path as _osp",
        "import sys as _sys",
        "",
        "_sys.path.insert(0, _osp.dirname(_osp.abspath(__file__)))",
        "import numpy as np",
        "from scipy.integrate import solve_ivp",
        "import %s as model" % name,
        "",
        "par = {}  # parameter fields: %s" % params,
    ]
    if cp.states:
        lines += [
            "# t=0 from the prescribed ICs.  initial(par, True) instead",
            "# solves for a der=0 steady state — only for models that",
            "# have one (a pure integrator does not).",
            "y0 = model.initial(par, False)",
            "sol = solve_ivp(lambda t, y: model.derivative(t, y, par),",
            "                (0, 1), y0, rtol=1e-6, atol=1e-8,",
            "                dense_output=True)",
            "t = np.linspace(0, 1, 21)",
            'print("t:", np.array2string(t, precision=3))',
            'print("y:", np.array2string(sol.sol(t).T, precision=6,',
            '                            suppress_small=True))',
        ]
    else:
        lines += ["# no states — call the derivative directly:",
                  "# dy = model.derivative(0, y, par)"]
    return "\n".join(lines) + "\n"


def python_shell_script() -> str:
    """``run_python.sh`` — an environment bootstrap emitted beside
    ``run.py``.  Works from any cwd (paths resolve relative to the
    script); dependency strategy: uv ephemeral env → system python
    that already has numpy/scipy → a once-created local ``.venv``."""
    return '''#!/usr/bin/env bash
# run_python.sh — run the emitted model driver (run.py) from anywhere.
# Needs numpy + scipy; resolves them in this order:
#   1. uv — an ephemeral env (nothing installed permanently)
#   2. the system python3, if it already has numpy + scipy
#   3. a .venv created once next to this script, then reused
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v uv >/dev/null 2>&1; then
    exec uv run --no-project --with numpy --with scipy \
        python "$HERE/run.py" "$@"
fi

if python3 -c "import numpy, scipy" 2>/dev/null; then
    exec python3 "$HERE/run.py" "$@"
fi

VENV="$HERE/.venv"
if [ ! -x "$VENV/bin/python" ]; then
    echo "run_python.sh: creating $VENV (numpy/scipy not found)" >&2
    python3 -m venv "$VENV" || {
        echo "run_python.sh: python3-venv unavailable — install it or uv" >&2
        exit 1
    }
    "$VENV/bin/python" -m pip install --quiet --upgrade pip numpy scipy
fi
exec "$VENV/bin/python" "$HERE/run.py" "$@"
'''
