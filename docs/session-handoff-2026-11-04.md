# Session handoff — 2026-11-04

## §31 boundary semantics — implemented and verified on test_01

The port-coverage/initial-solve chain is closed. `POST /instantiate/initial`
on test_01 returns `ok:true` at t=0; `problems: []`; 347 tests pass.

**Concept (user, now baseline):** everything is a system; arcs are boundary
couplings, not things. Transport = `event-dynamic` = stateless (no interior,
no balance eq) — `temporalType` is now load-bearing in instantiation.
Coupling is a *shared* variable, eliminating cut equations in both domains
(physical: effort/flow continuity; signal: output IS the input).

### Machinery

- `builder.py` `contacted_elements` — port vars on `event-dynamic` entities
  bind contacted peer elements (contact order = incident-arc order).
  `service._collect` threads `temporalType` into `build_model` (both call
  sites). Emit stays pure gather-concat.
- **Seam resolved = arc-indexed var**: `*` contracts by *declared* index IRI
  only (checker never sees bound elements), so driving-force operands must be
  arc-typed. New `V_59 p_conv [idx_arc_convection]` (effort axis,
  `token_momentum` → token-comparable to `p_mech`) resolves per-contact to
  peers' `p_mech`. `p_mech` stays `[N]` on capacities.
- **Broadcast emit** (`emit_common.render_rhs` + `emit_python.broadcast`):
  rhs index set ⊂ lhs index set with matching shared extents → reshape +
  `broadcast_to` over the lhs's extra axes. `[N]` drop → `[A_conv,N]`
  repeats the same flow on both contacts. matlab/julia raise `VarError`
  until exercised.

### Content edits (data/*.trig)

- `V_59 p_conv` added to `ontology.trig`; ct assignment port `V_34 → V_59`.
- `E_4` = `(kConvX . Ayz) . (p_conv * F_conv)` — `e @ F` contracts `A_conv`
  → `+p_N1 − p_N3` = the drop per transport node.
- `E_29` = `reduceSum(F_conv . fmc, A_conv)` — the balance is the *net* rate
  per node. Root cause of the persistent `gtol`: elementwise `F . fmc` read
  the `V_57=0` cells on the transport as "each contact's flow = 0",
  contradicting `fmc = kA·4`. As net-rate it is the correct stateless
  constraint — and it also enforces `fmc_1 = fmc_2` when per-arc `kA`
  ever differ.
- `E_11` — stale `p_mech` → `p_conv` (orphaned `d` var; still coherent).

### Editing .trig directly — notes

Canonicals read the `rhsExpression` AST, not the `rhs` string: Expression
bnodes, `hasOperation promolg:X`, `hasArguments` = rdf list, index args =
bare index IRI leaf. Backend loads data files at boot — `./dev.sh restart
backend` to pick up.

## Deferred / open

- `matlab/julia` `broadcast` stubs raise — implement when those dialects
  are emitted.
- `E_28` has the same `F_heat * T` seam — needs a `T_heat [A_heat]` boundary
  var when a heat model is authored (mechanical pattern now).
- `VariableDetailDialog` two-column layout — user's older request, pending.
- `contacted_elements` node-extent rule unused by test_01 (V_59 binds via
  the arc-indexed path) — kept as the general rule for future node-indexed
  ports on event-dynamic entities (e.g. carried concentration `c [N,S]`).
