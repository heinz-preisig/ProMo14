# ProMo Suite — Implementation Status

**Last updated:** 2026-09-17 (end of session)

## Summary

| Module | Backend | Frontend | Tests | Status |
|--------|---------|----------|-------|--------|
| Hub + Catalogue | `GET /api/catalogue`, `POST /new`, `POST /fork` | `backend/static/hub.html` at `/` | covered by service tests | **Working** — artefact lines, pins, fork, open-in-app |
| Ontology Editor | `RdfStore` + `RdfContext` + full CRUD + seed data + rule resolution + versioning (`freeze_version`, publish/export) | React UI with all v1 tabs + Publish button | TypeScript + Vite build pass | **v1 verified end-to-end**; `?graph=` session param wired |
| Equation Editor | Parser + checker + service; `?graph=` pin-scoped context + artefact-graph writes | React + TypeScript + Vite app | 4 test files | Backend and frontend functional; `?graph=` wired |
| Behaviour Linker | Scaffold | Scaffold | — | Design discussion started (see `docs/behaviour-linker-design-discussion.md`) |
| Modeller | Scaffold | Phases 1–4 partial | 35 unit tests | Core editing complete, persistence pending; no backend calls yet |
| Shared (`packages/semantic`) | — | Contracts + placeholder | builds + tests | Placeholder implementations in place |
| Shared (`backend/core`) | `RdfStore` (versioning, frozen guard, resolution_scope), catalogue, full ontology CRUD | — | — | Legacy loader archived to `archive/loader.py` |
| Model Reuse | — | — | — | Not started |
| Instantiation | — | — | — | Not started |
| Code Generation | — | — | — | Not started |

## Versioning & graph selection (2026-09-17)

Implemented per `docs/versioning-and-session-design.md` (commits
`3bdb63d`, `0197117`, `0489b5d`):

- **Artefact types** — `promo:Ontology | Library | Assignment | Model |
  Glass` stamped on every graph; `promo:Version` on frozen graphs.
- **Catalogue** — `GET /api/catalogue` groups drafts + frozen versions
  into artefact lines with `usesOntology` pins; `POST /api/catalogue/new`
  and `/fork` create lines (fork re-homes instance IRIs).
- **Hub** — `backend/static/hub.html` at `/` lists artefact lines with
  Open/Fork/Publish/Export; apps launched as `app?graph=<iri>`.
- **Versioning** — `RdfStore.freeze_version(v)` copies the working graph
  to `{graphIRI}/{v}` (immutable); `GET /api/ontology/versions`,
  `POST /api/ontology/publish`, `GET /api/ontology/export?version=`;
  `scripts/export_ontology.py --repo` writes the ProMo-ontologies layout.
- **Graph selection** — `?graph=` on all ontology + equation endpoints;
  `editable_param` rejects frozen graphs with 403.  Resolution context
  = artefact + transitive `usesOntology` closure
  (`RdfStore.resolution_scope`, R4).  Shared helpers
  `graph_param`/`editable_param`/`resolve_graph`/`scoped_context` live in
  `backend/ontology/service.py`.
- **w3id live** — `https://w3id.org/promo` redirects to the ProMo
  Ontologies landing page (perma-id/w3id.org#6700 merged).

## Module details

### Ontology Editor

- **Design:** Complete — see `docs/ontology-design-discussion-2026-09-11.md`
  (all 9 questions resolved), `docs/ontology-editor-v1-ticket.md`
  (implementation plan), `docs/ontology-editor-design.md`,
  `docs/ontology-data-model.md`, ADR-004, ADR-006.
  Key decisions: two-branch domain tree (physical/information),
  multi-axis variable classification (variable_class → "role" axis),
  entity types from CWA 17960, 3 connection rule types, transport system
  as node (not arc), event dynamics fits existing taxonomy.
- **Backend:** All v1 steps implemented and verified:
  - `backend/core/graph_store.py` — PROMO vocabulary for Domain,
    ClassificationAxis, AxisTerm, EntityType, ConnectionRule,
    EquationClass. CRUD methods for all. `seed_default_ontology()`
    bootstraps two-branch tree, 7 tokens, role axes, 8 entity types, 3
    connection rules, 5 equation classes, 3 indices (species/node/arc).
    `add_domain`/`add_connection_rule` use replace semantics for
    `hasToken`/`sharedTokens`.
  - `backend/ontology/models.py` — VariableRecord, EquationRecord,
    DomainRecord (with `inherited_tokens`), ClassificationAxisRecord,
    AxisTermRecord, EntityTypeRecord, ConnectionRuleRecord.
  - `backend/ontology/service.py` — REST endpoints for all entity
    types; `_cascade_delete` (containment + incoming references);
    `GET /resolve-connection` ancestor-aware rule matching.
  - `backend/ontology/rdf_context.py` — domains(), axes(),
    entity_types(), connection_rules() accessors; multi-axis
    classification loading; index `internal_id` round-trip.
- **Frontend:** `apps/ontology-editor/` — all v1 tabs implemented and
  manually verified: Tokens, Domains (token inheritance UI), Axes
  (hierarchical terms), Scales, Entity Types, Indices, Rules.
- **Semantics:** token inheritance down the domain tree (additive only);
  cascade delete; ancestor-aware connection rule resolution.
- **Namespace:** `https://w3id.org/promo#` throughout
  (`backend/core/graph_store.py`: `PROMO`, `PROMOLG`,
  `ONTOLOGY_GRAPH_IRI`).  Publishing pipeline live end-to-end: exported
  `ontology.ttl` → `heinz-preisig/ProMo-ontologies` (GitHub Pages) →
  w3id redirect **verified live** (PR #6700 merged).  See
  `publish/README.md`.
- **Next:** Consume `resolve-connection` from the modeller's
  `ConnectionRuleResolver`; auto-stamp `usesOntology` at artefact
  creation; SHACL shape checks at the publish boundary (ADR-006).

### Equation Editor

- **Backend:** Fully functional parser, checker, compile space, units,
  context protocol, and FastAPI service.  Replaces ProMo13 TPG with a
  hand-written recursive-descent parser.
- **API:** `POST /api/equation/parse`, `POST /api/equation/check`,
  `GET /api/equation/context`, `POST/PUT/DELETE /api/equation/variables`
  — all accept `?graph=<iri>`; writes land in the selected artefact
  graph (default: working ontology), frozen graphs rejected with 403.
- **Tests:** Parser, checker, compile space, units — all passing.
  The ProMo13 corpus replay (73 expressions, 70/73) has been archived
  to `archive/test_corpus.py`; the new regression baseline will be
  expressions re-entered through the equation editor.
- **Frontend:** React + TypeScript + Vite app in `apps/equation-editor/`.
  Features port/dependent variable creation, expression input with a
  single **Check** action, LaTeX preview, error display, variable
  palette with cascade delete, equation list, and a debug equation
  context JSON editor.  `api.ts` reads `?graph=` from the URL once and
  appends it to every call.
- **Next:** Persistence UX (variables created via POST live in memory
  until Save); codegen targets.

### Behaviour Linker

- **Design:** In progress.  Design discussion started 2026-09-13 — see
  `docs/behaviour-linker-design-discussion.md`.  Core mechanic defined:
  BL reads ontology + var/expr bipartite graph, user selects
  state-defining equation, RHS variables resolved recursively.  Key
  principles: ontology tags are hints, BL selections are bindings; state
  is emergent (structural property of equation subgraph); transport
  system has no state.  Open questions remain on unit of selection,
  assignment artefact, interface definitions, and graphics.
- **Backend:** `backend/behaviour/` — empty scaffold.
- **Frontend:** `apps/behaviour-linker/` — empty scaffold.
- **Next:** Resolve open design questions, then implement.

### Modeller

- **Frontend:** React + Konva.  Phases 1–3 complete (scene layer,
  semantic contracts, rules and graphical resolution).  Phase 4
  partially done (interactive knots, but no persistence yet).
- **Tests:** 35 unit tests passing (TreeOps, ModelState, buildScene,
  connectionService).
- **Backend:** `backend/modeller/` — empty scaffold.
- **Features:** Node/arc creation, drag, selection, deletion,
  three-panel hierarchy navigation, composite grouping, open-arc
  reconnection, pan/zoom, catalogue-resolved graphics,
  connection-rule enforcement.
- **Next:** RDF topology and hierarchy/layout persistence boundaries;
  then composition and scale.
- **Details:** See `docs/modeller-status.md`.

### Shared infrastructure

- **`packages/semantic`:** `SemanticCatalogue`, `ConnectionRuleResolver`
  interfaces with in-memory placeholder implementations.
  `connectionService.ts` shared by arc creation and reconnection.
- **`backend/core`:** `RdfStore` and legacy v8 loader implemented; full
  ontology CRUD (domains, axes, entity types, connection rules, tokens);
  shared IRI minting; seed data bootstrap.
- **`backend/main.py`:** FastAPI app mounting per-tool routers; server
  starts and `/api/health` returns `{"status":"ok"}`.

## How to run

### Modeller (frontend)
```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
npm install
npm run dev      # modeller on :3000
npm test         # all workspace tests
```

### Equation editor (backend)
```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
uv sync

# run compile-space tests
uv run python -m backend.equation.test_compile_space

# start API server
uv run uvicorn backend.main:app --port 8000
```

### Equation editor (frontend)
```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
npm install
npm run dev:equation  # Vite dev server on http://localhost:3001
```
