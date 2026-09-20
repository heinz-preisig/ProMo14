# ProMo Suite — Implementation Status

**Last updated:** 2026-09-20

## Summary

| Module | Backend | Frontend | Tests | Status |
|--------|---------|----------|-------|--------|
| Hub + Catalogue | `GET /api/catalogue`, `POST /new`, `POST /fork` | `backend/static/hub.html` at `/` | covered by service tests | **Working** — artefact lines, pins, fork, open-in-app |
| Ontology Editor | `RdfStore` + `RdfContext` + full CRUD + seed data + rule resolution + versioning (`freeze_version`, publish/export) | React UI with all v1 tabs + Publish button | TypeScript + Vite build pass | **v1 verified end-to-end**; `?graph=` session param wired |
| Equation Editor | Parser + checker + codegen + LaTeX document; `?graph=` pin-scoped context + artefact-graph writes | React + TypeScript + Vite app | 6 test files, 119 tests | Backend and frontend functional; `?graph=` wired |
| Behaviour Linker | Scaffold | Scaffold | — | Design discussion started (see `docs/behaviour-linker-design-discussion.md`) |
| Modeller | `GET`/`PUT /api/modeller/model` (ADR-007) | Phases 1–4 partial | 35 unit tests | Core editing + persistence working; ontology-backed catalogue + rule resolver live |
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
  entity types from CWA 17960, 5 connection rules, transport system
  as node (not arc), event dynamics fits existing taxonomy.
- **Backend:** All v1 steps implemented and verified:
  - `backend/core/graph_store.py` — PROMO vocabulary for Domain,
    ClassificationAxis, AxisTerm, EntityType, ConnectionRule,
    EquationClass. CRUD methods for all. `seed_default_ontology()`
    bootstraps two-branch tree, 7 tokens, role axes, entity types, 5
    connection rules, 5 equation classes, indices (species/node/arc +
    7 arc sub-indices).  `add_domain`/`add_connection_rule` use replace
    semantics for `hasToken`/`sharedTokens`.
  - Seeded structure (2026-09-20): transport entity tree grouped by
    token (`mass_transport` {diffusion, convection}, `energy_transport`
    {heat, radiation, work}); arc sub-indices via
    `promo:subIndexOf`/`promo:selector`; `particulate`|`continuum`
    regime grouping atop both scale trees; two-tier seed contract
    (initial-state vs floor migrations, core graph only).  Design:
    BL doc §16–17.
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
- **Connection rules (5 seeded):** `physical-same` (bidirectional,
  token-flow, same-branch, physical↔physical, licenses all conserved
  tokens), `signal` (reference, same-branch, information-internal),
  `access` (reference, same-branch, physical↔physical service coupling),
  `sensor` (reference, cross-branch, physical→information, observation
  subtoken), `actuation` (reference, cross-branch, information→physical,
  manipulation subtoken).  Rule attributes: `direction`, `carrier`
  (token-flow | reference), `scope` (same | cross | any, branch-relative),
  `sharedTokens` (the license).  `GET /resolve-connection` walks domain
  ancestor chains, filters by scope, then requires a licensed token to be
  comparable to a comparable effective-token pair on the endpoints —
  returns matching rules + `matched_tokens`, most-specific first.
  `carrier` → `arcTypeIri = promo:ArcType/<carrier>` (arcs are typed
  token-flow or reference; the rule name is the kind, not the arc type).
- **Namespace:** `https://w3id.org/promo#` throughout
  (`backend/core/graph_store.py`: `PROMO`, `PROMOLG`,
  `ONTOLOGY_GRAPH_IRI`).  Publishing pipeline live end-to-end: exported
  `ontology.ttl` → `heinz-preisig/ProMo-ontologies` (GitHub Pages) →
  w3id redirect **verified live** (PR #6700 merged).  See
  `publish/README.md`.
- **Next:** Auto-stamp `usesOntology` at artefact creation; SHACL shape
  checks at the publish boundary (ADR-006).  (Modeller consumes
  `resolve-connection` since 2026-09-18 — see Modeller section.)

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
- **Codegen (2026-09-18):** `POST /api/equation/generate` renders the
  checked tree to python (NumPy, provisional), matlab (`MultiDimVar`
  Einstein library, vendored at `runtime/matlab/@MultiDimVar`), and
  LaTeX; `GET /api/equation/document` renders a printable landscape
  article (Jinja2, variables + equations tables by network).
- **LaTeX symbols (2026-09-18):** per-variable `promo:latex` alias —
  editable in every variable-definition GUI (port + dependent editors,
  detail modal); preview + codegen + document render it verbatim.
  Index short names capitalised (S/N/A/Q) in seed + persisted data.
- **`Instantiate` redesigned (2026-09-19, ADR-008):**
  `Instantiate(proto)` — single `Var` argument, whole-RHS declaration
  only; the LHS variable becomes a new *instance* of the prototype
  (inherits units + index structure, empty incidence, LHS class
  enforced to `constant`/`parameter`).  Universal constants
  `zero`/`one`/`half` seeded with pre-bound `promo:value`;
  `promo:instanceOf` provenance + `equation_class="instantiate"`
  written at save.
- **Next:** RDF vocabulary finalization for equations/operators;
  LaTeX→image cache deferred.  (Persistence UX done 2026-09-18:
  store-global dirty tracking + Save button + unsaved badge.)

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
- **Backend:** `backend/modeller/service.py` — `GET`/`PUT
  `/api/modeller/model` (ADR-007, 2026-09-18).  Known gap: `main.py`
  has no `/modeller` SPA route — hub→model links hit the hub
  catch-all (2026-09-20).
- **Features:** Node/arc creation, drag, selection, deletion,
  three-panel hierarchy navigation, composite grouping, open-arc
  reconnection, pan/zoom, catalogue-resolved graphics,
  connection-rule enforcement.
- **Resolver:** `RemoteRuleResolver` (`packages/semantic`) consumes
  `GET /api/ontology/resolve-connection` — sync cache for hover
  feedback, `resolveAsync` for connect actions, `carrier` →
  `promo:ArcType/<carrier>` mapping, placeholder fallback when the
  backend is down (2026-09-18).
- **Catalogue:** `RemoteCatalogue` (`packages/semantic`) loads
  entity-types/domains/tokens/connection-rules over injected fetchers
  and exposes them via the sync `SemanticCatalogue` interface —
  entity `branch` → top-level domain IRI → `domainTypeIris` (new field
  on `BaseEntityDefinition`), arc types synthesised from rule carriers,
  graphicals delegated to the placeholder catalogue, whole-catalogue
  fallback when the backend is down (2026-09-18).  `buildConnectionQuery`
  now populates domain IRIs, so `resolve-connection` gets real domain
  pairs.  8 tests in `remoteCatalogue.test.ts`.
- **Persistence:** ADR-007 — artefact graph = one model document;
  `GET`/`PUT /api/modeller/model` (2026-09-18).
- **Next:** composition and scale (reusable composite insertion,
  provenance, port mapping; on-demand graph access for large models).
  Note: entity types carry only their top-level branch — rules scoped
  to subdomains won't match until entities get finer domain assignment.
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

### Dev orchestrator (preferred)
```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
./dev.sh start all        # backend :8000 + all app dev servers
./dev.sh start ontology   # one app — ensures backend, fresh-starts the app
./dev.sh status           # ports, PIDs, hub URL
./dev.sh stop backend     # warns if the ontology store is dirty
```
`start` always kills whatever holds the port first (fresh code);
app starts *ensure* the backend but never bounce it (unsaved-store
safety).  Hub: `http://localhost:8000/`.

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
