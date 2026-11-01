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

## Test invocations

```bash
uv run --with pytest --with httpx pytest backend/ -x -q
(cd packages/semantic && npm test)   # vitest
(cd apps/modeller && npx tsc --noEmit)
```
