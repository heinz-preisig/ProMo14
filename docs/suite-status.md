# ProMo Suite — Implementation Status

**Last updated:** 2026-09-12 (end of session)

## Summary

| Module | Backend | Frontend | Tests | Status |
|--------|---------|----------|-------|--------|
| Ontology Editor | `RdfStore` + `RdfContext` + service scaffold | Scaffold | `RdfContext` wired | Design complete; v1 ticket ready; implementation pending |
| Equation Editor | Parser + checker + service | React + TypeScript + Vite app | 4 test files | Backend and frontend functional |
| Behaviour Linker | Scaffold | Scaffold | — | Not started, design TBD |
| Modeller | Scaffold | Phases 1–4 partial | 35 unit tests | Core editing complete, persistence pending |
| Shared (`packages/semantic`) | — | Contracts + placeholder | builds + tests | Placeholder implementations in place |
| Shared (`backend/core`) | `RdfStore`, legacy loader | — | — | Initial implementation, needs full graph CRUD |
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
- **Backend:** `backend/ontology/rdf_context.py` (`RdfContext`) and
  `backend/core/graph_store.py` (`RdfStore`) are implemented; the
  `RdfContext` provider is wired and tested.
  `backend/ontology/service.py` is a router scaffold.
- **Frontend:** `apps/ontology-editor/` — UI scaffold; build passes.
- **Next:** Implement v1 per `docs/ontology-editor-v1-ticket.md` (10-step
  sequence: RDF vocabulary → models → graph store → service → RdfContext
  → seed data → frontend types/API → domain tree → variable editor →
  new tabs).

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
- **`backend/core`:** `RdfStore` and legacy v8 loader implemented; shared
  IRI minting and CRUD operations are still pending.
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
