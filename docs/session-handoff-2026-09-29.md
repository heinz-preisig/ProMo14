# Session handoff — 2026-09-29

State of the ProMo14 workspace at end of day.  Branch `main`, remote
`heinz-preisig/ProMo14`.  Supersedes `session-handoff-2026-09-28.md`.

**Before switching machines:** all work committed and pushed
(`35b7445` + handoff commit → `origin/main`).  `git status` is clean,
the modeller `dist/` is built, and the store was clean at last check
(run `./dev.sh save` if unsure).  On the home machine: `./dev.sh sync`
(pull + `uv sync` + `npm install` + build all + start all).  Do **not**
`wipe-restart` — `data/` is the sync channel.

## What landed — pins & gesture gates (`35b7445`, late afternoon)

- **All four pin kinds first-class** — `usesLibrary`/`usesAssignment`
  join `usesOntology`/`usesSpecies`: declared vocabulary in
  `graph_store.py`, stamped at creation (`create_artefact_graph`
  `uses_library=`/`uses_assignment=`), copied on fork, editable on
  drafts via `PUT /api/catalogue/pins`.  `resolution_scope` now
  traverses `usesOntology` + `usesLibrary` — a model sees its pinned
  library's entity types and equations without extra wiring.
- **Instantiate resolves dependencies from pins** — `/model`, `/code`,
  `/initial` read `usesLibrary`/`usesAssignment` off the model graph
  (`_model_dependencies`); `?vars=` still overrides as the library IRI
  and implies `<iri>/assignments`.
- **§20 gesture admissibility** — new `backend/core/gestures.py`
  resolves entity-type capability sets through `promo:parent`
  ancestry over the resolution scope.  `PUT /api/modeller/model`
  rejects inadmissible placements with **422 before the wipe** (the
  graph is left untouched); `/api/instantiate/model` + `/code` report
  persisted violations as `inadmissible-gesture` problems — the safety
  net for graphs that predate the gate or bypassed it.  Capabilities
  are seeded in `data/ontology.trig`: `cap_species_source` on
  environment, `cap_reaction_host` on lumped/distributed/point,
  `cap_species_transport` on mass transport (incl. the new
  `etype_convection_transport`).
- **`GET /api/modeller/behaviour-entity-types`** — entity types with a
  *closed* assignment in the model's pinned assignment graphs; the
  modeller palette now lists only those (a placeable node is one whose
  behaviour is bound).  Note: an unpinned model currently gets an
  **empty palette** — deliberate, but worth revisiting if confusing.
- **Hub: pin editor + artefact delete** — **Pins…** on every draft
  line edits all four kinds (per-kind chips `ont:`/`lib:`/`asg:`/
  `spec:`); **Delete…** hits `DELETE /api/catalogue/artefact` — 403 on
  the core ontology and frozen versions, 409 while still referenced
  (pins or `versionOf`).  Hub is now served
  `Cache-Control: no-cache` so `hub.html` edits reach the browser.
- **Behaviour-derived assignment graphs repinned** —
  `{library}/assignments` now stamps the library's *own* `usesOntology`
  pins plus `usesLibrary` back to the library, instead of the raw
  resolution-scope list.
- **Fix en route** — `ontology/service.py::resolve_connection` builds
  ancestor chains on the scoped working graph (`ctx.graph`), not the
  raw request `graph_iri`.
- **Tests** — gesture admissibility PUT/report, pinned-library entity
  types, artefact-delete lifecycle (409 → 200 → 404, 403 ontology).
  **402 pass.**

## What landed — behaviour-linker (earlier commits, all pushed)

- `e2bf960` — state vs algebraic base equations: a state-class LHS
  yields the integrator loop; the base picker is grouped accordingly.
- `45b5807` — class-agnostic state, frontier suggestions, printable
  LaTeX, unsaved indicator.
- `1e46b98` — markings-only assignments saved; backend snapshot drives
  `lastSaved`.
- `bbe9153`, `4b7f709`, `03e59ea`, `b57e26f` — LaTeX gap, dead-code
  cleanup + frontier tests, component modularisation,
  `useBehaviourLinker` hook (App.tsx presentational only).
- `18b455f`, `112bb17`, `3c87bb7`, `0ef8adf`, `0427afd` —
  constants/parameters in printable LaTeX, neutral "base equation"
  labels, base equation closes the sequence, loaded assignments
  normalised, **closed allowed for role-only (equation-less)
  assignments**.
- `5df7996`, `a5f2f8b` — data updates from the behaviour sessions.

## State

- Backend tests: **402 passed** (`uv run pytest backend/ -x -q`).
- `data/ontology.trig`: capabilities + `usesLibrary`/`usesAssignment`
  property declarations; `data/model.trig` is **new** — the `test_01`
  model artefact's per-line persistence fan-out (now tracked);
  assignments/library re-saved with the new pins.
- Modeller `dist/` built at 16:50 — the hub-served UI is current
  (palette filter included).
- Status docs updated: `suite-status.md`, `species-status.md`,
  `behaviour-linker-status.md`.

## Pending / next

- **Exercise the gates end-to-end** — place a species gesture on an
  incapable node in the modeller UI and confirm the 422 surfaces
  sanely; delete a referenced artefact via the hub.
- **Empty-palette check** — a model with no `usesAssignment` pin (or
  no closed assignments) shows no node types at all; decide whether a
  hint/fallback is warranted.
- **Multi-pin limits** — `usesLibrary`/`usesAssignment` are
  multi-valued in RDF but `_model_dependencies` takes the first.
- **Cross-artefact consistency review** — still deferred until all
  apps are operational (dependency-DAG branches, impact analysis,
  resource-level refs, stale `closed` assignments, SHACL at publish
  boundary, atomic multi-file persistence, clean-instantiation gate).
- Deferred queue unchanged: reaction-domain equations,
  behaviour-linker graphical editor, expression-valued cells
  (`promo:valueExpression`), multi-pin `usesSpecies` consumption,
  external-IRI links on variables, LaTeX→image cache, RDF vocabulary
  finalization.

## Commands

- Tests: `uv run python -m pytest backend -x -q`
- Frontend after `apps/modeller/src` edits: `./dev.sh build modeller`
  — **always rebuild before refreshing**, the hub serves `dist/`
- Store: `./dev.sh save` before stopping if dirty; `./dev.sh status`
- Other machine: `./dev.sh sync` (pull + deps + build + start all)
