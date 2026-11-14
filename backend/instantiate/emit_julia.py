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
    data_kinds,
    emit_plan,
    inst_name,
    loop_layout,
    split_gathers,
    t0_layout,
    tear_loop,
)
from .plan import CodePlan, name_map


class _Julia(Dialect):
    """Julia surface syntax: 1-based indexing, ``@view`` state
    slices, NamedTuple params, ``sparse`` incidence literals,
    in-place ``nlsolve!`` loop residuals."""

    target = "julia"
    index_base = 1
    no_rhs = "nothing  # no rhs"
    occ_fns = True
    #: same-level units are independent — spawn them; fetches
    #: barrier before any loop (a global solve) consumes results.
    level_tasks = True

    def task_spawn(self, tid: int, expr: str) -> str:
        return "    _t%d = Threads.@spawn %s" % (tid, expr)

    def task_fetch(self, tid: int, binds: List[str], st) -> str:
        if st is not None:
            # the dy write happens at the barrier, not in the task
            return "    dy[%d:%d] = fetch(_t%d)" % (
                st.offset + 1, st.offset + st.size, tid)
        if binds:
            return "    %s = fetch(_t%d)" % (", ".join(binds), tid)
        return "    fetch(_t%d)" % tid

    def occ_fn_open(self, name: str, params: List[str],
                    returns: List[str]) -> List[str]:
        return ["function %s(%s)" % (name, ", ".join(params))]

    def occ_fn_close(self, returns: List[str]) -> List[str]:
        if not returns:
            return ["    return nothing", "end"]
        if len(returns) == 1:
            return ["    return %s" % returns[0], "end"]
        return ["    return (%s)" % ", ".join(returns), "end"]

    def occ_fn_call(self, name: str, args: List[str],
                    returns: List[str]) -> str:
        if not returns:
            return "    %s(%s)" % (name, ", ".join(args))
        return "    %s = %s(%s)" % (", ".join(returns), name,
                                    ", ".join(args))

    def header(self, cp: CodePlan) -> List[str]:
        kinds = data_kinds(cp)
        out = ["using SparseArrays"]
        if cp.loops or cp.states or cp.constraints:
            # NLsolve backs the algebraic-loop residuals, the t=0
            # solve and the prescribed-balance check.
            out.append("using NLsolve")
        if cp.constraints:
            # rank() — the underdetermined guard in _solve_balance.
            out.append("using LinearAlgebra")
        if kinds:
            # the shared data file — matrices + value/IC tables live
            # in model_data.json next to this file (the language-
            # neutral half of the data/code split).
            out += ["using JSON", "",
                    '_DATA = JSON.parsefile(joinpath(@__DIR__, '
                    '"model_data.json"))']
        if "matrices" in kinds:
            # JSON.parsefile yields Vector{Any} — Int/Float64 the
            # pieces or sparse() and the solvers see Any-typed data.
            out += ["", "function _mx(n)",
                    "    e = _DATA[\"matrices\"][n]",
                    "    return sparse(Int.(e[\"i\"]) .+ 1, "
                    "Int.(e[\"j\"]) .+ 1, "
                    "Float64.(e[\"v\"]), e[\"m\"], e[\"n\"])",
                    "end"]
        if {"values", "ics"} & kinds:
            out += ["", "function _shape(e)",
                    "    d = Int.(e[\"dims\"])",
                    "    length(d) <= 1 && return Float64.(e[\"flat\"])",
                    "    # C-order flat → column-major: reshape the "
                    "    # reversed dims, permute back",
                    "    return permutedims(reshape(Float64.(e[\"flat\"]), "
                    "        reverse(d)...), reverse(1:length(d)))",
                    "end"]
        if "values" in kinds:
            out += ["", '_tab(n) = _shape(_DATA["values"][n])']
        if "ics" in kinds:
            out += ["", '_ictab(n) = _shape(_DATA["ics"][n])']
        out.append("")
        return out

    def matrix(self, mx, space: CompileSpace) -> str:
        nm = mx.name or inst_name(mx.instance)
        return '%s = _mx("%s")  # F over [%d x %d]' % (
            nm, nm, len(mx.rows), len(mx.cols))

    def fn_open(self, cp: CodePlan) -> List[str]:
        if cp.outputs:
            return ["function derivative!(dy, y, par, t; "
                    "outs=nothing)"]
        return ["function derivative!(dy, y, par, t)"]

    def permute(self, src: str, perm: List[int]) -> str:
        if len(perm) <= 1:
            return src
        return "permutedims(%s, (%s))" % (
            src, ", ".join(str(p + 1) for p in perm))

    def broadcast(self, src: str, mapped: List[int],
                  dims: List[int], lhs_indices=None,
                  space=None) -> str:
        if not dims:
            return src
        return "reshape(%s, (%s))" % (
            src, ", ".join(str(d) for d in mapped))

    def state_unpack(self, st, space: CompileSpace) -> str:
        return "    %s = @view y[%d:%d]" % (
            st.name or inst_name(st.instance),
            st.offset + 1, st.offset + st.size)

    def param(self, p, space: CompileSpace) -> str:
        nm = p.name or inst_name(p.instance)
        if p.values is not None:
            return '    %s = _tab("%s")  # value cells' % (nm, nm)
        return "    %s = par.%s" % (nm, nm)

    def gather(self, g, space: CompileSpace) -> str:
        gn = g.name or inst_name(g.instance)
        pn = g.peer_name or inst_name(g.peer_instance)
        if g.scalar:
            return "    %s = %s[%d]  # port gather" % (gn, pn,
                                                       g.map[0] + 1)
        return "    %s = %s[%s]  # port gather" % (
            gn, pn, [i + 1 for i in g.map])

    def gather_multi(self, pieces, space: CompileSpace) -> str:
        gn = pieces[0].name or inst_name(pieces[0].instance)
        sel = ", ".join(
            "%s[[%s]]" % (
                s.peer_name or inst_name(s.peer_instance),
                ", ".join(str(i + 1) for i in s.map))
            for s in pieces)
        return "    %s = vcat(%s)  # port gather" % (gn, sel)

    def loop(self, out: List[str], loop_id: int, blocks, space,
             cp: CodePlan) -> None:
        """One algebraic loop, cone-blocked: torn vars only are
        ``nlsolve`` unknowns; interior blocks sweep forward inside
        the residual and once more after the solve to bind them."""
        tears, sweep = tear_loop(blocks)
        names, sizes = loop_layout(tears)
        total = sum(sizes)
        out.append("    function _loop%d!(r, x)  # algebraic loop %d"
                   % (loop_id, loop_id))
        off = 0
        for nm, sz in zip(names, sizes):
            out.append("        %s = x[%d:%d]"
                       % (nm, off + 1, off + sz))
            off += sz
        for b in sweep:
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("        %s = %s" % (nm, rhs))
        off = 0
        for b, nm, sz in zip(tears, names, sizes):
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            out.append("        r[%d:%d] = (%s) .- %s"
                       % (off + 1, off + sz, rhs, nm))
            off += sz
        out.append("        return nothing")
        out.append("    end")
        out.append("    _x%d = nlsolve(_loop%d!, zeros(%d))"
                   % (loop_id, loop_id, total))
        off = 0
        for nm, sz in zip(names, sizes):
            out.append("    %s = _x%d.zero[%d:%d]"
                       % (nm, loop_id, off + 1, off + sz))
            off += sz
        # bind eliminated vars at the solved tear values
        for b in sweep:
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("    %s = %s" % (nm, rhs))

    def fn_close(self) -> List[str]:
        return ["    return nothing", "end", ""]

    def output_tap(self, out, cp: CodePlan, space: CompileSpace
                   ) -> None:
        """``outs[:name] = name`` per §21 output — the optional
        ``outs`` kwarg is a side channel; the OrdinaryDiffEq call
        signature stays ``derivative!(dy, y, par, t)``."""
        out.append("    if outs !== nothing  # §21 outputs")
        for o in cp.outputs:
            nm = o.name or inst_name(o.instance)
            out.append("        outs[:%s] = %s" % (nm, nm))
        out.append("    end")

    def outputs_fn(self, out, cp: CodePlan, space: CompileSpace
                   ) -> None:
        """``outputs(y, par, t)`` — one derivative! call into a
        scratch dy, returns the recorded outputs Dict."""
        out.append("function outputs(y, par, t)")
        out.append("    outs = Dict{Symbol,Any}()")
        out.append("    derivative!(zeros(length(y)), y, par, t; "
                   "outs=outs)")
        out.append("    return outs")
        out.append("end")
        out.append("")

    def pin_term(self, st, space: CompileSpace) -> str:
        """The IC pin expression — a cells literal or a ``par`` lookup,
        used as the residual's rhs term in a non-steady solve."""
        nm = st.name or inst_name(st.instance)
        if st.ic_source == "cells":
            return '_ictab("%s")' % nm
        return "par.ic0_%s" % nm

    def constrained(self, out: List[str], cp: CodePlan,
                    space: CompileSpace) -> None:
        """The prescribed-balance block inside ``derivative!`` — a
        nested out-of-place ``_balance`` residual over the non-state
        unknowns (every runtime block contributes ``rhs .- lhs``),
        solved once via ``_solve_balance`` and unpacked; the state's
        derivative slots then drop into ``dy``."""
        spec = t0_layout(cp)
        state_names = {s.name or inst_name(s.instance) for s in cp.states}
        unknowns = [u for u in spec.unknowns if u[0] not in state_names]
        invariant, dependent = split_gathers(
            cp, {n for n, _, _ in unknowns})
        for pieces in invariant:
            out.append(self.gather(pieces[0], space) if len(pieces) == 1
                       else self.gather_multi(pieces, space))
        out.append("    function _balance(u)")
        offset = 0
        for name, size, _idx in unknowns:
            out.append("        %s = u[%d:%d]" % (name, offset + 1,
                                                  offset + size))
            offset += size
        for pieces in dependent:
            out.append("    " + (self.gather(pieces[0], space)
                                 if len(pieces) == 1
                                 else self.gather_multi(pieces, space)))
        for i, (block, term) in enumerate(spec.residuals):
            rhs = self.render_rhs(block, space,
                                  name_map(cp, block.occurrence, block.entity_type))
            out.append("        _r%d = vec((%s) .- %s)" % (i, rhs, term))
        out.append("        return vcat(%s)" % ", ".join(
            "_r%d" % i for i in range(len(spec.residuals))))
        out.append("    end")
        # :balance — callsite key for the cached finite-diff A in
        # _solve_balance (a fresh closure each call can't be hashed
        # stably; the affine u-coefficients are capture-invariant).
        out.append("    _u = _solve_balance(_balance, %d, :balance)"
                   % offset)
        offset = 0
        for name, size, _idx in unknowns:
            out.append("    %s = _u[%d:%d]" % (name, offset + 1,
                                               offset + size))
            offset += size
        for state, derivative in zip(cp.states, spec.dx):
            out.append("    dy[%d:%d] = vec(%s)" % (
                state.offset + 1, state.offset + state.size, derivative))

    def footer(self, out: List[str], cp: CodePlan,
               space: CompileSpace) -> None:
        """Emits the helpers the rendered body can reference:
        ``contract`` (the reduceSum contraction fast-path →
        ``contract(a,b,(li,),(ri,))`` codegen emits) whenever it
        appears, then ``_solve_balance`` —
        the checked-solve shim shared by the constrained ``_balance``
        and the t=0 solve: a consistency check at size 0, convergence
        + residual bound otherwise.  The underdetermined-rank guard
        the other dialects emit is skipped — NLsolve does not return
        a Jacobian."""
        if any("contract(" in l for l in out):
            # generic tensor contraction: permute the contracted axes
            # to a's end / b's front, reshape to a matmul, reshape
            # back to the remaining axes (1×1 when all contract).
            out += ["function contract(a, b, da, db)",
                    "    ca = collect(da); cb = collect(db)",
                    "    fa = setdiff(collect(1:ndims(a)), ca)",
                    "    fb = setdiff(collect(1:ndims(b)), cb)",
                    "    A = reshape(permutedims(a, vcat(fa, ca)), :,",
                    "                prod(size(a)[ca]))",
                    "    B = reshape(permutedims(b, vcat(cb, fb)),",
                    "                prod(size(b)[cb]), :)",
                    "    dims = (size(a)[fa]..., size(b)[fb]...)",
                    "    return isempty(dims) ? A * B : "
                    "reshape(A * B, dims)",
                    "end"]
        if not cp.constraints:
            return
        # Emitted balance residuals are affine in u — and can be
        # overdetermined (nlsolve is square-only).  Affine fast-path:
        # a finite-difference A built once per callsite key, then
        # u = -(A \ r0) — backslash is QR least-squares when
        # length(r) > count — plus one residual verify.  Verify-fail
        # or rank-deficiency demotes: underdetermined → hard error
        # (mirrors the other dialects), square → nlsolve fallback,
        # non-square nonlinear → no Julia solver — explicit error.
        out += ["const _BAL_CACHE = Dict{Any, Any}()",
                "function _solve_balance(fun, count, key)",
                "    if count == 0",
                "        u = zeros(0); r = fun(u)",
                "        (all(isfinite, r) && all(abs.(r) .<= 1e-8)) "
                "|| error(\"inconsistent prescribed balance\")",
                "        return u",
                "    end",
                "    cached = get(_BAL_CACHE, key, nothing)",
                "    cached === :nonlin && "
                "return _nlsolve_balance(fun, count)",
                "    r0 = fun(zeros(count))",
                "    n = length(r0)",
                "    if cached === nothing",
                "        cached = zeros(n, count)",
                "        for k in 1:count",
                "            ek = zeros(count); ek[k] = 1.0",
                "            cached[:, k] = fun(ek) .- r0",
                "        end",
                "        _BAL_CACHE[key] = cached",
                "    end",
                "    A = cached",
                "    if rank(A) >= count",
                "        u = -(A \\ r0)",
                "        r = fun(u)",
                "        (all(isfinite, r) && all(abs.(r) .<= 1e-8)) "
                "&& return u",
                "    else",
                "        error(\"prescribed balance system is "
                "underdetermined\")",
                "    end",
                "    n == count || error(\"prescribed balance: "
                "nonlinear overdetermined system — unsupported\")",
                "    _BAL_CACHE[key] = :nonlin",
                "    return _nlsolve_balance(fun, count)",
                "end",
                "",
                "function _nlsolve_balance(fun, count)",
                "    res = nlsolve(fun, zeros(count))",
                "    r = fun(res.zero)",
                "    (NLsolve.converged(res) && all(isfinite, r) && "
                "all(abs.(r) .<= 1e-8)) "
                "|| error(\"prescribed balance solve failed\")",
                "    return res.zero",
                "end"]

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
        invariant, dependent = split_gathers(
            cp, {n for n, _, _ in spec.unknowns})
        for pieces in invariant:
            out.append(self.gather(pieces[0], space) if len(pieces) == 1
                       else self.gather_multi(pieces, space))
        out.append("    function _t0(u)  # t=0 residual system")
        off = 0
        for nm, sz, _idx in spec.unknowns:
            out.append("        %s = u[%d:%d]" % (nm, off + 1, off + sz))
            off += sz
        out.append("        if steady_state")
        out.append("            total_diff = (x, y) -> x .* 0  "
                   "# der = 0")
        out.append("        end")
        for pieces in dependent:
            out.append("    " + (self.gather(pieces[0], space)
                                 if len(pieces) == 1
                                 else self.gather_multi(pieces, space)))
        for b in spec.guesses:
            nm = b.lhs_name or inst_name(b.lhs_instance)
            out.append("        x0 = %s  # root! guess" % nm)
        for i, (b, term) in enumerate(spec.residuals):
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            out.append("        _r%d = vec((%s) .- %s)" % (i, rhs, term))
        out.append("        _rs = Any[%s]" % ", ".join(
            "_r%d" % i for i in range(len(spec.residuals))))
        out.append("        if steady_state")
        out.append("            append!(_rs, Any[%s])  # der = 0"
                   % ", ".join("vec(%s)" % n for n in spec.dx))
        out.append("        else")
        ne = 0
        for b, term in spec.initials:
            rhs = self.render_rhs(b, space,
                                  name_map(cp, b.occurrence, b.entity_type))
            out.append("            _e%d = vec((%s) .- %s)  # initialise"
                       % (ne, rhs, term))
            ne += 1
        for st in spec.pins:
            nm = st.name or inst_name(st.instance)
            out.append("            _e%d = vec((%s) .- %s)  # IC pin"
                       % (ne, self.pin_term(st, space), nm))
            ne += 1
        out.append("            append!(_rs, Any[%s])" % ", ".join(
            "_e%d" % i for i in range(ne)))
        out.append("        end")
        out.append("        return isempty(_rs) ? zeros(length(u)) : "
                   "vcat(_rs...)")
        out.append("    end")
        if cp.constraints:
            # (:t0, steady_state) — the flag changes _t0's residual
            # set, so it must key the cached finite-diff A too.
            out.append("    _u = _solve_balance(_t0, %d, "
                       "(:t0, steady_state))"
                       % sum(sz for _, sz, _ in spec.unknowns))
        else:
            out.append("    _u = nlsolve(_t0, zeros(%d)).zero"
                       % sum(sz for _, sz, _ in spec.unknowns))
        y_names = {s.name or inst_name(s.instance) for s in cp.states}
        off = 0
        for nm, sz, _idx in spec.unknowns:
            if nm in y_names:
                out.append("    %s = _u[%d:%d]" % (nm, off + 1,
                                                  off + sz))
            off += sz
        # vcat, not […] — Julia [x] nests (Vector{Vector}), Matlab
        # [x] concatenates; the solver wants the flat y0 vector.
        out.append("    return vcat(%s)" % y0)
        out.append("end")
        out.append("")


def emit_julia(cp: CodePlan, space: CompileSpace) -> str:
    """Emit the in-place derivative function for a code plan."""
    return emit_plan(cp, space, _Julia())


def julia_project(src: str) -> str:
    """The bundle's ``Project.toml`` — the package deps of the emitted
    ``src`` so ``run.jl`` can ``Pkg.instantiate()`` them.  Scanned
    rather than declared unconditionally: NLsolve/JSON only appear in
    the header when the model needs them, and Integral blocks render
    ``quadgk(...)`` — a real package dep.
    SparseArrays is stdlib but must still be listed once a project
    environment is active."""
    lines = ["[deps]",
             'SparseArrays = "2f01184e-e22b-5df5-ae63-d93ebab69eaf"']
    if "using LinearAlgebra" in src:
        lines.append('LinearAlgebra = '
                     '"37e2e46d-f89d-539d-b4ee-838fcccc9c8e"')
    if "using JSON" in src:
        lines.append('JSON = "682c06a0-de6a-54ab-a142-c8b1cf79cde6"')
    if "using NLsolve" in src:
        lines.append('NLsolve = "2774e3e8-f4cf-5e23-947b-6d7e65073b56"')
    if "quadgk(" in src:
        lines.append('QuadGK = "1fd47b50-473d-5c70-9696-f719f8f3bcdc"')
    return "\n".join(lines) + "\n"


def julia_run_script(name: str, cp: CodePlan) -> str:
    """A runnable driver emitted beside ``<name>.jl``: activate the
    bundled Project.toml (first run resolves + precompiles NLsolve/
    JSON, afterwards a cached no-op), include the model, then the t=0
    initialisation and a fixed-step RK4 integration — no ODE-package
    dependency, keeping the environment small."""
    params = ", ".join(p.name for p in cp.params) or "none"
    lines = [
        "# %s — generated driver (run: bash run_julia.sh)." % name,
        "# First run instantiates the bundled Project.toml; afterwards",
        "# Pkg.instantiate() is a cached no-op.",
        "using Pkg",
        "Pkg.activate(@__DIR__)",
        "Pkg.instantiate()",
        "",
        'include(joinpath(@__DIR__, "%s.jl"))' % name,
        "",
        'par = Dict{String, Float64}()  # parameter keys: %s' % params,
    ]
    if cp.states:
        lines += [
            "# t=0 from the prescribed ICs.  initial(par; steady_state=true)",
            "# instead solves for a der=0 steady state — only for models",
            "# that have one (a pure integrator does not).",
            "y0 = initial(par; steady_state=false)",
            "",
            "# Plain fixed-step RK4 — OrdinaryDiffEq would add adaptivity",
            "# but a much bigger dependency tree.",
            "t0, t1, n = 0.0, 1.0, 101",
            "t = collect(range(t0, t1; length=n))",
            "dt = (t1 - t0) / (n - 1)",
            "y = copy(y0)",
            "traj = zeros(length(y), n)",
            "traj[:, 1] .= y",
            "for k in 1:n-1",
            "    k1 = similar(y); k2 = similar(y)",
            "    k3 = similar(y); k4 = similar(y)",
            "    derivative!(k1, y, par, t[k])",
            "    derivative!(k2, y .+ (dt / 2) .* k1, par, t[k] + dt / 2)",
            "    derivative!(k3, y .+ (dt / 2) .* k2, par, t[k] + dt / 2)",
            "    derivative!(k4, y .+ dt .* k3, par, t[k] + dt)",
            "    y .+= (dt / 6) .* (k1 .+ 2 .* k2 .+ 2 .* k3 .+ k4)",
            "    traj[:, k + 1] .= y",
            "end",
            'println("t: ", round.(t[1:10:end]; digits=3))',
            'println("y: ", round.(traj[:, 1:10:end]\'; digits=6))',
        ]
    else:
        lines += ["# no states — call the derivative directly:",
                  "# dy = zeros(0); model.derivative!(dy, y, par, 0.0)"]
    return "\n".join(lines) + "\n"


def julia_shell_script() -> str:
    """``run_julia.sh`` — a cwd-independent launcher emitted beside
    ``run.jl``.  Julia's own Project/instantiate machinery covers the
    dependencies, so the shell side only needs to find julia."""
    return '''#!/usr/bin/env bash
# run_julia.sh — run the emitted model driver (run.jl) from anywhere.
# The bundled Project.toml declares the model's packages; run.jl
# calls Pkg.instantiate() — the first run resolves and precompiles
# them, afterwards it is a cached no-op.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v julia >/dev/null 2>&1 || {
    echo "run_julia.sh: julia not found — install it (julialang.org)" >&2
    exit 1
}
exec julia "$HERE/run.jl" "$@"
'''
