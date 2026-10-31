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
  --disable-warnings`: **476 passed** (2 new `sub_plan_slice` tests).
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

## Open threads

1. **§22 Jacobian remainder (if wanted)** — emit the block-level
   sparsity (`jac_prototype`/coloring) or DM-style matching for
   tear selection; ordering is done, pattern/matching is not.
2. **§22 remainder** — bundle render, gas/pipe+regen on real
   assignments, cross-artefact review.
3. **`unreachable` live check** — needs a controller/sensor model
   (deferred).
4. Broader deferred work per 2026-10-30 handoff (token/port policy,
   `token_space` question, `carriesToken`-for-port policy, §14
   signal direction, cross-artefact review).
