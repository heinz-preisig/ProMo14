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

## 1. Make the graph choice unavoidable

**Problem:** opening an app without `?graph=` falls back to legacy
dataset-wide scope (`scoped_context` default).  Edits then land in the
working ontology graph regardless of intent — silent misattribution.

**Files:** `apps/*/src/api.ts`, app entry components,
`backend/ontology/service.py` (`graph_param`/`scoped_context`).

**Options:**

- App without `?graph=` redirects to the hub (`/`) — simplest, matches
  "switching subject = back to the hub".
- Or app shows an artefact picker that sets `?graph=` and reloads.
- Backend could additionally *require* `?graph=` on write endpoints
  (defence in depth); reads may keep the legacy default for tooling.

## 2. Missing SPA routes

**Problem:** `main.py` serves `/ontology/*` and `/equation/*` plus the
hub catch-all.  `/modeller` and `/behaviour` have no routes — hub→Open
for model/glass artefacts serves the hub page again.

**Files:** `backend/main.py` (add `MODELLER_STATIC_DIR` +
`serve_modeller_spa`; behaviour when it gets a UI).

## 3. `usesOntology` auto-stamping at creation

**Problem:** `POST /api/catalogue/new` accepts a `uses` pin list, but
artefacts created *inside* editors (new variable library, new model)
don't stamp pins — the dependency edge is never born.

**Files:** `backend/ontology/service.py`, `backend/equation/service.py`,
`backend/core/catalogue.py`; editor creation dialogs should offer the
pin set (default: current resolution scope).

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
