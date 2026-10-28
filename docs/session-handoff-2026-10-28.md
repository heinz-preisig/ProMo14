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

### Output channel in codegen (same day, commit pending)

§21 outputs are now plumbed end to end: `EntityInstantiation.outputs`
(from the assignment) → `CodePlan.outputs` (`OutputSlot`) → emitted
output channel per dialect — python `derivative(t, y, par, out=None)`
records `out["name"] = name` plus an `outputs(t, y, par)` wrapper;
julia `derivative!(...; outs=nothing)` + `outputs(y, par, t)`; matlab
`[dy, outs]` multi-return (`.value` unwrap).  The ODE signatures stay
backward-compatible — the channel is optional everywhere.  `/model`
exposes `entity_types[].outputs`.

## Where to pick up — candidate queue

1. ~~Re-save legacy assignments~~ — done above; `data/assignments.trig`
   is §21-canonical.
2. Composites/reuse semantics (design-discussion §8; codegen
   approach 2).
3. Direction-aware donor selection for chained port `c` (§15).
4. Deferred: cross-artefact consistency review.  (~~ν→codegen
   wiring~~ — stale: landed 2026-09-24, verified 2026-09-28; cells
   reach the emitters via `ParamSlot.values` → `model_data.json`.)
