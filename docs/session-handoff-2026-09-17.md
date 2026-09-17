# Session handoff — 2026-09-17

State of the ProMo14 workspace at end of session.  HEAD `0489b5d`,
branch `main`, pushed to `heinz-preisig/ProMo14`.

## What landed today (4 commits)

| Commit | Content |
|--------|---------|
| `67adbf4` | Publish/export chain: `GET /api/ontology/versions`, `POST /api/ontology/publish`, `GET /api/ontology/export?version=`; Publish button in the ontology editor auto-downloads frozen Turtle; `scripts/export_ontology.py --repo DIR` writes the ProMo-ontologies layout (`ontology/{version}` extensionless + `ontology.ttl`). |
| `3bdb63d` | Versioning machinery: artefact type markers (`promo:Ontology\|Library\|Assignment\|Model\|Glass`), `GET /api/catalogue` (`backend/core/catalogue.py`), hub page `backend/static/hub.html` at `/`, scoped `RdfContext`, frozen-graph guard (`is_frozen`/`assert_editable`), design doc `versioning-and-session-design.md`. |
| `0197117` | `?graph=` on all ontology endpoints; frozen-write → 403; `POST /api/catalogue/new` + `/fork` (fork re-homes instance IRIs to the new namespace); hub actions; ontology-editor session param. |
| `0489b5d` | Equation-editor `?graph=` wiring: pin-scoped `RdfContext` via `RdfStore.resolution_scope` (R4 transitive `usesOntology` closure), shared helpers made public, `api.ts` session param, `test_equation_context_scoped_by_pins`. |

Also today: **w3id verified live** — `curl -L https://w3id.org/promo`
serves the ProMo Ontologies landing page (perma-id/w3id.org#6700
merged).

## Architecture in one paragraph

Everything is a named graph in one `rdflib.Dataset`.  Each graph is an
**artefact line** (working draft + frozen `{graphIRI}/{v}` versions).
Artefacts declare dependencies as `promo:usesOntology` pins.  The hub
(`/`) lists artefact lines; **Open** launches the type's app as
`app?graph=<iri>`; the app forwards the IRI on every call; the backend
resolves vocabulary against the artefact + transitive pin closure
(`scoped_context` → `RdfStore.resolution_scope`).  Frozen graphs reject
writes with 403.  No server-side session — the URL is the context.

App routes: hub `/`, ontology `/ontology`, equation `/equation`,
behaviour `/behaviour` (stub), modeller `/modeller` (no backend calls
yet).  `APPS` map in `hub.html`: ontology→/ontology, library→/equation,
assignment→/behaviour, model+glass→/modeller.

## Key code locations

- `backend/core/graph_store.py` — `RdfStore`: `freeze_version`,
  `is_frozen`/`assert_editable`, `resolution_scope`, `mint_iri`,
  `ancestor_chain`/`effective_tokens`/`tokens_comparable`.
- `backend/core/catalogue.py` — artefact-line grouping for the hub.
- `backend/ontology/service.py` — public helpers `graph_param`,
  `editable_param` (403 on frozen), `resolve_graph`, `scoped_context`;
  all CRUD endpoints take `?graph=`; `resolve_connection` does
  ancestor-aware + scope + token-licensing matching.
- `backend/equation/service.py` — `/context`, `/variables` CRUD scoped
  by `?graph=`; imports the shared helpers from `ontology.service`.
- `backend/static/hub.html` — the hub SPA (vanilla JS, no build).
- `apps/*/src/api.ts` — each reads `?graph=` from `window.location`
  once and appends to every fetch.

## Reproduce on another machine

`data/` is gitignored — the dataset lives in `data/ontology.trig` per
machine.

```bash
git clone git@github.com:heinz-preisig/ProMo14.git   # or git pull
cd ProMo14
uv sync
npm install
./dev.sh wipe-restart        # seeds the current ontology on first load
uv run python scripts/extend_ontology_hap.py   # HAP extensions (idempotent)
./dev.sh restart backend     # pick up the extended file
./dev.sh start               # all services
```

Services: backend :8000, ontology editor :3001, equation editor :3002,
behaviour :3003, modeller :3004.  Logs in `logs/`.  Hub at
`http://localhost:8000/` (backend serves the static page).

Node via `~/.nvm` (v24.19.0) — `source ~/.nvm/nvm.sh` if `npm`/`npx`
are missing.

## Verified

- 138 backend tests pass: `uv run pytest backend/ -x -q`
  (`archive/` ignored — legacy loader tests broken by design).
- `npx tsc --noEmit` clean in `apps/equation-editor` and
  `apps/ontology-editor`.
- w3id redirect live (see above).

## Caveats

- In-memory state: changes persist only via Save / `POST /save`;
  restarting the backend loses unsaved edits.  `data/ontology.trig` is
  the only persistent artefact file so far.
- `usesOntology` pins are accepted by `POST /api/catalogue/new` but not
  yet auto-stamped when artefacts are created inside editors.
- `mint_iri` has no collision check.
- ADR-006 change classification is not yet enforced at publish —
  SHACL shapes are the endorsed mechanism (user likes SHACL; keep away
  from OWL — rdfs:Class/rdf:Property only, no owl:*).

## Next tasks (priority order)

1. **`usesOntology` auto-stamping** at artefact creation in the editors.
2. **Persistence UX** — Save/dirty-state across apps; per-artefact
   `.trig` files (one file per artefact line, per the design doc).
3. **Modeller `ConnectionRuleResolver`** → `GET /api/ontology/resolve-connection`.
4. **SHACL shape checks** at the publish boundary (ADR-006
   re-validation).
5. **BL design/implementation** — see
   `docs/behaviour-linker-design-discussion.md`; assignment artefact =
   named graph with `promo:Assignment`, `hasEquationSequence` (rdf:List),
   state/port/instantiated variable marks.
6. Optional: `promo:Release` manifest; cascade-freezing; reference
   index for "deletion only if unreferenced".

## Ruled contracts (don't re-litigate)

- **R1–R8** in `versioning-and-session-design.md` — ontology is a role;
  pins multi-valued + transitive; per-graph version lines; resolution
  context = pin set; frozen = read-only; glasses = named graphs;
  missing pins fetchable via w3id; draft pins = unstable.
- **Connection rules** — arcs declare variable *sharing*, not cut
  equations; token-flow carries a shared (effort, flow) pair;
  `scope` is branch-relative (`same`/`cross`/`any`); empty sharedTokens
  never applies; token matching = comparability (same root-to-leaf
  path).  `physical-cross` retired.
- **Namespaces** — `promo#` = vocabulary only; instance IRIs mint under
  `{graphIRI}#`; external IRIs (QUDT) referenced as-is.
- **No OWL** — RDFS-level only; skos:exactMatch/closeMatch or
  promo:mappedTo for external links; promo:usesOntology for deps.
