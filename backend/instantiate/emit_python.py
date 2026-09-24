"""NumPy emitter — render a ``CodePlan`` as a Python derivative
function.

The emitter walks the plan's levels; each block's ``rhs`` is parsed,
checked and rendered by the equation ``Renderer`` (``python``
target) with the plan's per-type ``names`` map as the name override
— so a port var and its peer (same var IRI on two types) get
distinct identifiers.

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

import re
from typing import Dict, List, Tuple

from backend.equation.checker import check
from backend.equation.codegen import render
from backend.equation.compile_space import CompileSpace
from backend.equation.parser import parse
from backend.equation.syntax import Var

from .plan import CodePlan, PlanBlock


def _name(instance: str) -> str:
    """Fallback emitted name — the internal_id part, sanitised."""
    return re.sub(r"\W", "_", instance.split("@")[0])


def _num(v) -> str:
    """One cell value as a literal; missing cells are NaN."""
    return "np.nan" if v is None else repr(v)


def _array_lit(flat: List, dims: List[int]) -> str:
    """A flat C-order value table as an ``np.array`` literal shaped
    to the bound index sizes — the ν channel's codegen form."""
    items = ", ".join(_num(v) for v in flat)
    if not dims:
        return items or "np.nan"
    arr = "np.array([%s])" % items
    if len(dims) > 1:
        arr += ".reshape((%s))" % ", ".join(str(d) for d in dims)
    return arr


def _dense(rows: int, cols: int,
           entries: List[Tuple[int, int, int]]) -> str:
    """A COO entry list as a dense ``np.array`` literal."""
    m = [[0] * cols for _ in range(rows)]
    for r, c, s in entries:
        m[r][c] = s
    return "np.array([%s])" % ", ".join(str(r) for r in m)


def _render_rhs(block: PlanBlock, space: CompileSpace,
                names: Dict[str, str]) -> str:
    """Parse → check → render one block's RHS for the python target,
    with the entity type's instance-name map as the override."""
    if not block.rhs:
        return "None  # no rhs"
    lhs = Var(_name(block.lhs_instance))
    checked = check(parse(block.rhs), space, lhs)
    return render(checked, space, "python", lhs=lhs.name,
                  names=names)


def _bsize(b: PlanBlock) -> int:
    """Flat size of a block's lhs — product of bound index sizes."""
    n = 1
    for els in b.lhs_indices.values():
        n *= max(1, len(els or []))
    return n


def _emit_loop(out: List[str], loop_id: int, blocks: List[PlanBlock],
               space: CompileSpace, cp: CodePlan) -> None:
    """Emit one algebraic loop as an ``fsolve`` residual block: the
    loop's lhs vars are the unknowns (packed flat), each residual is
    ``rhs - lhs`` evaluated with the guesses bound."""
    names = [b.lhs_name or _name(b.lhs_instance) for b in blocks]
    sizes = [_bsize(b) for b in blocks]
    total = sum(sizes)
    out.append("    def _loop%d(x):  # algebraic loop %d"
               % (loop_id, loop_id))
    off = 0
    for nm, sz in zip(names, sizes):
        out.append("        %s = x[%d:%d]" % (nm, off, off + sz))
        off += sz
    for b, nm in zip(blocks, names):
        rhs = _render_rhs(b, space, cp.names.get(b.entity_type, {}))
        out.append("        _r_%s = (%s) - %s" % (nm, rhs, nm))
    out.append("        return np.concatenate([%s])"
               % ", ".join("np.atleast_1d(_r_%s)" % nm
                           for nm in names))
    out.append("    _x%d = fsolve(_loop%d, np.zeros(%d))"
               % (loop_id, loop_id, total))
    off = 0
    for nm, sz in zip(names, sizes):
        out.append("    %s = _x%d[%d:%d]" % (nm, loop_id, off, off + sz))
        off += sz


def emit_python(cp: CodePlan, space: CompileSpace) -> str:
    """Emit the derivative function for a code plan."""
    out: List[str] = ["import numpy as np"]
    if cp.loops:
        out.append("from scipy.optimize import fsolve")
    out.append("")

    for mx in cp.matrices:
        out.append("%s = %s  # F over [%d x %d]"
                   % (mx.name or _name(mx.instance),
                      _dense(len(mx.rows), len(mx.cols), mx.entries),
                      len(mx.rows), len(mx.cols)))
    if cp.matrices:
        out.append("")

    total = sum(s.size for s in cp.states)
    out.append("def derivative(t, y, par):")
    out.append("    dy = np.zeros(%d)" % total)
    for st in cp.states:
        out.append("    %s = y[%d:%d]"
                   % (st.name or _name(st.instance), st.offset,
                      st.offset + st.size))
    for p in cp.params + cp.inputs:
        if p.kind == "constant" and p.value is not None:
            continue                      # inlined by the renderer
        nm = p.name or _name(p.instance)
        if p.values is not None:
            dims = [max(1, len(els or []))
                    for els in p.indices.values()]
            out.append("    %s = %s  # value cells"
                       % (nm, _array_lit(p.values, dims)))
        else:
            out.append('    %s = par["%s"]' % (nm, nm))

    state_lhs = {(s.entity_type, s.var): s for s in cp.states}
    emitted_gathers = set()
    for level, lvl in enumerate(cp.levels):
        out.append("    # level %d" % level)
        consumed = {v for b in lvl for v in b.inputs}
        for g in cp.gathers:
            if g.var in consumed and g.instance not in emitted_gathers:
                emitted_gathers.add(g.instance)
                gn = g.name or _name(g.instance)
                pn = g.peer_name or _name(g.peer_instance)
                if g.scalar:
                    out.append("    %s = %s[%d]  # port gather"
                               % (gn, pn, g.map[0]))
                else:
                    out.append("    %s = %s[%s]  # port gather"
                               % (gn, pn, g.map))
        loops_here: Dict[int, List[PlanBlock]] = {}
        for b in lvl:
            if b.loop >= 0:
                loops_here.setdefault(b.loop, []).append(b)
                continue
            rhs = _render_rhs(b, space, cp.names.get(b.entity_type, {}))
            st = state_lhs.get((b.entity_type, b.lhs))
            if st is not None:
                out.append("    dy[%d:%d] = %s"
                           % (st.offset, st.offset + st.size, rhs))
            else:
                out.append("    %s = %s"
                           % (b.lhs_name or _name(b.lhs_instance), rhs))
        for loop_id, blocks in sorted(loops_here.items()):
            _emit_loop(out, loop_id, blocks, space, cp)
    out.append("    return dy")
    out.append("")
    return "\n".join(out)
