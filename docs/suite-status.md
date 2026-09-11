# ProMo Suite — Implementation Status

**Last updated:** 2026-09-11 (end of session)

## Summary

| Module | Backend | Frontend | Tests | Status |
|--------|---------|----------|-------|--------|
| Ontology Editor | `RdfStore` + `RdfContext` + service scaffold | Scaffold | `RdfContext`/corpus wired | Phase 0/1 backend done; CRUD pending |
| Equation Editor | Parser + checker + service | React + TypeScript + Vite app | 5 test files, corpus 70/73 | Backend and frontend functional |
| Behaviour Linker | Scaffold | Scaffold | — | Not started, design TBD |
| Modeller | Scaffold | Phases 1–4 partial | 35 unit tests | Core editing complete, persistence pending |
| Shared (`packages/semantic`) | — | Contracts + placeholder | builds + tests | Placeholder implementations in place |
| Shared (`backend/core`) | `RdfStore`, legacy loader | — | corpus replay | Initial implementation, needs full graph CRUD |
| Model Reuse | — | — | — | Not started |
| Instantiation | — | — | — | Not started |
| Code Generation | — | — | — | Not started |

## Module details

### Ontology Editor

- **Design:** Complete — see `docs/ontology-editor-design.md`,
  `docs/ontology-data-model.md`, ADR-006.
- **Backend:** `backend/ontology/rdf_context.py` (`RdfContext`) and
  `backend/core/graph_store.py` (`RdfStore`) are implemented; the
  `RdfContext` provider is already used by the equation corpus test.
  `backend/ontology/service.py` is a router scaffold.
- **Frontend:** `apps/ontology-editor/` — UI scaffold; build passes.
- **Next:** Extend `RdfContext` to read all named graphs and the new
  lowercase TriG types; build frontend domain tree + variable table +
  detail editor.

### Equation Editor

- **Backend:** Fully functional parser, checker, compile space, units,
  context protocol, and FastAPI service.  Replaces ProMo13 TPG with a
  hand-written recursive-descent parser.
- **API:** `POST /api/equation/parse`, `POST /api/equation/check`.
- **Tests:** Parser, checker, compile space, units, and corpus replay
  (73 expressions from ProMo13 — all parse, **70/73** pass full checks
  now that real index structures, units, and the domain tree are loaded
  from the v8 ontology data).
- **Frontend:** React + TypeScript + Vite app in `apps/equation-editor/`.
  Features port/dependent variable creation, expression input with a
  single **Check** action, LaTeX preview, error display, variable
  palette with cascade delete, equation list, and a debug equation
  context JSON editor.
- **Known issues:** See `docs/equation-editor-known-issues.md`.
- **Next:** Switch corpus test to the new arc/connection TriG data; wire
  the frontend to the ontology graph store.

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
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# run compile-space tests
.venv/bin/python -m backend.equation.test_compile_space

# run corpus replay
PROMO13_CORPUS_TTL=/home/heinz/1_Gits/CAM13/ProMo13/packages/Common/ontologies/var_equ_rdf.ttl \
  .venv/bin/python -m backend.equation.test_corpus

# start API server
.venv/bin/uvicorn backend.main:app --port 8000
```

### Equation editor (frontend)
```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
npm install
npm run dev:equation  # Vite dev server on http://localhost:3001
```
