# Species allocation & distribution — status

Implementation status of §20 in
`docs/behaviour-linker-design-discussion.md` (species allocation and
distribution).  Last updated 2026-09-22.

## Concept

Species presence is a **non-topological index** `S` whose element set is
computed, not drawn.  A monotone fixpoint propagation spreads species
over the model's nodes and arcs:

- **Injection** — a reservoir node (`species_source` capability)
  references an `Allocation` (a named set of species) and injects it.
- **Transport** — a mass/species-transport arc (`species_transport`
  capability) carries `species(source) ∩ permeable(arc)`; `permeable`
  absent = all pass, a strict subset = a semipermeable wall.
- **Reaction** — a `reaction_host` node fires a reaction when its
  reactants are present, adding the products (reactions cascade).
- **Fixpoint** — species only accumulate; iteration terminates.

The modeller stays **species-agnostic**: the vocabulary lives in a
separate *species artefact*; the model only places allocations,
reactions and permeability by reference.

## Artefact model

A `promo:Species` graph (catalogue type `species`) holds:

- `promo:Component` — a species (the `S` element).
- `promo:Allocation` — a named injectable set, `promo:member`→Component.
- `promo:Reaction` — `promo:reactant`/`promo:product`→Component.

Service: `GET`/`PUT /api/species/species?graph=` (whole-document,
mirrors the modeller pattern).  Edited in the standalone `/species` SPA.

## Capabilities

`promo:capability` → `promo:Capability` resources on entity types,
inherited through `promo:parent` ancestry (a subtype grants what its
parents do).  Seeded by `_seed_capabilities` (floor migration):

| Entity type | Capability |
|-------------|-----------|
| `environment` | `species_source` |
| `lumped`, `distributed`, `point` | `reaction_host` |
| `mass_transport` | `species_transport` (diffusion/convection inherit) |

Exposed on `GET /api/ontology/entity-types` as `capabilities: string[]`.

## Modeller gestures

The model carries placements (persisted in the model artefact):

- `promo:speciesAllocation` — reservoir → Allocation IRI.
- `promo:hostsReaction` — node → Reaction IRIs.
- `promo:permeable` — arc → Component IRIs that pass.

The Properties panel (`apps/modeller/src/SpeciesPanel.tsx`) gates the
pickers by capability.  The model names its species artefact via the
`?species=<graph>` URL param.

## Distribution → `S` binding

`GET /api/instantiate/model?graph=<model>&vars=<vars>&species=<species>`
and `/code` run `instantiate/distribute.py` over the placements +
artefact, then `build_model` binds the species index to the **union of
species over each variable's topological extent** (its nodes if
node-indexed, its bound arcs if arc-indexed, both if both).  Without
`?species=` the index stays symbolic.

## Code locations

- `backend/instantiate/distribute.py` — fixpoint engine (pure).
- `backend/instantiate/builder.py` — `species`/`species_index` params,
  `species_elements` closure.
- `backend/instantiate/service.py` — `_species_distribution`,
  `_entity_capabilities`, `_species_index_iri`; `?species=` on `/model`
  + `/code`.
- `backend/species/service.py` — artefact GET/PUT.
- `backend/core/graph_store.py` — `_seed_capabilities`, `Species` in
  `ARTEFACT_TYPES`.
- `backend/modeller/service.py` — `speciesAllocation`/`hostsReaction`/
  `permeable` persistence.
- `apps/species/` — the `/species` SPA (port 3005).
- `apps/modeller/src/SpeciesPanel.tsx` — the capability-gated gestures.

## Open / deferred

- **Stoichiometry** — coefficients belong to the `reactions` domain's
  kinetics, not distribution (only `{reactants}→{products}` sets are
  needed for presence).
- **`Q` (reaction index)** — could bind by the same mechanism.
- **Species-present readout** — show per-node/arc species in the
  modeller (the distribution is computed server-side; needs a small
  endpoint or reuse of the report).
- **Model→species pin** — currently a `?species=` URL param; a
  persistent `promo:usesSpecies` pin on the model artefact would be
  cleaner (settable at creation / in the hub).
