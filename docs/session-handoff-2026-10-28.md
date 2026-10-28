# Session handoff — 2026-10-28

## What was done

Implemented the **§21 move-based Behaviour Linker engine** end to end —
the open item from the 2026-10-27 design session. Backend rewrite +
persistence + service endpoint + SPA rewiring + tests; full suite
**421 passed**, SPA `dist` rebuilt.

### Backend — `backend/behaviour/`

- `closure.py` rewritten around **`apply_move(equations, sel, kind, …)`**
  → `_reclose` → `evaluate`.  Move kinds: `pick_base` (unpick keeps the
  equation so the integrator loop surfaces as a reported cycle),
  `pick` (a definer choice; same-variable pick = *exchange*, clears
  instantiated/port marks, keeps output), `delete` (consumers reopen;
  the deleted equation's exclusive provider cone prunes),
  `mark`/`unmark` (roles exclusive; marking instantiated/port drops
  the definer), `reorder` (desired sequence = position hints only).
- `_reclose` restores the invariant per move: drop unknown/dup
  equations → definer wins over stale marks → prune to **root cone**
  (base + definers of declared outputs; stateless selections add
  their unconsumed-lhs tips) → `pick`/`mark` auto-pull
  uniquely-definable definers → stable topological order (base last,
  state edges exempt; non-state cycles appended + reported).
- New endpoint kind **output** (`Selection.outputs`): an external
  sink — must be defined, its definer is a reachability root,
  unmatched outputs join `unresolved` with `as_output` and their
  candidates join the `frontier` unconditionally.  `evaluate` also
  reports `unconsumed` (defined non-state vars nothing consumes, no
  output claims) — they now **block `closed`**: a stateless entity's
  outputs are its interface.
- `service.py`: `SelectionIn`/`AssignmentOut.outputs`,
  `promo:hasOutputVariable` persisted on the artefact, new
  **`POST /api/behaviour/move`** returning
  `{selection, report, pulled, pruned}`; `PUT /assignment` now
  re-closes via a `reorder` move before persisting (stored artefacts
  are always canonical — topological order, base last, pruned).
- `instantiate/builder.py`: `AssignmentInfo.outputs` carried through
  `_assignments_collect` (artefact completeness; port donor logic
  unchanged — outputs are already defined vars in `peer_defined`).

### Frontend — `apps/behaviour-linker/`

- `useBehaviourLinker.ts`: every mutation is a serialized `/move`
  call (promise chain prevents interleaving); responses apply the
  canonical selection + report and flash pulled/pruned equation ids.
  Loading an entity type sends a `reorder` move — legacy artefacts
  normalize in one roundtrip.
- UI: per-row **out** toggle on sequence rows, outputs row +
  `output…` select in the roles panel, `unconsumed` hint row with
  one-click output marks, `(output)` badge on unresolved output
  demands, outputs line in the printable LaTeX.

### Tests / docs

- `test_closure.py` — 40 tests (12 new §21 move tests + `/move` and
  `hasOutputVariable` roundtrips).
- `test_builder.py` fixtures updated: donated variables declare
  `outputs` (`p` → effort port donor, `J` → exported transport flow).
- `docs/behaviour-linker-status.md` — §21 marked implemented, engine
  described as move-based.

## Semantics decisions taken

- **Delete reopens dependents** (does not cascade through consumers);
  only the deleted equation's exclusive *provider* cone prunes.
- **Marks vs definitions:** the last move wins — `pick` clears
  endpoint marks, `mark instantiated/port` drops the definer; a
  definer beats stale loaded marks during reclose.
- **Auto-pull:** `pick`/`mark` recursively pull in variables with
  exactly one candidate equation (no choice to offer); `reorder`/
  `delete` never pull.
- **Unconsumed tips block `closed`** — dead code for based entities,
  undeclared outputs for stateless ones.

## Migration note

Pre-§21 artefacts (e.g. `data/assignments.trig` stateless transports
without output marks, or with dead-code equations) may read stale
`closed` flags / sequences — the first `reorder` (SPA load or PUT)
re-closes and shows *modified* until re-saved.  No manual `.trig`
edits — re-save via the app.

**Audited + re-saved 2026-10-28:** all 3 stored assignments checked
via dry-run `reorder` + `evaluate`.  `etype_lumped` and
`etype_environment` were already canonical and closed; no output
marks needed anywhere (every defined var is consumed internally).
`etype_convection_transport` was re-PUT — only drift was sequence
order (base was first); now canonical `[E_11, E_12, E_15, E_16]`,
still `closed`.  The audit also caught an engine bug — unknown
equations were kept instead of pruned, then crashed the dedupe pass;
fixed with a regression test.

### Output channel in codegen (same day)

§21 outputs are now plumbed end to end: `EntityInstantiation.outputs`
(from the assignment) → `CodePlan.outputs` (`OutputSlot`) → emitted
output channel per dialect — python `derivative(t, y, par, out=None)`
records `out["name"] = name` plus an `outputs(t, y, par)` wrapper;
julia `derivative!(...; outs=nothing)` + `outputs(y, par, t)`; matlab
`[dy, outs]` multi-return (`.value` unwrap).  The ODE signatures stay
backward-compatible — the channel is optional everywhere.  `/model`
exposes `entity_types[].outputs`.

## End-of-day update

- **Indexed powers fixed:** the checker takes the ordered union of base
  and exponent indices. Activity kinetics `a[S] ^ alpha[Q,S]` therefore
  has indices `[S,Q]`, and `Product(a ^ alpha, S)` leaves `[Q]`.
- **Axis alignment:** Python/NumPy and Julia code generation permute
  dense operands into result-index order and insert singleton axes for
  indexed powers and index-preserving products. Matlab continues to use
  label-aware `MultiDimVar` operations.
- **Value fills:** wildcard and sub-index selectors, coverage badges,
  fill editing and per-binding problem badges are implemented. `/model`
  runs `plan()` so bad-fill/fill-conflict problems reach the report.
- **Design decision:** expression-valued cells were implemented and then
  reverted (`e1ca09e`). Instantiation carries literal numbers only;
  equations carry all relations. Computed values and initial conditions
  belong in equation definitions (initialise-class equations for ICs),
  not in cell expressions. The equation language remains symbolic, with
  no numeric literals. `docs/value-expression.md` is currently empty;
  this handoff records the rejection.
- **Validation:** `uv run pytest backend/equation -x -q` — **198 passed**;
  `uv run pytest backend/ -x -q` — **428 passed**. Dependency deprecation
  warnings remain; `git diff --check` is clean. The final indexed-power
  changes are backend-only; no frontend rebuild is required for them.

## Evening design session — §22 referenced composites

Composite/model-reuse semantics settled with the user and recorded as
**§22** in `behaviour-linker-design-discussion.md`.  Decisions:

- **Refer, don't copy** — `refersTo` + per-occurrence override map on
  the composite; live reference gives propagating fixes; copy exists
  already as hub Fork.
- **Interface declared in the referenced artefact** — its open arcs
  (arc type + token + §15 direction) surface as connectable terminals;
  `resolve-connection` adjudicates host↔terminal links.
- **Per-occurrence instantiation** — use-site keyed; instance paths
  `comp/inner@frag`; effective context = submodel pins + overrides
  (must cover the submodel's placements/symbols); species crossing a
  port checked on both sides; host `promo:Instantiation` nests one
  sub-plan per occurrence; codegen stays call-style.
- **Modification menu** — parameterize (overrides) / edit the artefact /
  fork + re-point / **dissolve** (one-way flatten to inline content,
  external arcs remap onto copied terminals, `dissolvedFrom`
  provenance).  Host-side structural overlays rejected.
- Gestures: save-as-composite, library pick (interface summary),
  insert, connect, override, dissolve.  Open: predicate name,
  copy-vs-move on extraction, frozen-reference pin shape.

## Where to pick up — candidate queue

1. ~~Re-save legacy assignments~~ — done above; `data/assignments.trig`
   is §21-canonical.
2. Composites/reuse — **designed 2026-10-28 as §22** (referenced
   composites: `refersTo` + override map, open-arc interface,
   per-occurrence instantiation, dissolve/fork for modification).
   Implementation is the next step.
3. Direction-aware donor selection for chained port `c` (§15).
4. Deferred: cross-artefact consistency review.  (~~ν→codegen
   wiring~~ — stale: landed 2026-09-24, verified 2026-09-28; cells
   reach the emitters via `ParamSlot.values` → `model_data.json`.)
