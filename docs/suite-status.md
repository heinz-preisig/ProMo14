# ProMo Suite — Implementation Status

**Last updated:** 2026-09-10

## Summary

| Module | Backend | Frontend | Tests | Status |
|--------|---------|----------|-------|--------|
| Ontology Editor | Scaffold | Scaffold | — | Design complete, not implemented |
| Equation Editor | Parser + checker + service | Placeholder | 5 test files, corpus replay | Backend functional, frontend not started |
| Behaviour Linker | Scaffold | Scaffold | — | Not started, design TBD |
| Modeller | Scaffold | Phases 1–4 partial | 35 unit tests | Core editing complete, persistence pending |
| Shared (`packages/semantic`) | — | Contracts + placeholder | 9 tests | Placeholder implementations in place |
| Shared (`backend/core`) | Scaffold | — | — | Not started |
| Model Reuse | — | — | — | Not started |
| Instantiation | — | — | — | Not started |
| Code Generation | — | — | — | Not started |

## Module details

### Ontology Editor

- **Design:** Complete — see `docs/ontology-editor-design.md`,
  `docs/ontology-data-model.md`, ADR-006.
- **Backend:** `backend/ontology/` — empty scaffold.
- **Frontend:** `apps/ontology-editor/` — empty scaffold.
- **Next:** Implement backend graph store and `RdfContext` provider;
  build frontend domain tree + variable table + detail editor.

### Equation Editor

- **Backend:** Fully functional parser, checker, compile space, units,
  context protocol, and FastAPI service.  Replaces ProMo13 TPG with a
  hand-written recursive-descent parser.
- **API:** `POST /api/equation/parse`, `POST /api/equation/check`.
- **Tests:** Parser, checker, compile space, units, and corpus replay
  (73 expressions from ProMo13 — all parse, 28/73 pass full checks due
  to missing index structures, units, and domain tree in the old
  export).
- **Frontend:** Placeholder only — `apps/equation-editor/README.md`.
- **Known issues:** See `docs/equation-editor-known-issues.md`.
- **Next:** Build React frontend (expression input, variable palette,
  LaTeX preview, error display, equation list).

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
- **`backend/core`:** Empty scaffold — future home of shared RDF store,
  IRI minting, ontology client.
- **`backend/main.py`:** FastAPI app mounting per-tool routers.

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
cd /home/heinz/1_Gits/CAM14/ProMo14/backend
pip install -r requirements.txt
python -m pytest equation/     # run equation tests
uvicorn main:app --reload      # start API server
```
