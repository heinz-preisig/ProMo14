# Session handoff — 2026-10-31

## What shipped today

### Missing Ports panel — root cause: stale build

The `test_01` model's connect gesture showed valid arc types but no
Ports section.  Every code path was verified correct (session `graph`
param, hover wiring, fetch construction, render gating, live replay
of the exact request returns nonempty ports both sides).  The actual
cause: **`apps/modeller/dist/` held a bundle from Oct 16**, predating
both port-satisfaction commits (`7009d67`, `d7df7c5`) — the hub
serves that directory.  `./dev.sh build modeller` produced a fresh
bundle; the feature works now.  Note for both machines: `dist` is
synced/committed, so a repo sync can silently roll back a build —
rebuild after pulling.

### `unreachable` semantics clarified (no code change)

`unreachable` applies only to **unidirectional** arcs (signal/
reference rules — sensor reads, actuation writes): a source-side
port demand that would need feeding backwards reports `unreachable`
("one-way arc cannot feed source").  Physical token-flow arcs keep
bidirectional adjudication — the §15 reference direction is a sign
convention, not a flow restriction.  Live verification deferred
until a controller/sensor-style model exists (`test_01` has no
licensed signal demand to exercise it).

### §22 nested `promo:Instantiation` sub-plans + pin provenance

- `plan.sub_plan_slice(cp, path)` — the per-occurrence slice:
  slots/blocks owned **directly** by the path (nested occurrences
  own their own content — deeper prefixes excluded), nested
  occurrence registry carried over, loops survive only when fully
  inside the slice (coupling loops belong to the host).
- `_occurrence_contexts` records each occurrence's effective pins
  (`library`/`assignment`/`species`/`values`) on `occ["pins"]`;
  `plan()` carries them into `cp.occurrences`.
- `POST /api/instantiate/instantiations` writes one nested
  `promo:Instantiation` per occurrence: `hasSubPlan` link,
  `occurrencePath`, `instantiates` → referred artefact, `overrides`
  JSON, pin provenance (`usesLibrary`/`usesAssignment`/
  `usesSpecies`/`usesValues`), own sliced `promo:plan` JSON.
- New vocabulary declared in `graph_store.py`: `hasSubPlan`,
  `occurrencePath`, `instantiates`, `overrides`, `usesValues`.
- §22 status in `behaviour-linker-design-discussion.md` annotated —
  call-style codegen was already in the emitters (`occ_fns`,
  level-parallel spawn/fetch, cone-blocked `tear_loop`).

## Verification

- `uv run --with pytest --with httpx pytest backend/ -x -q
  --disable-warnings`: **478 passed**.
- Modeller rebuild: `tsc` + `vite build` clean.

### §22 ordinal-aware tear ordering

`_tear_order` (emit_common) sequences the iterated unknowns by
their intra-torn dependency DAG — a tear consumed by another
tear's residual comes first, so the solver Jacobian is block-
triangular wherever the torn structure allows.  Sequencing is over
the SCC *condensation*: mutually dependent tears stay adjacent as
one dense diagonal block.  Applies uniformly to all three emitters
via `tear_loop`.  **Bug caught by test**: `_sccs` returns only
non-trivial components — singleton tears needed re-adding as
their own components or the solve emptied (`np.zeros(0)`).

### §22 interface summary in library pick

Submodels palette buttons lazily fetch the artefact's root open
arcs on first hover (`loadModelDoc`) and render a compact summary —
`→/← arcType · entityType` per terminal, `closed — no declared
terminals` for closed artefacts.  Modeller `tsc`/vite build clean,
35 vitest tests pass; **rebuilt `dist` is served by the hub —
refresh the browser to see it.**

### §22 end-to-end referenced-composite validation

`test_referenced_composite_endpoint` builds two real model artefact
graphs in an isolated store (host with `refersTo` composite +
`openArcs`, sub with transport+capacity) and exercises
`/model` → `/code` → `POST /instantiations`.  Validates: occurrence
content merged under `comp/` prefix, boundary arc re-pointed, ports
bound across the boundary, nested sub-plan persisted with
`occurrencePath`/`instantiates`/pin provenance.

**Bug found + fixed**: `PlanBlock.occurrence` was derived from
`vb.instance` (`V_1@etype_...` — no path prefix) so every block
reported `occurrence=""`.  `_occ_of_elements` attributes blocks by
bound element IRIs instead.

**Deeper finding — Option A deferred**: with a shared library the
merge unions bindings by var/entity-type IRI, so bindings span the
boundary (transport `J` covers host b1 + sub a2; capacity `m`/`p`
cover host c1 + occurrence c2) → no block is occurrence-owned →
sub-plan slice empty and call-style helpers inert.  User chose
Option A (split entity bindings per occurrence — `comp/inner@frag`
instances) but **deferred it until a real referenced-composite
case exists**; building the case needs authored gas/pipe equations
(user content).  Test documents the current empty-slice semantics.

## Open threads

1. **§22 Option A — per-occurrence binding split** (deferred,
   user-approved direction): split `VarBinding`s so occurrence
   nodes get path-keyed instances; unblocks non-empty sub-plans
   and call-style helper extraction.  **Blocked on**: a real
   referenced-composite example (gas/pipe+regen) — needs authored
   equations; `extract-submodel` can produce the structure once
   content exists.
2. **§22 Jacobian remainder (if wanted)** — emit the block-level
   sparsity (`jac_prototype`/coloring) or DM-style matching for
   tear selection; ordering is done, pattern/matching is not.
3. **§22 remainder** — bundle render, cross-artefact review.
4. **`unreachable` live check** — needs a controller/sensor model
   (deferred).
5. Broader deferred work per 2026-10-30 handoff (token/port policy,
   `token_space` question, `carriesToken`-for-port policy, §14
   signal direction, cross-artefact review).
