# ProMo Suite

Browser-based physics modelling tool suite.  npm workspaces monorepo
with Python FastAPI backend.

## Modules

- `apps/modeller` — graphical model composer (React + Konva)
- `apps/equation-editor` — equation editor frontend (scaffold; backend exists)
- `apps/ontology-editor` — ontology editor frontend (scaffold)
- `apps/behaviour-linker` — behaviour linker frontend (scaffold)
- `packages/semantic` — shared IRI contracts, catalogue, connection rules
- `backend/` — Python FastAPI backend (per-tool routers + shared core)

## Quick start

```bash
npm install
npm run dev    # starts the modeller on :3000
npm test       # all workspace tests
```

## Documentation

See `docs/suite-overview.md` for the cross-cutting architecture,
pipeline, and inter-module contracts.  Each tool has its own overview
and status document:

- Suite: `docs/suite-overview.md` + `docs/suite-status.md`
- Modeller: `docs/modeller-overview.md` + `docs/modeller-status.md`
- Equation Editor: `docs/equation-editor-overview.md` + `docs/equation-editor-status.md`
- Ontology Editor: `docs/ontology-editor-overview.md` + `docs/ontology-editor-status.md`
- Behaviour Linker: `docs/behaviour-linker-overview.md` + `docs/behaviour-linker-status.md`

Decision records (ADRs) and detailed technical references are listed in
`docs/suite-overview.md` §8.
