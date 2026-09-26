# Ontology Editor — Implementation Status

**Last updated:** 2026-09-20

## Current state

v1 implemented and verified end-to-end.  Backend, frontend, and seed data
all working; manual UI testing done 2026-09-14.

- `backend/core/graph_store.py` (`RdfStore`): implemented.
  - Wraps `rdflib.Dataset`.
  - Loads `PROMO_DATA_DIR/*.trig` and seeds from legacy v8 JSON/TriG when
    the editable ontology graph is empty; otherwise seeds
    `seed_default_ontology()`.
  - Persist/serialize as TriG.
  - `add_domain` replaces the full `hasToken` set on save (update
    semantics, not append-only); same for `sharedTokens` on rules.
- `backend/ontology/rdf_context.py` (`RdfContext`): implemented.
  - Implements `EquationContext`.
  - Reads variables, indices, and the network tree from the seeded
    `RdfStore.ontology_graph`.
  - Parses `promo:network` list literals and `>>>` interface paths.
- `backend/ontology/service.py`: full CRUD for domains, tokens, axes,
  axis terms, scale dimensions/values, entity types, indices, connection
  rules; `POST /save`; `GET /resolve-connection` (ancestor-aware rule
  matching).
- `apps/ontology-editor/`: 7 stage tabs (Tokens, Domains, Axes, Scales,
  Entity Types, Indices, Rules), hierarchical tree rendering, token
  inheritance UI.

## Semantics implemented (2026-09-14)

- **Token model** — Stage 1 (Tokens tab) defines the global token list;
  Stage 2 (Domains tab) activates tokens per domain.  Subdomains inherit
  parent tokens (read-only, greyed-out `(inherited)` in the UI) and may
  add more from the global list; inherited tokens cannot be removed.
  Backend resolves `inherited_tokens` by walking the `promo:parent`
  chain in `_list_domain_records`.
- **Cascade delete** — `_cascade_delete` removes the subject, all
  contained descendants (via `parent`, `hasAxis`, `hasScale`,
  `hasDomain`), and all incoming references (e.g. `hasToken` links from
  domains to a deleted token).  Applied to every delete endpoint.
- **Connection rule resolution** — `GET /api/ontology/resolve-connection?source&target`
  returns applicable rules for a domain pair.  A rule applies when its
  `source_domain`/`target_domain` is the endpoint domain or an ancestor;
  bidirectional rules match the swapped pair; the `scope` attribute
  filters on the branch pair (`same` = shared ancestor, `cross` = none,
  `any` = unconstrained); results sorted most-specific first.
  `physical-cross` was retired 2026-09-15 (token-flow + cross can never
  apply); seed rules are `physical-same`, `signal`, `access`, `sensor`,
  `actuation`.
- **Validation** — frontend disables Save until required fields are
  filled; backend returns 422 on empty labels; axis terms require a
  selected axis.
- **Seed indices** — `species` (bound to `component_mass` token), `node`,
  `arc` (network topology indices), plus arc sub-indices `A_mass`,
  `A_energy`, `A_diff`, `A_conv`, `A_heat`, `A_rad`, `A_work`
  (`promo:subIndexOf`/`promo:selector`, see below).
- **Dev tooling** — `dev.sh` runs uvicorn with `--reload`.

## Seeded structure & migrations (2026-09-20)

- **Transport entity tree** — `transport_system` specialised by token:
  `mass_transport` {`diffusion_transport`, `convection_transport`} and
  `energy_transport` {`heat_transport`, `radiation_transport`,
  `work_transport`}, linked by `promo:parent`.  Mechanism leaves bind
  the continuum scale pair; grouping types carry no scale bindings.
- **Arc sub-indices** — `Index` resources may carry `promo:subIndexOf`
  (base index) + `promo:selector` (entity type defining membership via
  the incident transport node).  Seven seeded under `arc`; the checker
  sees plain distinct indices, instantiation resolves membership.
  Design: BL doc §16.
- **Scale regimes** — `particulate`|`continuum` grouping values top the
  `length` and `time` trees; `length` gained a `molecular` level under
  `particulate`.  Regime is derived by `promo:parent` ancestry; all
  seeded entity types are continuum.  Design: BL doc §17.
- **Seed contract** — `seed_default_ontology` writes initial state once
  (empty graph); four idempotent migrations in `load()`
  (`_seed_constants`, `_seed_scale_regimes`, `_seed_transport_mechanisms`,
  `_seed_arc_sub_indices`) guarantee a floor on the core graph only —
  floor deletions resurrect on restart, modifications persist, other
  artefact graphs are never seeded.  Design: BL doc §17.

## Design

| Document | Content |
|----------|---------|
| `docs/ontology-editor-design.md` | UI layout, variable table, detail editor, equation editor integration, user function registration |
| `docs/ontology-data-model.md` | RDF schema for variables, indices, equations, tokens, domain tree; loader contract |
| `docs/ADR-006-ontology-evolution.md` | Versioning, change classification, migration rules |
| `docs/equation-context-contract.md` | `EquationContext` protocol (the seam to the equation editor) |

## Backend

`backend/ontology/` now contains the `RdfContext` provider and a
FastAPI router scaffold.  The provider is functional and tested.

### Planned backend

- RDF graph store (rdflib or persistent triple store).
- `RdfContext` provider implementing `EquationContext` — loads
  variables, indices, and domain tree from a named graph.
- CRUD operations for variables, indices, tokens, networks, equations.
- Versioning: create new named graph on semantic changes; additive
  changes within a version.
- Reference-count check before deletion (cascade report).

## Frontend

`apps/ontology-editor/` — empty scaffold.

### Planned frontend

- React with Tailwind or shadcn/ui.
- Three-pane layout: domain tree, variable table, detail editor.
- TanStack Table for sort/filter/selection.
- Equation editor integration (modal/inline) for core equations.
- User function registration dialog.
- Publication exports (LaTeX, variable table, domain tree diagram).

## Pending items

1. ~~Wire equation editor to `RdfContext`~~ **Done (2026-09-15):**
   `RdfContext` reads all named graphs (ProMo14 vocabulary only) and
   builds the domain tree from `promo:Domain`/`promo:parent` with the
   authoritative `universe` root (`domain_universe`).  Variables, equations
   and indices use `promo:inDomain` IRI links while readable network names
   remain compatibility qualifiers; verified end-to-end via `/api/equation/context` +
   `/check`.  Legacy v8 loader archived to `archive/loader.py`.
2. ~~Wire modeller `ConnectionRuleResolver` to
   `GET /api/ontology/resolve-connection`~~ **Done (2026-09-18):**
   `RemoteRuleResolver` in `packages/semantic` — sync cache for hover,
   `resolveAsync` for connect actions, `carrier` →
   `promo:ArcType/<carrier>`, placeholder fallback when backend is down.
   Remaining gap: modeller palette still feeds placeholder entity types;
   rules match on domains + token licensing, so real matches need
   ontology-backed entity/domain types.
3. ~~Implement ontology versioning~~ **Done (2026-09-17):**
   `RdfStore.freeze_version(v)` → immutable `{graphIRI}/{v}` named
   graph; `GET /versions`, `POST /publish`, `GET /export?version=`;
   Publish button in the UI auto-downloads frozen Turtle;
   `scripts/export_ontology.py --repo` writes the ProMo-ontologies
   layout.  Change classification (ADR-006) still to be enforced —
   SHACL shapes at the publish boundary are the endorsed mechanism.
4. ~~Add publication export functionality~~ **Done (2026-09-17)** — see
   item 3.
5. ~~Persist `ontology.trig` automatically or prompt on unsaved changes~~
   **Done (2026-09-18):** store-global dirty tracking — mutation middleware
   in `backend/main.py` flags `RdfStore.dirty` on any successful
   POST/PUT/DELETE; `GET /api/ontology/status` exposes it; both editors
   poll via `useStoreDirty`, show an "● unsaved" badge, and warn on tab
   close (`beforeunload`).  `save()` clears the flag and stamps
   `last_saved`.  Full autosave deliberately not implemented — Save
   remains an explicit user action.
6. **Graph selection (done 2026-09-17):** every endpoint accepts
   `?graph=<iri>`; `editable_param` rejects frozen version graphs with
   403; `scoped_context` resolves the artefact + transitive
   `usesOntology` pin set (R4).  Editor reads `?graph=` from the URL.
   Remaining: auto-stamp `usesOntology` when artefacts are created
   outside `POST /api/catalogue/new`.

## Implementation plan

The ontology editor is the first module in the ProMo14 pipeline.  Its job
is to author the vocabulary (domain tree, indices, tokens, variables, core
equations) and publish a versioned ontology named graph that the equation
editor, modeller, and code generator consume.

### Phase 0 — Shared RDF store in `backend/core`

A single `RdfStore` based on `rdflib.Dataset` removes the temporary JSON/TriG
bridge and becomes the source of truth for both ontology and equation
contexts.

- `backend/core/graph_store.py`:
  - `RdfStore` wrapping a `Dataset`.
  - `RdfStore.from_dir(PROMO_DATA_DIR)` — load any existing TriG named
    graphs; fall back to the legacy JSON/TriG loader and materialise the
    result as one default/ontology graph.
  - `RdfStore.to_dir(PROMO_DATA_DIR)` — serialise the whole dataset as
    `ontology.trig` (or versioned `ontology_<version>.trig`).
  - Named graph CRUD: `add_graph`, `replace_graph`, `remove_graph`.
  - IRI minting: `next_internal_id(prefix)`, `mint_iri(base, suffix)`.

### Phase 1 — `RdfContext` provider

- `backend/ontology/rdf_context.py`:
  - Implements `EquationContext` from `backend/equation/context.py`.
  - Builds `Variable`, `Index`, and the parent → children network tree by
    walking the `RdfStore.ontology_graph`.
  - Computes `accessible_networks` from the RDF domain tree.
  - Parses `promo:network` list literals and `>>>` interface paths.
  - **Limitation:** currently only reads the seeded `ontology_graph`.
    The `variableExpression.trig` data lives in named graphs with
    lowercase `promo:variable`/`promo:index` types; `RdfContext` must be
    extended to consume these.
- `backend/equation/service.py`:
  - Switch `/api/equation/context` to use `RdfContext` when a graph IRI is
    available, or the legacy loader as a fallback.

### Phase 2 — Ontology CRUD backend

- `backend/ontology/models.py` — Pydantic models for `Network`, `Index`,
  `Token`, `Variable`, `Equation`, `OntologyVersion`.
- `backend/ontology/service.py` — FastAPI router under `/api/ontology`:
  - `/networks`, `/networks/{iri}`
  - `/indices`, `/indices/{iri}`
  - `/tokens`, `/tokens/{iri}`
  - `/variables`, `/variables/{iri}`
  - `/equations`, `/equations/{iri}`
  - `/versions` (publish / list)
  - `/check` — semantic pre-check using the equation checker.
- `backend/ontology/store.py` — higher-level operations on top of
  `RdfStore` with change classification, reference counting, and version
  snapshotting.

### Phase 3 — Frontend scaffold

- `apps/ontology-editor/` (new Vite + React app):
  - Three-pane layout: domain tree, variable table, detail editor.
  - Re-use `apps/equation-editor` components for variable/indices and the
    equation editor as a modal.
  - Save/publish workflow creates a new ontology named graph and writes it
    back to `PROMO_DATA_DIR`.

### Phase 4 — Versioning and re-validation

- Change classification (additive, annotation, deprecation, semantic
  modification, deletion) per ADR-006.
- Reference-count check before deletion.
- Publish creates a new named graph; re-validation of dependent var/expr
  graphs is left to a background batch job.

### Phase 5 — Publication exports

- LaTeX equation set, variable table, domain tree diagram, ontology report.

## Dependencies

- Equation editor backend (for equation checking within the ontology
  editor).
- `backend/core` shared services (RDF store, IRI minting).

## Current priority

v1 is complete and verified.  The next concrete steps are:

1. ~~Wire equation editor `/api/equation/context` to `RdfContext`~~ —
   done (2026-09-15).
2. Consume `resolve-connection` from the modeller's
   `ConnectionRuleResolver` (replaces the allow-all placeholder).
3. ~~Extend `RdfContext` to read **all named graphs** in the `RdfStore`~~
   — done (2026-09-15).  Legacy `promo:variable`/`promo:index` support
   was dropped again the same day: the legacy loader is archived and
   only the ProMo14 vocabulary is recognised.
