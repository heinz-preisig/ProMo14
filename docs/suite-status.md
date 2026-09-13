# ProMo Suite — Implementation Status

**Last updated:** 2026-09-12 (end of session)

## Summary

| Module | Backend | Frontend | Tests | Status |
|--------|---------|----------|-------|--------|
| Ontology Editor | `RdfStore` + `RdfContext` + full CRUD + seed data | React UI with all v1 tabs | TypeScript + Vite build pass | **v1 implemented**; end-to-end testing next |
| Equation Editor | Parser + checker + service | React + TypeScript + Vite app | 4 test files | Backend and frontend functional |
| Behaviour Linker | Scaffold | Scaffold | — | Not started, design TBD |
| Modeller | Scaffold | Phases 1–4 partial | 35 unit tests | Core editing complete, persistence pending |
| Shared (`packages/semantic`) | — | Contracts + placeholder | builds + tests | Placeholder implementations in place |
| Shared (`backend/core`) | `RdfStore`, legacy loader, full ontology CRUD | — | — | Ontology CRUD complete; shared IRI minting done |
| Model Reuse | — | — | — | Not started |
| Instantiation | — | — | — | Not started |
| Code Generation | — | — | — | Not started |

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
- **Backend:** All v1 steps implemented:
  - `backend/core/graph_store.py` — PROMO vocabulary for Domain,
    ClassificationAxis, AxisTerm, EntityType, ConnectionRule,
    EquationClass. CRUD methods for all. `seed_default_ontology()`
    bootstraps two-branch tree, 7 tokens, role axes, 8 entity types, 3
    connection rules, 5 equation classes.
  - `backend/ontology/models.py` — VariableRecord, EquationRecord,
    DomainRecord, ClassificationAxisRecord, AxisTermRecord,
    EntityTypeRecord, ConnectionRuleRecord.
  - `backend/ontology/service.py` — REST endpoints for domains, axes,
    axis terms, entity types, connection rules, token CRUD.
  - `backend/ontology/rdf_context.py` — domains(), axes(),
    entity_types(), connection_rules() accessors; multi-axis
    classification loading.
- **Frontend:** `apps/ontology-editor/` — all v1 tabs implemented:
  Variables (with multi-axis tagger), Indices, Domains, Tokens, Axes,
  Entity Types, Connection Rules, Equations. TypeScript and Vite
  builds pass clean.
- **Next:** End-to-end testing (backend + frontend together). Then wire
  equation editor to `RdfContext`.

### Equation Editor

- **Backend:** Fully functional parser, checker, compile space, units,
  context protocol, and FastAPI service.  Replaces ProMo13 TPG with a
  hand-written recursive-descent parser.
- **API:** `POST /api/equation/parse`, `POST /api/equation/check`.
- **Tests:** Parser, checker, compile space, units — all passing.
  The ProMo13 corpus replay (73 expressions, 70/73) has been archived
  to `archive/test_corpus.py`; the new regression baseline will be
  expressions re-entered through the equation editor.
- **Frontend:** React + TypeScript + Vite app in `apps/equation-editor/`.
  Features port/dependent variable creation, expression input with a
  single **Check** action, LaTeX preview, error display, variable
  palette with cascade delete, equation list, and a debug equation
  context JSON editor.
- **Next:** Wire the frontend to the ontology graph store.

### Behaviour Linker

- **Design:** Not started.  Role is defined in ADR-004 (selects
  equations for I/O behaviour, assigns graphical representation, spawns
  Graphic Object Editor).
- **Backend:** `backend/behaviour/` — empty scaffold.
- **Frontend:** `apps/behaviour-linker/` — empty scaffold.
- **Next:** Define the behaviour-linking workflow and graphical
  assignment contract.

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
