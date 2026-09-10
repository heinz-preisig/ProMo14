# ProMo Suite

Browser-based modelling tool suite. npm workspaces monorepo:

- `apps/modeller` — model composer prototype (React + Konva)
- `apps/ontology-editor`, `apps/equation-editor`, `apps/behaviour-linker` — scaffolds
- `packages/semantic` — shared IRI contracts, catalogue, connection rules
- `backend/` — Python FastAPI backend (per-tool routers + shared core)

```bash
npm install
npm run dev    # starts the modeller on :3000
npm test       # all workspace tests
```
