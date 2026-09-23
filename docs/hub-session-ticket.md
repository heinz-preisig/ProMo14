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

**Deferred:** backend enforcement (`?graph=` required on write
endpoints).  The test suite deliberately exercises the legacy default
(~15 call sites across equation/modeller/species/behaviour tests write
without `?graph=`); enforcement needs those fixtures to create
artefact graphs first.  Revisit when per-artefact `.trig` lands.

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

## 4. Per-artefact `.trig` persistence

**Problem:** the whole dataset serialises to one `data/ontology.trig`.
The design says one file per artefact line (draft + its frozen
versions); "the file is the history".  Single-file storage also makes
per-machine sync all-or-nothing.

**Files:** `backend/core/graph_store.py` (`load`, `save`, `freeze_version`),
`dev.sh` wipe semantics, `data/README.md`.

**Notes:** `load()` already globs `*.trig`; the work is in `save()`
(fan-out per artefact line) and `freeze_version` (keep versions in the
line's file).  Migration: split existing `ontology.trig` on first load.

## 5. Hub UX gaps

**File:** `backend/static/hub.html`

- **Open always targets the draft line IRI** — no way to open a frozen
  version read-only (versions list only offers `export` for ontologies).
- **`prompt()`-based creation** — no pin picker, no type validation;
  replace with a small form (type select, IRI, label, pin multi-select
  populated from the catalogue).
- **No dirty-guard on switch** — leaving an artefact with unsaved
  changes gives no warning (the store-global dirty flag exists;
  `GET /api/ontology/status` already exposes it).
- **No "save" affordance** in the hub itself.

## 6. Dev-mode entry split

**Problem:** hub→Open navigates to `:8000/<app>/` which serves the
*built* SPA (`apps/*/dist`), while development happens on the Vite
servers (`:3001`–`:3004`).  A developer iterating on an app never
touches the hub flow.

**Options:** hub links honour a dev flag/port map; or document that
`:8000` is the "user mode" entry and `:300x` is "dev mode" — with
`?graph=` still required in both.

---

## 7. Seed-floor migrations for user artefact graphs (opt-in)

**Problem:** `RdfStore.load()` applies idempotent floor migrations
(`_seed_constants`, `_seed_scale_regimes`, `_seed_transport_mechanisms`,
`_seed_arc_sub_indices`) to the **core ontology graph only**.  Forked
ontologies and other artefact graphs never receive new seed content —
and there is no explicit "apply current seed floor to this graph"
operation.

**Files:** `backend/core/graph_store.py` (`load`, the `_seed_*`
methods), `backend/ontology/service.py` (a `POST …/migrate` or
`apply-seed-floor` endpoint taking `?graph=`).

**Policy questions:** should migrations stay automatic for the core
graph (current behaviour — additive, idempotent, edit-preserving) or
become opt-in?  For user graphs the answer is clearly opt-in — the
endpoint just doesn't exist yet.

## Out of scope (already ruled)

- No server-side session — the URL stays the context (R4/context flow).
- No per-app "which ontology?" dialog — pins answer it per artefact.
