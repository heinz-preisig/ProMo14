# Hub as Suite Entry Point — Gap Ticket

## Context

The versioning/session design (`docs/versioning-and-session-design.md`,
ruled + implemented 2026-09-17) makes the **hub** the suite entry point:
artefact lines in a table, **Open** launches `app?graph=<iri>`, the URL
is the session, resolution scope = artefact + transitive `usesOntology`
pins.

The machinery works, but the choice is still *bypassable* and the
storage layout doesn't reflect it — which is how runtime edits silently
land in the default ontology graph (observed 2026-09-21: port variables
created on another machine were unrecoverable here; the per-machine
`data/` + single-file store hides "what am I working on").

This ticket collects the gaps between the ruled design and the current
behaviour.

## Design reference

- `docs/versioning-and-session-design.md` — R1–R8, storage layout,
  context flow
- `docs/session-handoff-2026-09-17.md` — next-tasks list
- `backend/static/hub.html` — current hub implementation
- `backend/main.py` — SPA routes + catch-all

---

## 1. Make the graph choice unavoidable — DONE (2026-09-23, frontend)

**Problem:** opening an app without `?graph=` falls back to legacy
dataset-wide scope (`scoped_context` default).  Edits then land in the
working ontology graph regardless of intent — silent misattribution.

**Done:** every app's `main.tsx` renders a `MissingGraph` guard (link
to the hub — `http://localhost:8000/` under `import.meta.env.DEV`,
`/` in prod) when `?graph=` is absent.  A redirect to `/` was rejected:
in dev Vite serves the app at `/`, so it would loop.  Applies to all
six apps uniformly — the core ontology is itself a `promo:Ontology`
catalogue line opened via `?graph=`.

**Enforcement landed (2026-09-23):** `editable_param` now 400s when
`?graph=` is absent — writes must name their artefact; reads keep the
legacy dataset-wide default via `graph_param`.  The frontends already
send `?graph=` on every call (`apiFetch`/`withGraph`), so only tests
needed updating: `backend/testing.py::GraphClient` injects the
session's graph IRI on mutating calls that lack one, and each fixture
binds it to the artefact under test (core ontology for
ontology/equation/behaviour/instantiate, a fresh `promo:Model` for
modeller).  Instantiate GETs gained explicit `vars=` — the assignment
graph derives from the artefact the assignments were PUT under
(`<iri>/assignments`), not the legacy default graph.

## 2. Missing SPA routes — DONE (stale ticket)

`main.py` already serves `/modeller/*`, `/behaviour/*`,
`/instantiation/*`, `/species/*` with per-app asset mounts;
`apps/modeller/dist` is built and hub→Open works.  `/behaviour` and
`/species` correctly 404 ("not built") until those apps ship a dist.

## 3. `usesOntology` auto-stamping at creation — DONE (2026-09-23)

**Problem:** `POST /api/catalogue/new` accepts a `uses` pin list, but
artefacts created *inside* editors (new variable library, new model)
don't stamp pins — the dependency edge is never born.

**Done:** no editor has an artefact-creation dialog — the real
loophole was write endpoints *materializing* an empty graph on any
`?graph=` IRI (no type marker, no pins; a pinless graph resolves to
itself only, so such an artefact sees no ontology at all).
`editable_param` now 404s when `?graph=` names an empty graph —
creation goes only through `/api/catalogue/new` or `/fork`, where pins
are born.  Behaviour's `PUT`/`DELETE /assignment` moved from
`graph_param` to `editable_param` (they also lacked the R5 frozen
guard); `_assignment_graph` already stamped the derived assignment
artefact correctly (`uses = resolution_scope(source)`).  Reads keep
the legacy default for tooling.

## 4. Per-artefact `.trig` persistence — DONE

`RdfStore.save()` (no arg) fans out one `.trig` per artefact line —
the draft graph plus its `versionOf` children ("the file is the
history") — named by the line IRI's last segment (`lib.trig`), with a
hash suffix on slug collision.  The ontology line keeps the tracked
`ontology.trig` name; default-graph triples ride along in it.  Stale
line files are removed on save.  `save(filename)` remains as the
explicit whole-dataset single-file export.  `load()` detects a legacy
single-file `ontology.trig` (non-empty graphs outside the ontology
line) and splits it on first load.  `POST /api/ontology/save` with no
`filename` (all editors, `dev.sh save`) uses the fan-out.

## 5. Hub UX gaps — DONE (2026-09-23)

**File:** `backend/static/hub.html`

- **Frozen versions open read-only** — every version row gets an
  `open` button targeting the version graph IRI in the line's app;
  writes are rejected server-side by the R5 frozen guard
  (`editable_param` → 403).
- **Creation form replaces `prompt()`** — type select, IRI (default
  per type until touched), label, and pin multi-selects populated
  from the catalogue: ontology lines for `usesOntology`, species
  lines for `usesSpecies`, each offering the draft IRI and every
  frozen version IRI (pinning a version is the reproducible choice).
- **Dirty-guard on switch** — the hub polls `GET /api/ontology/status`
  (5 s) and confirms before Open/Instantiate when the store is dirty.
- **Save affordance** — toolbar Save button + `● unsaved changes`
  badge, shown while `dirty` (POST `/api/ontology/save`, the
  per-line fan-out).

## 6. Dev-mode entry split — DONE (2026-09-23)

**Problem:** hub→Open navigates to `:8000/<app>/` which serves the
*built* SPA (`apps/*/dist`), while development happens on the Vite
servers (`:3001`–`:3005`).  A developer iterating on an app never
touches the hub flow.

**Done:** the hub honours a `?dev` URL flag — Open then targets the
Vite dev servers (`DEV_PORTS` map in `hub.html`: ontology 3001,
library→equation 3002, assignment→behaviour 3003, model/glass→
modeller 3004, species 3005).  A toolbar toggle switches modes.
Instantiation has no `dev.sh` service and stays on the backend path
in both modes.  `?graph=` is required in both modes (the apps'
`MissingGraph` guard enforces it).

**Also fixed:** `apps/instantiation/vite.config.ts` claimed port
3004, colliding with modeller — moved to 3006.

---

## 7. Seed-floor migrations for user artefact graphs — DONE (2026-09-23)

**Problem:** `RdfStore.load()` applies idempotent floor migrations
(`_seed_constants`, `_seed_scale_regimes`, `_seed_transport_mechanisms`,
`_seed_arc_sub_indices`) to the **core ontology graph only**.  Forked
ontologies never receive new seed content — silent semantic drift:
engines find no declared capabilities in a stale fork and return empty
distributions with no error.

**Done:** the ordered seed sequence is factored into
`RdfStore.apply_seed_floor(g, base)` — shared by `load()` (core graph,
still automatic: suite-owned, additive, idempotent),
`seed_default_ontology()`, and the new
`POST /api/ontology/apply-seed-floor?graph=` endpoint (opt-in for
forks).  The endpoint requires the `promo:Ontology` marker (422
otherwise — models/libraries consume semantics via pins, seeding them
would pollute them with ontology vocabulary) and a draft graph
(`editable_param`: 404 unknown, 403 frozen — "the file is the
history").  Scope is deliberately narrower than the ticket stated:
only `promo:Ontology` drafts are candidates.

**Staleness is visible, not silent:** `apply_seed_floor` stamps
`promo:seedFloor "2026-09"` (`SEED_FLOOR` in `graph_store.py` — bump
when any `_seed_*` step's content changes).  `GET /api/catalogue`
reports `seedFloor`/`staleFloor` per draft ontology line plus the
current floor at top level; the hub shows an **update floor** badge
that POSTs the endpoint — user-consented, never auto-applied to user
graphs.  `fork_graph` carries the stamp across (the copy has the
source's floor content, so it inherits the source's staleness state).

## Out of scope (already ruled)

- No server-side session — the URL stays the context (R4/context flow).
- No per-app "which ontology?" dialog — pins answer it per artefact.
