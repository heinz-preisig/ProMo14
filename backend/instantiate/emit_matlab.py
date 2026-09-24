"""Matlab emitter — render a ``CodePlan`` as a derivative function
for the ``MultiDimVar`` library (Einstein-notation tensors).

Same walk as the NumPy/Julia emitters; the differences are Matlab's
and the library's:

- **1-based indexing** — state slices, gather maps and matrix COO
  entries are shifted by one;
- **MultiDimVar operands** — ``einsum``/``reducesum`` work on
  labelled tensors, so every state, parameter and gather is wrapped
  as ``MultiDimVar({labels}, sizes, {labels}, value)`` with the
  index ``internal_code`` aliases as labels;
- **gathers relabel** — ``p[N]`` gathered over a port's contacts is
  ``p_in[A_diff]``: the peer's ``.value`` is indexed positionally
  and re-wrapped with the *port* variable's labels;
- **sparse literals** — incidence matrices emit as
  ``sparse(I, J, V, m, n)`` (column vectors, ``;``-separated),
  wrapped in a MultiDimVar so ``einsum`` sees the labels;
- **``dy`` unwrap** — Matlab can't dot-index a call result, so a
  balance's rhs goes to a ``d<lhs>`` temp and ``dy`` takes
  ``.value``.

Generated shape::

    V_4 = MultiDimVar({'N', 'A_diff'}, [2 2], {'N', 'A_diff'}, ...
                      sparse([1; 2], [1; 2], [-1; 1], 2, 2));

    function dy = derivative(t, y, par)
      dy = zeros(2, 1);
      V_1 = MultiDimVar({'N'}, 2, {'N'}, y(1:2));        % state
      V_5 = MultiDimVar({}, 1, {}, par.V_5);             % param
      % level 0
      V_2 = V_1;
      % level 1
      V_6 = MultiDimVar({'A_diff'}, 2, {'A_diff'}, ...
                        V_2.value([1 2]));               % gather
      V_3_diffusion_transport = einsum(V_5, V_6);
      % level 2
      V_3_lumped_capacity = MultiDimVar({'A_diff'}, 2, {'A_diff'}, ...
                        V_3_diffusion_transport.value([1 2]));
      dV_1 = einsum(V_4, V_3_lumped_capacity, {'A_diff'});
      dy(1:2) = dV_1.value;                              % balance → dy
    end

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


def _idx_label(iri: str, space: CompileSpace) -> str:
    """An index IRI's emitted label — the internal_code alias."""
    idx = space.indices.get(iri)
    if idx is not None:
        lab = idx.aliases.get("internal_code")
        if lab:
            return lab
    return re.sub(r"\W", "_", iri.split("/")[-1] or iri)


def _labels(indices: Dict[str, List[str]],
            space: CompileSpace) -> Tuple[str, str]:
    """Bound index map → (labels cell, sizes) for the MultiDimVar
    wrap: ``({'N', 'A_diff'}, [2 2])``; a scalar is ``({}, 1)``."""
    labs = ["'%s'" % _idx_label(iri, space) for iri in indices]
    sizes = [str(max(1, len(els or []))) for els in indices.values()]
    cell = "{%s}" % ", ".join(labs) if labs else "{}"
    dim = ("[%s]" % " ".join(sizes) if len(sizes) > 1
           else (sizes[0] if sizes else "1"))
    return cell, dim


def _mdv(indices: Dict[str, List[str]], space: CompileSpace,
         value: str) -> str:
    """``MultiDimVar({labels}, sizes, {labels}, value)``."""
    cell, dim = _labels(indices, space)
    return "MultiDimVar(%s, %s, %s, %s)" % (cell, dim, cell, value)


def _num(v) -> str:
    """One cell value as a literal; missing cells are NaN."""
    return "NaN" if v is None else repr(v)


def _array_lit(flat: List, dims: List[int]) -> str:
    """A flat C-order value table as a Matlab array literal shaped
    to the bound index sizes.  Matlab is column-major: an n-D table
    is reshaped to the reversed dims and permuted back so element
    order matches the C-order coordinate enumeration; a 1-D table
    emits as a column vector."""
    if not dims:
        return _num(flat[0]) if flat else "NaN"
    if len(dims) == 1:
        return "[%s]" % "; ".join(_num(v) for v in flat)
    n = len(dims)
    items = ", ".join(_num(v) for v in flat)
    rev = " ".join(str(d) for d in reversed(dims))
    perm = " ".join(str(i) for i in range(n, 0, -1))
    return ("permute(reshape([%s], %s), [%s])"
            % (items, rev, perm))


def _sparse(entries: List[Tuple[int, int, int]],
            rows: int, cols: int) -> str:
    """A COO entry list as a ``sparse(I, J, V, m, n)`` literal —
    column vectors, indices shifted to Matlab's 1-based convention."""
    ii = [str(r + 1) for r, _, _ in entries]
    jj = [str(c + 1) for _, c, _ in entries]
    vv = [str(s) for _, _, s in entries]
    return ("sparse([%s], [%s], [%s], %d, %d)"
            % ("; ".join(ii), "; ".join(jj), "; ".join(vv),
               rows, cols))


def _render_rhs(block: PlanBlock, space: CompileSpace,
                names: Dict[str, str]) -> str:
    """Parse → check → render one block's RHS for the matlab target,
    with the entity type's instance-name map as the override."""
    if not block.rhs:
        return "[]  % no rhs"
    lhs = Var(_name(block.lhs_instance))
    checked = check(parse(block.rhs), space, lhs)
    return render(checked, space, "matlab", lhs=lhs.name,
                  names=names)


def _bsize(b: PlanBlock) -> int:
    """Flat size of a block's lhs — product of bound index sizes."""
    n = 1
    for els in b.lhs_indices.values():
        n *= max(1, len(els or []))
    return n


def _emit_loop(out: List[str], loop_id: int, blocks: List[PlanBlock],
               space: CompileSpace, cp: CodePlan) -> None:
    """Emit one algebraic loop as an ``fsolve`` residual block — a
    nested function (shares the parent's workspace) whose guesses
    wrap as MultiDimVars and whose residuals unwrap via ``.value``."""
    names = [b.lhs_name or _name(b.lhs_instance) for b in blocks]
    sizes = [_bsize(b) for b in blocks]
    total = sum(sizes)
    out.append("  function r = _loop%d(x)  %% algebraic loop %d"
               % (loop_id, loop_id))
    off = 0
    for b, nm, sz in zip(blocks, names, sizes):
        out.append("    %s = %s;"
                   % (nm, _mdv(b.lhs_indices, space,
                               "x(%d:%d)" % (off + 1, off + sz))))
        off += sz
    for i, (b, nm) in enumerate(zip(blocks, names)):
        rhs = _render_rhs(b, space, cp.names.get(b.entity_type, {}))
        out.append("    _r%d = (%s) - %s;" % (i, rhs, nm))
    out.append("    r = [%s];"
               % "; ".join("_r%d.value" % i for i in range(len(blocks))))
    out.append("  end")
    out.append("  _x%d = fsolve(@_loop%d, zeros(%d, 1));"
               % (loop_id, loop_id, total))
    off = 0
    for b, nm, sz in zip(blocks, names, sizes):
        out.append("  %s = %s;"
                   % (nm, _mdv(b.lhs_indices, space,
                               "_x%d(%d:%d)"
                               % (loop_id, off + 1, off + sz))))
        off += sz


def emit_matlab(cp: CodePlan, space: CompileSpace) -> str:
    """Emit the derivative function for a code plan."""
    out: List[str] = []

    for mx in cp.matrices:
        lit = _sparse(mx.entries, len(mx.rows), len(mx.cols))
        # Wrap so einsum sees the [row, col] index labels.
        idx = {iri: els for iri, els in (mx.indices or {}).items()}
        out.append("%s = %s;  %% F over [%d x %d]"
                   % (mx.name or _name(mx.instance),
                      _mdv(idx, space, lit) if idx else lit,
                      len(mx.rows), len(mx.cols)))
    if cp.matrices:
        out.append("")

    total = sum(s.size for s in cp.states)
    out.append("function dy = derivative(t, y, par)")
    out.append("  dy = zeros(%d, 1);" % total)
    for st in cp.states:
        out.append("  %s = %s;"
                   % (st.name or _name(st.instance),
                      _mdv(st.indices, space,
                           "y(%d:%d)" % (st.offset + 1,
                                         st.offset + st.size))))
    for p in cp.params + cp.inputs:
        if p.kind == "constant" and p.value is not None:
            continue                      # inlined by the renderer
        nm = p.name or _name(p.instance)
        if p.values is not None:
            dims = [max(1, len(els or []))
                    for els in p.indices.values()]
            out.append("  %s = %s;  %% value cells"
                       % (nm, _mdv(p.indices, space,
                                   _array_lit(p.values, dims))))
        else:
            out.append("  %s = %s;" % (nm, _mdv(p.indices, space,
                                               "par.%s" % nm)))

    state_lhs = {(s.entity_type, s.var): s for s in cp.states}
    emitted_gathers = set()
    for level, lvl in enumerate(cp.levels):
        out.append("  %% level %d" % level)
        consumed = {v for b in lvl for v in b.inputs}
        for g in cp.gathers:
            if g.var in consumed and g.instance not in emitted_gathers:
                emitted_gathers.add(g.instance)
                gn = g.name or _name(g.instance)
                pn = g.peer_name or _name(g.peer_instance)
                if g.scalar:
                    val = "%s.value(%d)" % (pn, g.map[0] + 1)
                else:
                    val = "%s.value([%s])" % (
                        pn, " ".join(str(i + 1) for i in g.map))
                out.append("  %s = %s;  %% port gather"
                           % (gn, _mdv(g.indices, space, val)))
        loops_here: Dict[int, List[PlanBlock]] = {}
        for b in lvl:
            if b.loop >= 0:
                loops_here.setdefault(b.loop, []).append(b)
                continue
            rhs = _render_rhs(b, space, cp.names.get(b.entity_type, {}))
            st = state_lhs.get((b.entity_type, b.lhs))
            if st is not None:
                tmp = "d%s" % (b.lhs_name or _name(b.lhs_instance))
                out.append("  %s = %s;" % (tmp, rhs))
                out.append("  dy(%d:%d) = %s.value;"
                           % (st.offset + 1, st.offset + st.size, tmp))
            else:
                out.append("  %s = %s;"
                           % (b.lhs_name or _name(b.lhs_instance), rhs))
        for loop_id, blocks in sorted(loops_here.items()):
            _emit_loop(out, loop_id, blocks, space, cp)
    out.append("end")
    out.append("")
    return "\n".join(out)
