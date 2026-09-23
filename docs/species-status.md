# Species allocation & distribution — status

Implementation status of §20 in
`docs/behaviour-linker-design-discussion.md` (species allocation and
distribution).  Last updated 2026-09-23.

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

**Ruled (2026-09-23):** the artefact is a *named reaction scheme* —
abstract and reusable.  Components are generic (`A`, `B`, `C` …);
reactions are simple `{reactants} → {products}` rules (complex schemes
are built from single reactions, not long lists).  What is
model-specific stays out: placements, permeability, and the alias map.

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
pickers by capability.

## Model→species pin (implemented 2026-09-23)

The model names its species artefact via a `promo:usesSpecies` pin on
the model graph IRI — the persistent form of the `?species=` param,
mirroring `usesOntology`:

- **Stamped** at creation (`POST /api/catalogue/new` `uses_species`),
  copied on fork, replaceable on drafts via `PUT /api/catalogue/pins`
  (frozen → 403).  The hub shows purple species chips and a
  **Species…** button on model lines.
- **Read** by the modeller: `ModelDocument.usesSpecies` round-trips;
  `?species=` overrides the pin and is seeded into state so the next
  save stamps it (migration path from the URL param).
- **Consumed** by `/api/instantiate/model` + `/code`: `?species=`
  falls back to the pin (`_species_pin`).
- **Fixed en route:** `PUT /api/modeller/model`'s typed-subject wipe
  no longer deletes the graph IRI's self-description — it is typed
  `promo:Model` itself, so artefact type, label and pins were being
  wiped on every save.

## Species-present readout (implemented 2026-09-23)

`GET /api/instantiate/species-distribution?graph=<model>[&species=]`
returns the fixpoint's per-element sets — `{nodes: {iri: [compIris]},
arcs: {iri: [compIris]}}` — running the same `distribute()` engine
that binds `S` at instantiation.  `?species=` falls back to the
model's `usesSpecies` pin.

The modeller fetches it debounced (400 ms) whenever `modelNodes`/
`modelArcs` change and shows it in `SpeciesPanel`: **present:** on
nodes (also on nodes without species gestures — presence is
informative everywhere) and **carries:** on transport arcs, rendered
through the alias-aware `compLabel`.

## Model-level aliasing (ruled + implemented 2026-09-23)

Species are abstract in the artefact; their *reading* is
model-dependent (`A :: H2O`).  The alias is a per-model binding, so it
lives in the **model graph** — the artefact stays reusable across
models that read the same scheme differently:

```turtle
<componentIRI>  promo:speciesAlias  "H2O" .   # in the model graph
```

- Edited in the modeller's **Species aliases** dialog (toolbar,
  `apps/modeller/src/SpeciesAliasDialog.tsx`) — model-level, not
  per-node.  The species app never sees aliases (it edits the
  vocabulary, not its interpretation).
- `AppState.speciesAliases` (Map) ↔ `ModelDocument.speciesAliases`
  (dict); PUT wipes `(_, promo:speciesAlias, _)` explicitly since the
  subjects are external IRIs.
- `SpeciesPanel.compLabel` resolves `alias ?? label ?? frag` — pickers
  show `H2O` once aliased.
- `promo:speciesAlias` (not `promo:alias`) — the latter is the
  variable-alias JSON mechanism (`_add_aliases`).

**Open:** alias target is a literal today; an IRI-valued alias (a
shared substance catalogue, or an ontology subtoken linking to
`component_mass` balances) is the migration path.

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
- `apps/species/` — the `/species` SPA (port 3005, `dev.sh species`).
- `apps/modeller/src/SpeciesPanel.tsx` — the capability-gated gestures.
- `apps/modeller/src/SpeciesAliasDialog.tsx` — model-level alias table.

## Open / deferred

- **Stoichiometry** — coefficients belong to the `reactions` domain's
  kinetics, not distribution (only `{reactants}→{products}` sets are
  needed for presence).  Ruled refinement (2026-09-23): coefficient
  *slots* belong to the Reaction in the scheme (the chemistry is
  fixed); *values* bind at kinetic-equation instantiation, after the
  model topology exists.
- **`Q` (reaction index)** — could bind by the same mechanism.
- **Multi-pin** — `usesSpecies` is multi-valued in RDF but the
  modeller UI uses the first only; a model doc save drops additional
  pins (single-scheme-per-model assumption).
