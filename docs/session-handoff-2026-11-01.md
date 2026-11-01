# Session handoff — 2026-11-01

## What was done

### §26 variable-IRI migration — shipped and closed out

- **`06976be`** — the §26 migration itself: instance IRIs are absolute
  and artefact-scoped (`{graph}#name` variables, `{graph}Node_/Arc_`
  model records, `promo#ArcType/<carrier>`). `_migrate_variable_iris`
  rehomes relative `promo:X` spellings, consolidates split records
  (ontology graph wins home, richest record wins literals), rewrites
  URIRef objects and `promo:` tokens inside JSON literals. All 25
  stored equations check in every scope; 0 relative URIs in data.
- **`7c72b10`** — residue: placeholder catalogue + modeller palette
  defaults to absolute `promo#` spellings.
- **`5b79f32`** — **new `_heal_vocab_ns_refs` load step** (after
  `_migrate_incidence_factors`, before `_migrate_canonical_rhs`): a
  `promo#X` reference with no subject is repointed to the unique
  same-local-name artefact subject, or the stale role claim is
  stripped (variable deleted). `rdf:first` members repoint but never
  drop; vocab refs and non-role predicates are out of scope. Real
  data: `promo#F_conv` → `ontology#F_conv` across assignment roles,
  canonical argument lists and `incidenceList` literals; dead
  `c`/`rho`/`fn_conv` role claims stripped. **Zero dangling instance
  refs across all graphs.**

### No-legacy rule + full code review

- **`a97de3c`** — `templates/legacy/` deleted; user rule: *no legacy
  code — this is a starting point for the new system*.
- **`bc119f5`** — `core/gestures.py` → `core/capabilities.py` (it is
  the §20 capability-gate, not UI gestures); dead `ensure_data_dir` +
  `UNIT_FIELDS` out.
- **`d997936`** — dead code in `backend/equation`: 3 unraised
  exceptions, 2 dead parser helpers, unused `get_variable`.
- **`7a30524`** / **`3f439b1`** / **`8a43851`** — dead `_str` helper,
  `arc_carrier` docstring and IRI-example comments to §26 spelling.
- **`3c19677`** — `ontology-data-model.md` seed spelling + stale
  "never migrated" claim; `dev:ontology` script added (all six apps
  now have root dev scripts).
- Reviewed everything: backend all modules, packages, all six apps
  (incl. `species` + `instantiation`), docs, dev scripts. Verdict:
  tight — only the two app monoliths (`ontology-editor/App.tsx` 1045,
  `instantiation/App.tsx` 870) flagged as optional future splits.

### Design discussion outcomes

- **Incidence matrices of event-dynamic transport systems** — the
  historical problems were IRI chaos (F_* spelling/duplicates), the
  §17 regime-binding flip (transport_system was molecular-event at
  point length), missing reference directions, and the E_11
  contraction form — all now settled. Residual: no regime gate in
  `fbuilder.py` (membership is type-driven) and **no event-dynamic
  transport system exists in data yet**, so that path is untested.
  If it matters, write a design note on whether event-dynamic
  transport participates in conservation incidence at all.
- **"Extend the modelling domain"** — clarified as *authoring
  content*, not extending the bipartite graph. The var/expr bipartite
  structure is regime-agnostic; extension should follow real cases,
  not speculation.

## Tomorrow's plan: energy + heat/mass transfer + basic control

Everything needed is **already seeded** — this is authoring work:

- Energy: `etype_energy_transport` → `etype_heat/radiation/work_transport`,
  `A_heat`/`A_rad`/`A_work` sub-indices, `F_heat`/`F_rad`/`F_work` factors.
- Mass: `etype_mass_transport` → diffusion + convection, `F_diff`/`F_conv`.
- Control layer: `rule_sensor` (physical→info, `token_observation`),
  `rule_signal` (info↔info), `rule_actuation` (info→physical,
  `token_manipulation`), `rule_access`; `etype_info_constant/dynamic/event`.
- Signal arcs are `reference` carrier → correctly excluded from F.

Suggested order:

1. **Author energy equations** (exercises `F_heat`/`A_heat` in scope):
   `dU/dt = F_heat·q + F_conv·(ṁ·h)`, conduction `q = -k·A·ΔT`,
   convection enthalpy `ṁ·h(T)`, radiation `σ·A·(T⁴-T₀⁴)`.
2. **Draw the model** — lumped capacity + heat/convection arcs +
   info entities wired by sensor/signal/actuation arcs.
3. **Control last** — sensor readout (output role), controller law
   on `info_dynamic` (`u = K_p·e`, `e = r - y`), actuation mapping
   `u` → manipulated physical term. Setpoint = `input` role.

Watchpoints: the `ṁ·h` coupling term is user physics (no machinery
gap, but it is what makes "combined" real); multi-component mass
transfer pulls in §20 species machinery; control variables resolve
via `network!label` in the information domain. The signal-rule path
is seeded but **never exercised in a real model** — expect the first
control loop to surface seams.

## State

- 493 backend + 26 semantic tests pass; both apps `tsc` clean.
- All work committed and pushed: `06976be` … `5b79f32` (10 commits).
- Main queue after content work: **§21 closure rewrite to
  invariant-restoring moves** (evaluate-driven → pick/exchange/
  delete/unmark-output), plus `promo:hasOutputVariable` persistence
  and delete cascade-vs-reopen UX (design-gated).

---

# Evening session — §26 IRI system normalized, §27 composition

## What was done

### IRI construction centralized (single source per language)

- **`backend/core/iri.py`** (new) + **`packages/semantic/src/iris.ts`**
  (new): every IRI shape has a named constructor. Two joins:
  `vocab_iri` = `{base}#{frag}` (vocabulary members), `child_iri` =
  `{base}/{seg}` (subordinate resources).
- Server owns minting: `POST /variables` with `iri:''` returns
  `{graph}#V_n` minted from the **store's own counter** (client's
  `nextInternalId` guess ignored — could collide). `arc_type_iri` is
  server-synthesised on rule records.
- Clients mint only whole-document topology IDs (`modelNodeIri`,
  `modelArcIri`, `speciesMemberIri`) via the shared helpers.

### Normalization — the grammar is now uniform

- **Artefact graph IRIs are slash-free names** (`…/library`,
  `…/model`, `…/ontology`). `_normalize_graph_iris` runs first in
  `load()`: trailing-slash identifiers rename, pins/`versionOf`/
  `refersTo` follow (incl. inside frozen graphs), `{old}#x` members
  rehome. `deps.py` normalizes `?graph=` via `canonical_graph_iri`.
- **`concat_iri` deleted** — Node/Arc mint via `child_iri`
  (`{graph}/Node_n`); the `test-modelNode_3` seam is gone.
- **Variables key on internal ID** — `{graph}#{internal_id}`, not
  label: rename-stable identity, labels are data. `_migrate_variable_iris_keyed`
  rehomes label-IRIs, rewriting refs + literal tokens.
- **Seed records get deterministic internal IDs** (`const_zero`,
  `F_{mech}`) — `{graph}#{iid}` reproduces their readable IRIs, so
  the convention stays uniform with zero special-casing.
- Verified on a copy of real data: `library/#x` → `library#V_n`,
  `const_*`/`F_*` intact, **zero non-conforming variable IRIs**,
  filenames stable.

### §27 — ontology composition (documented)

- **Artefacts compose via pins; nothing merges.** `resolution_scope`
  walks the transitive `usesOntology`/`usesLibrary` closure (BFS,
  cycle-safe) — already implemented, now specified + tested.
- `usesAssignment`/`usesSpecies`/`usesModel` are resource pins,
  consumed by their own services — excluded from vocabulary scope.
- Alignment deferred: mapping artefact (`promo:equivalentTo`) + rule
  resolver expansion, when a second ontology actually exists.

## State

- **502 backend + 26 semantic tests**; all workspaces `tsc`+vite clean.
- `data/` on disk still holds old spellings — converges on next
  save after server restart (in-memory migration is verified).
- Equation authoring can proceed: new variables mint `#V_n`.

## Test invocations

```bash
uv run --with pytest --with httpx pytest backend/ -x -q
(cd packages/semantic && npm test)   # vitest
(cd apps/modeller && npx tsc --noEmit)
```

# Late evening — save/delete path bugs found during energy authoring

## What was done

- **Root cause of the phantom §18 409s (mu/V_35):**
  `next_internal_id` scanned only `self.ontology_graph` for `internalID`
  literals — blind to `V_1..V_54` living in the *library* graph.
  Ontology's max is `V_34`, so a "New dependent variable" POST
  (`iri: ''`) minted `V_35` (= `mu`), then `V_36` — existing subjects.
  The create became an overwrite of the victim's record → guard 409'd
  with `units`/`index_structures`/`alias:global_ID` — and silently
  *saved* `mu` from being replaced. Fix: scan **all** named graphs in
  `graph_store.py:424` → now mints `V_55+`. Verified live.
- **`delete_variable` 404 "Variable not found":** required the subject
  in the UI-selected graph; ontology-living variables (e.g. `F_mass`)
  shown via resolution scope could never delete. Now resolves the
  owning graph by scanning `dataset.graphs()` for subject membership,
  preferring non-frozen (`service.py:1162`).
- **`_structural_changes` `global_ID` false positive:** absent alias
  fell back to the IRI *fragment* while the reader injects the full
  IRI → phantom `alias:global_ID` flag on any round-trip that omitted
  it. Fallback now `record.iri` on both sides (`service.py:1119`).
- **`DependentVariableEditor.draftVariable` signature override:**
  `checkResult.units`/`indices` overwrote the stored signature when
  attaching an equation to a used variable → phantom structural flags.
  Now gated on `structuralLocked = editing && (used || hasStored
  equations)` — `hasStoredEquations` is synchronous, closing the
  async `useVariableLock` race; unused variables still adopt the
  checker signature (first equation defines it).

## Known latent issue (not fixed)

- **POST update path shares the graph blind spot:** saving a
  foreign-graph variable writes a *second* record into the selected
  graph (subject `{ont}#F_x` inside `library`) instead of updating the
  owner — split identity. Same shape as the delete fix if it bites.

## State

- **502 backend tests** pass; equation-editor `tsc`+vite clean
  (bundle `index-DmJq04ph.js` — hard-refresh needed after rebuild).
- `fQx` save succeeded post-fix (`V_55` minted). Energy equations
  E_26–E_28 authored. `data/` diffs = user content + re-serialization.
