"""Matlab emitter — render a ``CodePlan`` as a derivative function
for the ``MultiDimVar`` library (Einstein-notation tensors).

The walk lives in ``emit_common.emit_plan``; this file supplies only
the Matlab surface syntax (the ``_Matlab`` dialect):

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

from backend.equation.compile_space import CompileSpace

from .emit_common import (
    Dialect,
    bound_dims,
    emit_plan,
    inst_name,
    loop_layout,
)
from .plan import CodePlan, PlanBlock


class _Matlab(Dialect):
    """Matlab/MultiDimVar surface syntax: 1-based indexing, labelled-
    tensor operand wraps, ``fsolve`` nested-function loop residuals."""

    target = "matlab"
    index_base = 1
    indent = "  "
    comment = "%"
    stmt_end = ";"
    no_rhs = "[]  % no rhs"

    # -- MultiDimVar labelling helpers ----------------------------------

    @staticmethod
    def _idx_label(iri: str, space: CompileSpace) -> str:
        """An index IRI's emitted label — the internal_code alias."""
        idx = space.indices.get(iri)
        if idx is not None:
            lab = idx.aliases.get("internal_code")
            if lab:
                return lab
        return re.sub(r"\W", "_", iri.split("/")[-1] or iri)

    @classmethod
    def _labels(cls, indices: Dict[str, List[str]],
                space: CompileSpace) -> Tuple[str, str]:
        """Bound index map → (labels cell, sizes) for the MultiDimVar
        wrap: ``({'N', 'A_diff'}, [2 2])``; a scalar is ``({}, 1)``."""
        labs = ["'%s'" % cls._idx_label(iri, space) for iri in indices]
        sizes = [str(max(1, len(els or [])))
                 for els in indices.values()]
        cell = "{%s}" % ", ".join(labs) if labs else "{}"
        dim = ("[%s]" % " ".join(sizes) if len(sizes) > 1
               else (sizes[0] if sizes else "1"))
        return cell, dim

    @classmethod
    def _mdv(cls, indices: Dict[str, List[str]], space: CompileSpace,
             value: str) -> str:
        """``MultiDimVar({labels}, sizes, {labels}, value)``."""
        cell, dim = cls._labels(indices, space)
        return "MultiDimVar(%s, %s, %s, %s)" % (cell, dim, cell, value)

    # -- literals --------------------------------------------------------

    @staticmethod
    def _num(v) -> str:
        """One cell value as a literal; missing cells are NaN."""
        return "NaN" if v is None else repr(v)

    @classmethod
    def _array_lit(cls, flat: List, dims: List[int]) -> str:
        """A flat C-order value table as a Matlab array literal shaped
        to the bound index sizes.  Matlab is column-major: an n-D table
        is reshaped to the reversed dims and permuted back so element
        order matches the C-order coordinate enumeration; a 1-D table
        emits as a column vector."""
        if not dims:
            return cls._num(flat[0]) if flat else "NaN"
        if len(dims) == 1:
            return "[%s]" % "; ".join(cls._num(v) for v in flat)
        n = len(dims)
        items = ", ".join(cls._num(v) for v in flat)
        rev = " ".join(str(d) for d in reversed(dims))
        perm = " ".join(str(i) for i in range(n, 0, -1))
        return ("permute(reshape([%s], %s), [%s])"
                % (items, rev, perm))

    @classmethod
    def _sparse(cls, entries: List[Tuple[int, int, int]],
                rows: int, cols: int) -> str:
        """A COO entry list as a ``sparse(I, J, V, m, n)`` literal —
        column vectors, indices shifted to Matlab's 1-based
        convention."""
        ii = [str(r + 1) for r, _, _ in entries]
        jj = [str(c + 1) for _, c, _ in entries]
        vv = [str(s) for _, _, s in entries]
        return ("sparse([%s], [%s], [%s], %d, %d)"
                % ("; ".join(ii), "; ".join(jj), "; ".join(vv),
                   rows, cols))

    # -- dialect hooks ---------------------------------------------------

    def matrix(self, mx, space: CompileSpace) -> str:
        lit = self._sparse(mx.entries, len(mx.rows), len(mx.cols))
        # Wrap so einsum sees the [row, col] index labels.
        idx = dict(mx.indices or {})
        return "%s = %s;  %% F over [%d x %d]" % (
            mx.name or inst_name(mx.instance),
            self._mdv(idx, space, lit) if idx else lit,
            len(mx.rows), len(mx.cols))

    def fn_open(self, cp: CodePlan) -> List[str]:
        total = sum(s.size for s in cp.states)
        return ["function dy = derivative(t, y, par)",
                "  dy = zeros(%d, 1);" % total]

    def state_unpack(self, st, space: CompileSpace) -> str:
        return "  %s = %s;" % (
            st.name or inst_name(st.instance),
            self._mdv(st.indices, space,
                      "y(%d:%d)" % (st.offset + 1,
                                    st.offset + st.size)))

    def param(self, p, space: CompileSpace) -> str:
        nm = p.name or inst_name(p.instance)
        if p.values is not None:
            return "  %s = %s;  %% value cells" % (
                nm, self._mdv(p.indices, space,
                              self._array_lit(p.values,
                                              bound_dims(p.indices))))
        return "  %s = %s;" % (nm, self._mdv(p.indices, space,
                                             "par.%s" % nm))

    def gather(self, g, space: CompileSpace) -> str:
        gn = g.name or inst_name(g.instance)
        pn = g.peer_name or inst_name(g.peer_instance)
        if g.scalar:
            val = "%s.value(%d)" % (pn, g.map[0] + 1)
        else:
            val = "%s.value([%s])" % (
                pn, " ".join(str(i + 1) for i in g.map))
        return "  %s = %s;  %% port gather" % (
            gn, self._mdv(g.indices, space, val))

    def state_assign(self, st, b: PlanBlock, rhs: str,
                     space: CompileSpace) -> List[str]:
        """``dy`` unwrap: rhs goes to a ``d<lhs>`` temp, ``dy`` takes
        its ``.value``."""
        tmp = "d%s" % (b.lhs_name or inst_name(b.lhs_instance))
        return ["  %s = %s;" % (tmp, rhs),
                "  dy(%d:%d) = %s.value;" % (
                    st.offset + 1, st.offset + st.size, tmp)]

    def loop(self, out: List[str], loop_id: int, blocks, space,
             cp: CodePlan) -> None:
        """One algebraic loop as an ``fsolve`` residual block — a
        nested function (shares the parent's workspace) whose guesses
        wrap as MultiDimVars and whose residuals unwrap via
        ``.value``."""
        names, sizes = loop_layout(blocks)
        total = sum(sizes)
        out.append("  function r = _loop%d(x)  %% algebraic loop %d"
                   % (loop_id, loop_id))
        off = 0
        for b, nm, sz in zip(blocks, names, sizes):
            out.append("    %s = %s;"
                       % (nm, self._mdv(b.lhs_indices, space,
                                        "x(%d:%d)" % (off + 1,
                                                      off + sz))))
            off += sz
        for i, (b, nm) in enumerate(zip(blocks, names)):
            rhs = self.render_rhs(b, space,
                                  cp.names.get(b.entity_type, {}))
            out.append("    _r%d = (%s) - %s;" % (i, rhs, nm))
        out.append("    r = [%s];"
                   % "; ".join("_r%d.value" % i
                               for i in range(len(blocks))))
        out.append("  end")
        out.append("  _x%d = fsolve(@_loop%d, zeros(%d, 1));"
                   % (loop_id, loop_id, total))
        off = 0
        for b, nm, sz in zip(blocks, names, sizes):
            out.append("  %s = %s;"
                       % (nm, self._mdv(b.lhs_indices, space,
                                        "_x%d(%d:%d)"
                                        % (loop_id, off + 1,
                                           off + sz))))
            off += sz

    def fn_close(self) -> List[str]:
        return ["end", ""]


def emit_matlab(cp: CodePlan, space: CompileSpace) -> str:
    """Emit the derivative function for a code plan."""
    return emit_plan(cp, space, _Matlab())
