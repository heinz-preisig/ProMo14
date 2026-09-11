# Ontology Editor — Implementation Status

**Last updated:** 2026-09-10

## Current state

Design complete.  Phase 0 and Phase 1 backend are implemented and wired
into the corpus smoke test.

- `backend/core/graph_store.py` (`RdfStore`): implemented.
  - Wraps `rdflib.Dataset`.
  - Loads `PROMO_DATA_DIR/*.trig` and seeds from legacy v8 JSON/TriG when
    the editable ontology graph is empty.
  - Persist/serialize as TriG.
- `backend/ontology/rdf_context.py` (`RdfContext`): implemented.
  - Implements `EquationContext`.
  - Reads variables, indices, and the network tree from the seeded
    `RdfStore.ontology_graph`.
  - Parses `promo:network` list literals and `>>>` interface paths.
- `backend/core/loader.py`: updated.
  - `rdflib` is optional for JSON-only loading.
  - Discovers and merges versioned `variables_v8*.json` files by size.
  - Converts v8 records into `Variable`/`Index` dataclass-compatible dicts.
- `apps/ontology-editor/`: UI scaffold with `App.tsx`, build passes.
- FastAPI router `backend/ontology/service.py` exists but is not yet fully
  wired with CRUD.

## Design

| Document | Content |
|----------|---------|
| `docs/ontology-editor-design.md` | UI layout, variable table, detail editor, equation editor integration, user function registration |
| `docs/ontology-data-model.md` | RDF schema for variables, indices, equations, tokens, domain tree; loader contract |
| `docs/ADR-006-ontology-evolution.md` | Versioning, change classification, migration rules |
| `docs/equation-context-contract.md` | `EquationContext` protocol (the seam to the equation editor) |

## Backend

`backend/ontology/` now contains the `RdfContext` provider and a
FastAPI router scaffold.  The provider is functional and consumed by
`backend/equation/test_corpus.py` for the real ontology context.

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

1. Implement backend graph store and `RdfContext` provider.
2. Build frontend domain tree pane.
3. Build variable table with filtering.
4. Build detail/editor pane with tabs (identity, domain, semantics,
   indices, equations).
5. Integrate equation editor for equation authoring.
6. Implement ontology versioning and change classification.
7. Add publication export functionality.

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

Phase 0 and Phase 1 are largely complete.  The next concrete steps are:

1. Extend `RdfContext` to read **all named graphs** in the `RdfStore`
   (not only `ontology_graph`) and to recognise lowercase
   `promo:variable` / `promo:index` types used by
   `variableExpression.trig`.
2. Switch the corpus smoke test to the new arc/connection data in
   `variableExpression.trig` (or the canonical v9 TriG file) so the
   remaining 3 legacy failures disappear.
3. Begin Phase 2 ontology CRUD backend (`models.py`, `service.py`,
   `store.py`).
