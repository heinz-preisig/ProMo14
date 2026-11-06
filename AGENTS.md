# ProMo14 — agent bootstrap

**Read `docs/design-principles.md` first.**  It records the suite's
global ideas and deliberate deviations from mainstream modelling —
symbolic-only equations, semantics-in-ontology, the three-layer token
model, artefact-line graph architecture.  The rationale lives there;
enforcement lives in the ontology and the test suite.

## Environment

- Python via `uv` (`.venv`, 3.13): `uv run pytest backend/ -x -q`
- Node via nvm — not on PATH: `source ~/.nvm/nvm.sh` first
- Services: `./dev.sh start|stop|status|save|wipe-restart [service]`
- Persist in-memory store → `data/*.trig`: `POST /api/ontology/save`
  or `./dev.sh save`

## Hard rules

- `data/*.trig` is serialized persistence — **APIs only, never
  hand-edit**.  In-memory store; Save/POST /save persists.
- Semantics lives in the ontology (`promo#` vocabulary = types only,
  instance IRIs under `{graphIRI}#`).  Extend the ontology, never
  special-case code.  No OWL — RDFS only.
- Equations are purely symbolic (no numeric literals); instantiation
  carries literal numbers only.  Computed values → `initialise`-class
  equations.
- After any frontend source edit, rebuild the dist before the user
  refreshes: `npm run build -w @promo/<app>` (source nvm first on
  machines that have it; hub serves `apps/*/dist`, not Vite sources).
- Writes need `?graph=` on `editable_param` endpoints; reads take
  lenient `graph_param` and resolve across the artefact's scope.

## House style

- Minimal upstream fixes over downstream workarounds; root cause first.
- Regression test for every semantic rule that's been ruled.
- Commit messages: conventional (`feat(scope): …`).

## Design review

Run `.devin/workflows/design-review.md` on a regular cadence (~weekly
or every ~10 semantic commits): audits the repo against
`design-principles.md` and keeps the principles doc refined.
