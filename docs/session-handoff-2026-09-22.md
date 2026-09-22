# Session handoff — 2026-09-22

State of the ProMo14 workspace at end of session.  Branch `main`,
pushed to `heinz-preisig/ProMo14`.  Supersedes
`session-handoff-2026-09-21.md`.

## What landed today (6 commits)

**§20 species allocation & distribution** — the full path from species
vocabulary to a bound `S` index at instantiation.  Design:
`docs/behaviour-linker-design-discussion.md` §20; status:
`docs/species-status.md`.

- `cae080b` — distribution engine (`instantiate/distribute.py`,
  monotone fixpoint: injection → permeable transport → conditional
  reactions; bidirectional spread) + tests.
- `4d55a22` — species artefact schema + GET/PUT `/api/species/species`;
  `Species` registered in `ARTEFACT_TYPES`; catalogue type `species`.
- `ace94fa` — `promo:capability` on entity types, inherited via
  `promo:parent`: `species_source` (environment), `reaction_host`
  (lumped/distributed/point), `species_transport` (mass_transport →
  diffusion/convection).  Exposed on `/entity-types`.
- `3659221` — wire distribution → `S` binding: model carries
  `speciesAllocation`/`hostsReaction`/`permeable`; `/model` + `/code`
  take `?species=`; `build_model` binds `S` to the union over each
  var's topological extent.
- `bbf5e9f` — `/species` SPA scaffold (port 3005): three-panel editor
  for components / allocations / reactions; hub `APPS` entry.
- `2dffded` — modeller gestures (`SpeciesPanel.tsx`): capability-gated
  pickers — reservoir picks allocation, reaction host toggles
  reactions, mass-transport arc sets per-species permeability.  Model
  names its artefact via `?species=`.

## Key code locations

- `backend/instantiate/distribute.py` — `distribute()` fixpoint;
  `SpeciesNode`/`SpeciesArc`/`Reaction`/`SpeciesArtefact` inputs.
- `backend/instantiate/builder.py` — `species`/`species_index` params;
  `species_elements` binds `S` to the union over the var's extent.
- `backend/instantiate/service.py` — `_species_distribution`,
  `_entity_capabilities`, `_species_index_iri`; `?species=` param.
- `backend/species/service.py` — `SpeciesDocument` GET/PUT.
- `backend/core/graph_store.py` — `_seed_capabilities` (floor
  migration, guarded by `cap_species_source`).
- `backend/modeller/service.py` — species-placement persistence.
- `apps/species/src/App.tsx` — the species editor.
- `apps/modeller/src/SpeciesPanel.tsx` — the gestures;
  `api.ts::SPECIES_IRI`/`fetchSpecies`/`fetchEntityCapabilities`;
  `ModelState.ts` `setNodeSpecies`/`setArcPermeable`.

## Reproduce on another machine

`data/ontology.trig` is **tracked in git** — `git pull` brings the
working dataset.  Do **not** run `wipe-restart`.

```bash
git pull
uv sync
npm install          # picks up the new apps/species workspace
./dev.sh start       # backend :8000 + app dev servers
```

On first load the backend runs the `_seed_capabilities` migration
(idempotent) and marks the store dirty — `./dev.sh save` to persist.

New app: `npm run dev:species` → :3005.  To exercise the gestures, open
the modeller with `?graph=<model>&species=<species-artefact>`.

Node via `~/.nvm` (v24.19.0) — `source ~/.nvm/nvm.sh` if needed.

## Verified

- 295 backend tests pass: `uv run pytest backend/ -x -q`
- `npx tsc --noEmit` clean in `apps/species` and `apps/modeller`
- modeller 35 + semantic 26 frontend tests pass

## Caveats

- In-memory store: changes persist only via Save / `POST /save` /
  `./dev.sh save`; restarting loses unsaved edits.
- The species gestures need a `?species=` param — there's no persistent
  model→species pin yet (see next tasks).
- `carries_species` on an arc = touches a `species_transport` node —
  energy arcs are excluded by capability, not by arc type.
- The species app is a scaffold — functional but minimal (no
  stoichiometry, no validation, no delete-guards).

## Next tasks (priority order)

1. **Model→species pin** — replace the `?species=` URL param with a
   `promo:usesSpecies` pin on the model artefact (set at creation or in
   the hub), so the association persists.
2. **Species-present readout** — surface the distribution in the
   modeller (per-node/arc species) — needs a small endpoint or reuse of
   the `/model` report's bound `S`.
3. **Stoichiometry** — coefficients for the `reactions` domain's
   kinetics (separate from distribution presence).
4. **`Q` binding** — reaction index by the same mechanism as `S`.
5. **Hub ticket** (`docs/hub-session-ticket.md`) — graph choice
   unavoidable; per-artefact `.trig` persistence.
6. **R3 port validation** — exercise on real models (may revert to R1).

## Ruled contracts (don't re-litigate)

See `session-handoff-2026-09-17.md` — R1–R8 versioning rules,
connection-rule semantics, namespace discipline (`promo#` = vocabulary
only), no OWL.  §20 adds: species stay **artefact-external** (the
modeller references, never hardcodes); capabilities are **entity-type**
predicates, distinct from connection rules.
