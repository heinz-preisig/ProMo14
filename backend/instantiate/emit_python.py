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

Limitations (milestone 1): algebraic-loop blocks are emitted inline
with a marker comment, not wrapped in a solver; multi-axis states
are packed flat without reshape.
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


def emit_python(cp: CodePlan, space: CompileSpace) -> str:
    """Emit the derivative function for a code plan."""
    out: List[str] = ["import numpy as np", ""]

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
        for b in lvl:
            rhs = _render_rhs(b, space, cp.names.get(b.entity_type, {}))
            marker = "  # algebraic loop %d" % b.loop if b.loop >= 0 else ""
            st = state_lhs.get((b.entity_type, b.lhs))
            if st is not None:
                out.append("    dy[%d:%d] = %s%s"
                           % (st.offset, st.offset + st.size,
                              rhs, marker))
            else:
                out.append("    %s = %s%s"
                           % (b.lhs_name or _name(b.lhs_instance),
                              rhs, marker))
    out.append("    return dy")
    out.append("")
    return "\n".join(out)
