"""Julia emitter — render a ``CodePlan`` as an in-place derivative
function for OrdinaryDiffEq (``f(du, u, p, t)``).

Same walk as the NumPy emitter; the differences are Julia's:

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


def _sparse(entries: List[Tuple[int, int, int]],
            rows: int, cols: int) -> str:
    """A COO entry list as a ``sparse(I, J, V, m, n)`` literal —
    indices shifted to Julia's 1-based convention."""
    ii = [str(r + 1) for r, _, _ in entries]
    jj = [str(c + 1) for _, c, _ in entries]
    vv = [str(s) for _, _, s in entries]
    return ("sparse([%s], [%s], [%s], %d, %d)"
            % (", ".join(ii), ", ".join(jj), ", ".join(vv),
               rows, cols))


def _render_rhs(block: PlanBlock, space: CompileSpace,
                names: Dict[str, str]) -> str:
    """Parse → check → render one block's RHS for the julia target,
    with the entity type's instance-name map as the override."""
    if not block.rhs:
        return "nothing  # no rhs"
    lhs = Var(_name(block.lhs_instance))
    checked = check(parse(block.rhs), space, lhs)
    return render(checked, space, "julia", lhs=lhs.name,
                  names=names)


def emit_julia(cp: CodePlan, space: CompileSpace) -> str:
    """Emit the in-place derivative function for a code plan."""
    out: List[str] = ["using SparseArrays", ""]

    for mx in cp.matrices:
        out.append("%s = %s  # F over [%d x %d]"
                   % (mx.name or _name(mx.instance),
                      _sparse(mx.entries, len(mx.rows), len(mx.cols)),
                      len(mx.rows), len(mx.cols)))
    if cp.matrices:
        out.append("")

    out.append("function derivative!(dy, y, par, t)")
    for st in cp.states:
        out.append("    %s = @view y[%d:%d]"
                   % (st.name or _name(st.instance),
                      st.offset + 1, st.offset + st.size))
    for p in cp.params + cp.inputs:
        if p.kind == "constant" and p.value is not None:
            continue                      # inlined by the renderer
        nm = p.name or _name(p.instance)
        out.append("    %s = par.%s" % (nm, nm))

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
                               % (gn, pn, g.map[0] + 1))
                else:
                    out.append("    %s = %s[%s]  # port gather"
                               % (gn, pn,
                                  [i + 1 for i in g.map]))
        for b in lvl:
            rhs = _render_rhs(b, space, cp.names.get(b.entity_type, {}))
            marker = "  # algebraic loop %d" % b.loop if b.loop >= 0 else ""
            st = state_lhs.get((b.entity_type, b.lhs))
            if st is not None:
                out.append("    dy[%d:%d] = %s%s"
                           % (st.offset + 1, st.offset + st.size,
                              rhs, marker))
            else:
                out.append("    %s = %s%s"
                           % (b.lhs_name or _name(b.lhs_instance),
                              rhs, marker))
    out.append("    return nothing")
    out.append("end")
    out.append("")
    return "\n".join(out)
