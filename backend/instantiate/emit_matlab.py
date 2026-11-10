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
from typing import Dict, List, Set, Tuple

from backend.equation.compile_space import CompileSpace

from .emit_common import (
    Dialect,
    T0Layout,
    data_kinds,
    emit_plan,
    inst_name,
    loop_layout,
    split_gathers,
    tear_loop,
    t0_layout,
)
from .plan import CodePlan, PlanBlock, name_map


class _Matlab(Dialect):
    """Matlab/MultiDimVar surface syntax: 1-based indexing, labelled-
    tensor operand wraps, ``fsolve`` nested-function loop residuals."""

    target = "matlab"
    index_base = 1
    indent = "  "
    comment = "%"
    stmt_end = ";"
    no_rhs = "[]  % no rhs"
    occ_fns = True
    #: local functions must follow the main function in a .m file.
    occ_fns_at_end = True

    def __init__(self) -> None:
        # const_binds: name -> rhs hoisted to dispatcher scope — bound
        # once per dispatcher call and shared by every nested function
        # via closure.  const_names: names visible at dispatcher level
        # (matrices, value-table binds, earlier hoists) so a later
        # expression can be proven constant against them.
        self.const_binds: Dict[str, str] = {}
        self.const_names: Set[str] = set()
        self._const_n = 0
        # set when a residual is proven static (every free name is a
        # solve unknown or a dispatcher constant) — footer then emits
        # the promo_solve_once helper its call site uses.
        self._uses_once = False

    #: Identifier tokens that are builtins or emitted helpers, never
    #: free variables — the dependency classifier for hoisting.
    _RESERVED = frozenset({
        "einsum", "reducesum", "MultiDimVar", "repmat", "reshape",
        "permute", "vertcat", "horzcat", "full", "value", "zeros",
        "ones", "true", "false", "if", "else", "end", "for",
        "function", "return", "size", "numel", "length", "isempty",
        "rank", "sum", "prod", "max", "min", "abs", "sqrt", "exp",
        "log", "sin", "cos", "inv", "norm", "linspace",
        "_tab", "_ictab", "_mx", "_shape", "_model_data",
        "promo_tab", "promo_ictab", "promo_mx", "promo_shape",
        "promo_model_data", "promo_solve_balance", "promo_fsolve_balance",
        "promo_derivative", "promo_balance", "promo_t0"})

    def _free_names(self, src: str) -> Set[str]:
        """Identifier tokens in a rendered expression minus builtins
        and helpers — the names it actually depends on.  Quoted index
        labels are stripped first so {'A_conv','N'} doesn't read as a
        free name."""
        src = re.sub(r"'[^']*'", "", src)
        src = re.sub(r'"[^"]*"', "", src)
        return set(re.findall(r"[A-Za-z_]\w*", src)) - self._RESERVED

    def _hoist(self, src: str, dependent: Set[str],
               hoists: List[str]) -> str:
        """Precompute an emitted expression once per call: unchanged
        when it touches a dependent (u-local) name; bound at dispatcher
        scope when every free name is a constant there; else bound once
        in the enclosing function body via ``hoists``."""
        if src == self.no_rhs:
            return src
        free = self._free_names(src)
        if free & dependent:
            return src
        if free <= self.const_names:
            for existing, rhs in self.const_binds.items():
                if rhs == src:
                    return existing       # same expr already hoisted
        self._const_n += 1
        nm = "_k%d" % self._const_n
        if free <= self.const_names:
            self.const_binds[nm] = src
            self.const_names.add(nm)
        else:
            hoists.append("  %s = %s;  %% u-independent — hoisted"
                          % (nm, src))
        return nm

    def _emit_gather(self, out: List[str], pieces, space) -> None:
        """An invariant (u-independent) port gather: bind it at
        dispatcher scope when every input is a constant there."""
        line = (self.gather(pieces[0], space) if len(pieces) == 1
                else self.gather_multi(pieces, space))
        m = re.match(r"\s*(\w+)\s*=\s*(.*);", line)
        if m:
            nm, rhs = m.group(1), m.group(2)
            if nm in self.const_names:
                return                      # already bound up top
            if self._free_names(rhs) <= self.const_names:
                self.const_binds[nm] = rhs
                self.const_names.add(nm)
                return
        out.append(line)

    def occ_fn_open(self, name: str, params: List[str],
                    returns: List[str]) -> List[str]:
        if not returns:
            return ["function %s(%s)" % (name, ", ".join(params))]
        if len(returns) == 1:
            return ["function %s = %s(%s)"
                    % (returns[0], name, ", ".join(params))]
        return ["function [%s] = %s(%s)"
                % (", ".join(returns), name, ", ".join(params))]

    def occ_fn_close(self, returns: List[str]) -> List[str]:
        return ["end"]

    def occ_fn_call(self, name: str, args: List[str],
                    returns: List[str]) -> str:
        if not returns:
            return "  %s(%s);" % (name, ", ".join(args))
        if len(returns) == 1:
            return "  %s = %s(%s);" % (returns[0], name,
                                      ", ".join(args))
        return "  [%s] = %s(%s);" % (", ".join(returns), name,
                                    ", ".join(args))

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

    # -- dialect hooks ---------------------------------------------------

    def broadcast(self, src: str, mapped: List[int],
                  dims: List[int], lhs_indices=None,
                  space=None) -> str:
        if not dims:
            return src
        rep = [str(d if m == 1 and d > 1 else 1)
               for m, d in zip(mapped, dims)]
        if set(rep) == {"1"}:
            # every lhs-only axis is a singleton — the reshape alone
            # lands on the bound shape; nothing to repmat.
            val = "reshape((%s).value, [%s])" % (
                src, " ".join(str(d) for d in dims))
        else:
            val = "repmat(reshape((%s).value, [%s]), [%s])" % (
                src,
                " ".join(str(d) for d in mapped),
                " ".join(rep))
        return self._mdv(dict(lhs_indices or {}), space, val)

    def matrix(self, mx, space: CompileSpace) -> str:
        nm = mx.name or inst_name(mx.instance)
        self.const_names.add(nm)   # dispatcher-level constant
        # einsum reshapes operands to 3-D page matrices — sparse can't
        # be N-D in Matlab or Octave, so the F literal must be dense
        # before the MultiDimVar wrap (small matrices anyway).
        lit = 'full(_mx("%s"))' % nm
        # Wrap so einsum sees the [row, col] index labels.
        idx = dict(mx.indices or {})
        return "%s = %s;  %% F over [%d x %d]" % (
            nm, self._mdv(idx, space, lit) if idx else lit,
            len(mx.rows), len(mx.cols))

    def fn_open(self, cp: CodePlan) -> List[str]:
        total = sum(s.size for s in cp.states)
        sig = ("function [dy, outs] = derivative(t, y, par)"
               if cp.outputs
               else "function dy = derivative(t, y, par)")
        return [sig, "  dy = zeros(%d, 1);" % total]

    def state_unpack(self, st, space: CompileSpace) -> str:
        return "  %s = %s;" % (
            st.name or inst_name(st.instance),
            self._mdv(st.indices, space,
                      "y(%d:%d)" % (st.offset + 1,
                                    st.offset + st.size)))

    def param(self, p, space: CompileSpace) -> str:
        nm = p.name or inst_name(p.instance)
        if p.values is not None:
            # value-cell table: static data — bind once at dispatcher
            # scope instead of re-wrapping the MultiDimVar per call.
            if nm not in self.const_binds:
                self.const_binds[nm] = self._mdv(
                    p.indices, space, '_tab("%s")' % nm)
                self.const_names.add(nm)
            return "  %% %s — bound once in the dispatcher" % nm
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

    def gather_multi(self, pieces, space: CompileSpace) -> str:
        gn = pieces[0].name or inst_name(pieces[0].instance)
        val = "vertcat(%s)" % ", ".join(
            "%s.value([%s])" % (
                s.peer_name or inst_name(s.peer_instance),
                " ".join(str(i + 1) for i in s.map))
            for s in pieces)
        return "  %s = %s;  %% port gather" % (
            gn, self._mdv(pieces[0].indices, space, val))

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
        """One algebraic loop, cone-blocked: torn vars only are
        ``fsolve`` unknowns (MultiDimVar-wrapped guesses); interior
        blocks sweep forward inside the nested residual and once
        more after the solve to bind them."""
        tears, sweep = tear_loop(blocks)
        names, sizes = loop_layout(tears)
        total = sum(sizes)
        out.append("  function r = _loop%d(x)  %% algebraic loop %d"
                   % (loop_id, loop_id))
        off = 0
        for b, nm, sz in zip(tears, names, sizes):
            out.append("    %s = %s;"
                       % (nm, self._mdv(b.lhs_indices, space,
                                        "x(%d:%d)" % (off + 1,
                                                      off + sz))))
            off += sz
        for b in sweep:
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("    %s = %s;" % (nm, rhs))
        for i, (b, nm) in enumerate(zip(tears, names)):
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            out.append("    _r%d = (%s) - %s;" % (i, rhs, nm))
        out.append("    r = [%s];"
                   % "; ".join("_r%d.value" % i
                               for i in range(len(tears))))
        out.append("  end")
        out.append("  _x%d = fsolve(@_loop%d, zeros(%d, 1));"
                   % (loop_id, loop_id, total))
        off = 0
        for b, nm, sz in zip(tears, names, sizes):
            out.append("  %s = %s;"
                       % (nm, self._mdv(b.lhs_indices, space,
                                        "_x%d(%d:%d)"
                                        % (loop_id, off + 1,
                                           off + sz))))
            off += sz
        # bind eliminated vars at the solved tear values
        for b in sweep:
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("  %s = %s;" % (nm, rhs))

    def fn_close(self) -> List[str]:
        return ["end", ""]

    def output_tap(self, out, cp: CodePlan, space: CompileSpace
                   ) -> None:
        """``outs.<name> = <name>.value`` per §21 output — the
        second return value exposes the recorded locals; callers
        using ``dy = derivative(t, y, par)`` are unaffected.  The
        ``.value`` unwrap yields plain numerics, matching ``dy`` and
        ``y0`` conventions."""
        for o in cp.outputs:
            nm = o.name or inst_name(o.instance)
            out.append("  outs.%s = %s.value;  %% §21 output"
                       % (nm, nm))

    def pin_term(self, st, space: CompileSpace) -> str:
        """The IC pin expression — a cells literal or a ``par`` lookup,
        MultiDimVar-wrapped; the residual's rhs term in a non-steady
        solve."""
        nm = st.name or inst_name(st.instance)
        if st.ic_source == "cells":
            return self._mdv(st.indices, space, '_ictab("%s")' % nm)
        return self._mdv(st.indices, space, "par.ic0_%s" % nm)

    def initial(self, out: List[str], cp: CodePlan, spec: T0Layout,
                space: CompileSpace) -> None:
        """``y0 = initial(par, steady_state)`` — the t=0 solve as a
        nested ``_t0`` function (shares the parent workspace); all
        states, the algebraic lhs vars and the ``d<state>`` slots
        unpack as MultiDimVars, residuals unwrap via ``.value``.
        Non-steady appends one pin residual per state (``initialise``
        block, value-cell literal or ``par.ic0_<name>``);
        ``steady_state`` swaps the pins for ``der = 0`` — the states
        are then the solved-for unknowns, keeping the system square.
        Matlab has no default arguments — callers pass ``false``."""
        out.append("function y0 = initial(par, steady_state)")
        for p in cp.params + cp.inputs:
            if p.kind == "constant" and p.value is not None:
                continue
            out.append(self.param(p, space))
        y_names = {s.name or inst_name(s.instance) for s in cp.states}
        y0 = ["%s.value(:)" % (s.name or inst_name(s.instance))
              for s in cp.states]
        invariant, dependent = split_gathers(
            cp, {n for n, _, _ in spec.unknowns})
        for pieces in invariant:
            self._emit_gather(out, pieces, space)
        # residual-local names: u unpacks, dependent gathers, the arg
        # and the steady-state totalDiff helper defined inside _t0.
        dep = {n for n, _, _ in spec.unknowns} | {
            pieces[0].name or inst_name(pieces[0].instance)
            for pieces in dependent} | {"u", "totalDiff"}
        hoists: List[str] = []
        rlines: List[str] = []
        for i, (b, term) in enumerate(spec.residuals):
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            rhs = self._hoist(rhs, dep, hoists)
            rlines.append("    _r%d = (%s) - %s;" % (i, rhs, term))
        elines: List[str] = []
        ne = 0
        for b, term in spec.initials:
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            rhs = self._hoist(rhs, dep, hoists)
            elines.append("      _e%d = (%s) - %s;  %% initialise"
                          % (ne, rhs, term))
            ne += 1
        for st in spec.pins:
            nm = st.name or inst_name(st.instance)
            rhs = self._hoist(self.pin_term(st, space), dep, hoists)
            elines.append("      _e%d = (%s) - %s;  %% IC pin"
                          % (ne, rhs, nm))
            ne += 1
        out += hoists
        out.append("  function r = _t0(u)  %% t=0 residual system")
        off = 0
        for nm, sz, idx in spec.unknowns:
            out.append("    %s = %s;" % (
                nm, self._mdv(idx, space,
                              "u(%d:%d)" % (off + 1, off + sz))))
            off += sz
        out.append("    if steady_state")
        out.append("      totalDiff = @(x, y) x .* 0;  %% der = 0")
        out.append("    end")
        for pieces in dependent:
            out.append("  " + (self.gather(pieces[0], space)
                               if len(pieces) == 1
                               else self.gather_multi(pieces, space)))
        for b in spec.guesses:
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("    x0 = %s.value;  %% root! guess" % nm)
        out += rlines
        if spec.residuals:
            out.append("    r = [%s];" % "; ".join(
                "_r%d.value" % i
                for i in range(len(spec.residuals))))
        else:
            out.append("    r = zeros(length(u), 1);")
        out.append("    if steady_state")
        out.append("      r = [r; %s];  %% der = 0" % "; ".join(
            "%s.value" % n for n in spec.dx))
        out.append("    else")
        out += elines
        out.append("      r = [r; %s];" % "; ".join(
            "_e%d.value" % i for i in range(ne)))
        out.append("    end")
        out.append("  end")
        if cp.constraints:
            out.append("  _u = promo_solve_balance(@_t0, %d);"
                       % sum(sz for _, sz, _ in spec.unknowns))
        else:
            out.append("  _u = fsolve(@_t0, zeros(%d, 1));"
                       % sum(sz for _, sz, _ in spec.unknowns))
        off = 0
        for nm, sz, idx in spec.unknowns:
            if nm in y_names:
                out.append("  %s = %s;" % (
                    nm, self._mdv(idx, space,
                                  "_u(%d:%d)" % (off + 1, off + sz))))
            off += sz
        out.append("  y0 = [%s];" % "; ".join(y0))
        out.append("end")
        out.append("")

    def constrained(self, out: List[str], cp: CodePlan,
                    space: CompileSpace) -> None:
        spec = t0_layout(cp)
        states = {s.name or inst_name(s.instance) for s in cp.states}
        unknowns = [u for u in spec.unknowns if u[0] not in states]
        invariant, dependent = split_gathers(
            cp, {n for n, _, _ in unknowns})
        for pieces in invariant:
            self._emit_gather(out, pieces, space)
        # residual-local names: u unpacks, dependent gathers, the arg.
        dep = {n for n, _, _ in unknowns} | {
            pieces[0].name or inst_name(pieces[0].instance)
            for pieces in dependent} | {"u"}
        hoists: List[str] = []
        rlines: List[str] = []
        for i, (block, term) in enumerate(spec.residuals):
            rhs = self.render_rhs(block, space,
                                  name_map(cp, block.occurrence, block.entity_type))
            rhs = self._hoist(rhs, dep, hoists)
            rlines.append("    promo_r%d = (%s) - %s;" % (i, rhs, term))
        rlines.append("    r = [%s];" % "; ".join(
            "promo_r%d.value(:)" % i for i in range(len(spec.residuals))))
        dep_g_lines = [
            "  " + (self.gather(pieces[0], space)
                   if len(pieces) == 1
                   else self.gather_multi(pieces, space))
            for pieces in dependent]
        # Is the residual time-invariant?  Every free name must be a
        # solve unknown or a dispatcher constant — a reference to a
        # y/par/function-level name anywhere makes it dynamic.  The
        # r-assembly line (rlines[-1]) only concatenates the residual
        # parts; trailing %-comments are stripped before tokenising.
        allowed = dep | self.const_names
        static = all(
            self._free_names(l.split("=", 1)[-1].split("%", 1)[0])
            <= allowed
            for l in rlines[:-1] + dep_g_lines)
        out += hoists
        out.append("  function r = promo_balance(u)")
        offset = 0
        for name, size, idx in unknowns:
            out.append("    %s = %s;" % (name, self._mdv(
                idx, space, "u(%d:%d)" % (offset + 1, offset + size))))
            offset += size
        out += dep_g_lines
        out += rlines
        out.append("  end")
        if static:
            self._uses_once = True
        out.append("  promo_u = %s(@promo_balance, %d);" % (
            "promo_solve_once" if static else "promo_solve_balance",
            offset))
        offset = 0
        for name, size, idx in unknowns:
            out.append("  %s = %s;" % (name, self._mdv(
                idx, space, "promo_u(%d:%d)" % (offset + 1, offset + size))))
            offset += size
        for state, derivative in zip(cp.states, spec.dx):
            out.append("  dy(%d:%d) = %s.value(:);" % (
                state.offset + 1, state.offset + state.size, derivative))

    def footer(self, out: List[str], cp: CodePlan,
               space: CompileSpace) -> None:
        """File-end locals: ``_mdv_value`` (integral body unwrap) and
        the ``model_data.json`` loaders — ``_model_data`` keeps the
        decoded dict in a ``persistent`` so it parses once."""
        if any("integral(" in ln for ln in out):
            out += ["",
                    "function v = _mdv_value(x)",
                    "  if isa(x, 'MultiDimVar'), x = x.value; end",
                    "  v = x;",
                    "end"]
        kinds = data_kinds(cp)
        if kinds:
            out += ["",
                    "% the shared data file — the language-neutral half",
                    "% of the data/code split (parsed once, persistent)",
                    "function d = _model_data()",
                    "  persistent d_",
                    "  if isempty(d_)",
                    "    d_ = jsondecode(fileread(fullfile("
                    "fileparts(mfilename('fullpath')), "
                    "'model_data.json')));",
                    "  end",
                    "  d = d_;",
                    "end"]
        if "matrices" in kinds:
            out += ["",
                    "function a = _mx(n)",
                    "  d = _model_data();",
                    "  e = d.matrices.(n);",
                    "  a = sparse(e.i + 1, e.j + 1, e.v, e.m, e.n);",
                    "end"]
        if {"values", "ics"} & kinds:
            out += ["",
                    "function a = _shape(e)",
                    "  % jsondecode hands column vectors — row them,",
                    "  % fliplr on a column is a no-op",
                    "  d = e.dims(:).';",
                    "  if numel(d) <= 1, a = e.flat(:); return; end",
                    "  a = permute(reshape(e.flat, fliplr(d)), "
                    "fliplr(1:numel(d)));",
                    "end"]
        if "values" in kinds:
            out += ["",
                    "function a = _tab(n)",
                    "  d = _model_data();",
                    "  a = _shape(d.values.(n));",
                    "end"]
        if "ics" in kinds:
            out += ["",
                    "function a = _ictab(n)",
                    "  d = _model_data();",
                    "  a = _shape(d.ics.(n));",
                    "end"]
        if cp.constraints:
            out += ["", "function u = promo_solve_balance(fun, count)",
                    "  if count == 0",
                    "    u = zeros(0, 1); r = fun(u);",
                    "    if any(~isfinite(r)) || any(abs(r) > 1e-8), error('inconsistent prescribed balance'); end",
                    "    return;",
                    "  end",
                    "  % Emitted balance residuals are affine in u — solve",
                    "  % A u = -r(0) with a finite-difference A, cached per",
                    "  % residual (keyed on the function name) so the inner",
                    "  % solve in promo_derivative costs ~2 residual evals",
                    "  % per ODE step instead of an fsolve.  fsolve stays",
                    "  % the fallback for genuinely nonlinear residuals.",
                    "  persistent affine nonlin;",
                    "  if isempty(affine), affine = struct(); nonlin = struct(); end",
                    "  key = ['f_' regexprep(func2str(fun), '[^A-Za-z0-9_]', '_')];",
                    "  if isfield(nonlin, key)",
                    "    u = promo_fsolve_balance(fun, count); return;",
                    "  end",
                    "  r0 = fun(zeros(count, 1));",
                    "  if isfield(affine, key)",
                    "    u = -(affine.(key) \\ r0);",
                    "    r = fun(u);",
                    "    if all(isfinite(r)) && all(abs(r) <= 1e-8), return; end",
                    "    affine = rmfield(affine, key); nonlin.(key) = true;",
                    "    u = promo_fsolve_balance(fun, count); return;",
                    "  end",
                    "  A = zeros(numel(r0), count);",
                    "  for k = 1:count",
                    "    ek = zeros(count, 1); ek(k) = 1;",
                    "    A(:,k) = fun(ek) - r0;",
                    "  end",
                    "  if rank(A) >= count",
                    "    u = -(A \\ r0);",
                    "    r = fun(u);",
                    "    if all(isfinite(r)) && all(abs(r) <= 1e-8)",
                    "      affine.(key) = A; return;",
                    "    end",
                    "  end",
                    "  nonlin.(key) = true;",
                    "  u = promo_fsolve_balance(fun, count);",
                    "end"] + ([
                    "",
                    "function u = promo_solve_once(fun, count)",
                    "  % The emitter proved this residual time-invariant:",
                    "  % every input is a dispatcher constant or a solve",
                    "  % unknown, so the solution never changes — solve",
                    "  % once, then reuse it for the rest of the run.",
                    "  persistent cache;",
                    "  if isempty(cache), cache = struct(); end",
                    "  key = ['f_' regexprep(func2str(fun), '[^A-Za-z0-9_]', '_')];",
                    "  if isfield(cache, key), u = cache.(key); return; end",
                    "  u = promo_solve_balance(fun, count);",
                    "  cache.(key) = u;",
                    "end"] if self._uses_once else []) + [
                    "",
                    "function u = promo_fsolve_balance(fun, count)",
                    "  options = optimset('TolFun', 1e-12, 'TolX', 1e-12, 'Display', 'off');",
                    "  [u, r, flag, output, jac] = fsolve(fun, zeros(count, 1), options);",
                    "  if flag <= 0 || any(~isfinite(r)) || any(abs(r) > 1e-8), error('prescribed balance solve failed'); end",
                    "  if rank(jac) < count, error('prescribed balance system is underdetermined'); end",
                    "end"]


def emit_matlab(cp: CodePlan, space: CompileSpace,
                function_name: str = "derivative") -> str:
    """Emit the derivative function for a code plan.

    ``function_name`` names the dispatcher — set it to the model/file
    name so the file's first function agrees with its filename
    (Matlab warns otherwise)."""
    name = re.sub(r"[^A-Za-z0-9_]", "_", function_name)
    if not name or not name[0].isalpha():
        name = "derivative"
    d = _Matlab()
    source = emit_plan(cp, space, d)
    source = source.replace("= derivative(t, y, par)", "= promo_derivative(t, y, par)")
    source = re.sub(r"\b_([A-Za-z][A-Za-z0-9_]*)", r"promo_\1", source)
    prefix = ["function [result, outs] = %s(varargin)" % name,
              "  outs = struct();"]
    if not cp.outputs:
        source = source.replace("function dy = promo_derivative(t, y, par)",
                                "function [dy, outs] = promo_derivative(t, y, par)\n  outs = struct();")
    start = source.index("function ")
    matrices, functions = source[:start], source[start:]
    prefix.append(matrices)
    for cnm, crhs in d.const_binds.items():
        # Constants bound once per dispatcher call — visible to every
        # nested function via closure.  The promo_ rename ran on the
        # emit_plan source already; apply it here too (_tab→promo_tab,
        # _k1→promo_k1).
        prefix.append(re.sub(r"\b_([A-Za-z][A-Za-z0-9_]*)", r"promo_\1",
                             "  %s = %s;  %% bound once" % (cnm, crhs)))
    prefix += ["  if nargin == 0", "    result.derivative = @promo_derivative;"]
    if cp.states:
        prefix.append("    result.initial = @initial;")
    # Everything emit_plan produced nests INSIDE the dispatcher: the
    # matrix binds above are dispatcher locals, and sibling functions
    # can't see them — F_conv_*/V_*_* matrices would be undefined in
    # promo_derivative/initial.  Nesting shares the workspace; the
    # returned handles keep it alive via closure (run.m only touches
    # result.*), and every emitted function already closes with `end`.
    prefix += ["    return;", "  end",
               "  [result, outs] = promo_derivative(varargin{:});",
               functions, "end"]
    header = ["% ProMo-generated model file.  Companions required:",
              "%   model_data.json — /code?target=data output, place next to this file",
              "%   @MultiDimVar    — vendored Einstein-notation library,",
              "%                     addpath('<repo>/runtime/matlab')"]
    return "\n".join(header + prefix)


def matlab_run_script(name: str, cp: CodePlan) -> str:
    """A runnable driver emitted beside ``<name>.m``: addpath for the
    bundled ``@MultiDimVar`` copy, fetch the model handles, fill
    ``par`` (the comment lists the emitted parameter names), then the
    t=0 balance and a short ode45 run."""
    params = ", ".join(p.name for p in cp.params) or "none"
    lines = [
        f"% {name} — generated driver (run from this directory)",
        f"% companions: {name}.m, model_data.json in this directory;",
        "% @MultiDimVar/ one level up (shared by all model dirs)",
        "here = fileparts(mfilename('fullpath'));",
        "addpath(fullfile(here, '..'));",
        "",
        f"m = {name}();",
        f"par = struct();  % parameter fields: {params}",
    ]
    if cp.states:
        lines += [
            "% t=0 from the prescribed ICs.  initial(par, true) instead",
            "% solves for a der=0 steady state — only for models that",
            "% have one (a pure integrator does not).",
            "y0 = m.initial(par, false);",
            "[t, y] = ode45(m.derivative, [0 1], y0);",
            "plot(t, y);",
        ]
    else:
        lines += ["% no states — call the derivative directly:",
                  "% dy = m.derivative(0, y, par);"]
    return "\n".join(lines) + "\n"
