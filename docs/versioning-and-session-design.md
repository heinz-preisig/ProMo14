# Versioning & Session Design — Artefact Lines, Pins, and the Hub

Status: ruled 2026-09-17 (design discussion); **implemented 2026-09-17**
(commits `3bdb63d`, `0197117`, `0489b5d`).  Remaining gaps are listed
under Deferred + the handoff doc.

Extends ADR-006 (ontology evolution) and the artefact-chain ruling in
`ontology-review-2026-09-17.md` §3 item 7.

## Scope

The version domain is the **data domain**: ontology, var/expr libraries,
BL assignments, models, glasses.  Generated code is *derived* — not
versioned, carries `promo:generatedFrom` provenance.  The tool suite
itself (Docker image) is software distribution, outside this domain.

## Rulings

**R1 — "Ontology" is a role, not a singleton.**  Any named graph can
play the ontology role: ProMo core, a user-built ontology, a domain
extension, a third-party vocabulary.  `ONTOLOGY_GRAPH_IRI` is a default,
not an assumption.  Users generating their own ontologies is the
designed-for case.

**R2 — `promo:usesOntology` is multi-valued and transitive.**  Artefact
graphs pin the *set* of ontology graphs they were checked against
(core + extensions).  Ontology extensions themselves pin what they
extend.  A pin set is coherent iff every pinned graph's own pins are
satisfied within the set — a transitive walk at load/publish, no solver.

**R3 — Versions are per-graph lines.**  `{graphIRI}/{v}`; each artefact
line carries its own history.  No cross-artefact version numbers —
release rhythms must not be coupled.

**R4 — Resolution context = the pin set.**  `RdfContext(store,
graph_iris=[...])` replaces the hardcoded working-graph binding.
Opening an artefact resolves vocabulary against its pins; working with
an old version and working with a foreign ontology are the same code
path.

**R5 — Frozen means read-only, enforced.**  A graph whose identifier is
`a promo:Version` refuses writes — enforced at the store/service layer,
not by accident of nothing writing to it.

**R6 — Glasses unify under the same mechanism.**  A glass is a named
graph pinning the domain ontology it skins.  Different entity sets,
different models per domain — all graphs with pins, no special
machinery.

**R7 — Missing pins are fetchable.**  Published graphs dereference via
w3id → GitHub Pages; a dependency absent locally can be pulled by IRI.
Private ontologies travel as `.trig` in the data dir.

**R8 — Pins may target a draft, meaning "unstable".**  A pin to a
working graph signals revalidation on next freeze; `freeze_version`
offers to re-pin dependents to the new version IRI.  Pins to version
IRIs are the stable form.

## Storage: one file per artefact line

- `data/*.trig` flat.  Each file holds one artefact line: working draft
  graph + all its frozen version graphs.  The file *is* the history.
- Filenames are convenience; graph IRIs are identity.  No path carries
  semantics.
- Generated outputs (LaTeX, code) live under `data/generated/{artefact}/`
  — derived files, outside the catalogue.

## Catalogue and hub

`GET /api/catalogue` returns **artefact lines**, not raw graphs:

```json
{ "iri": "…/ontology", "type": "ontology", "label": "ProMo core",
  "status": "draft",
  "versions": [{"version": "1.0", "iri": "…/ontology/1.0"}],
  "usesOntology": [] }
```

Type marker stamped at creation:
`<graphIRI> a promo:Ontology | promo:Library | promo:Assignment |
promo:Model | promo:Glass`.  Frozen graphs self-mark via
`a promo:Version` (already implemented in `freeze_version`).

The **hub** is the suite entry point — a flat table, not a tree and not
a wizard.  Every artefact line is a row: label · type · status · pins
as chips · actions.  Actions: **Open** (launches the type's app),
**Fork** (frozen → new draft line), **Publish**, **Export**.  "New …"
buttons per type; creating an artefact asks for its ontology pin set —
pins are born at creation, never retrofitted.

This replaces old ProMo's per-app "which ontology?" question and its
`data/{ontology}/{model-lib}` directory hierarchy.  The directory path
was the dependency mechanism; pins are the mechanism now — multi-valued,
version-precise, queryable, and indifferent to layout.

## Context flow: stateless, in the URL

Hub → `app?graph=<iri>` → app forwards the IRI → backend builds
`RdfContext` on the artefact's pin set (for an ontology, the graph
itself).  No server-side session; the URL is bookmarkable; switching
subject = back to the hub.

## Fork: how "my own ontology" starts

Copy graph → new IRI → **re-home instance IRIs** to the new graph's
namespace (required — shared IRIs would merge under union semantics;
the namespace migration machinery already does this) → stamp
`promo:versionOf`/`derivedFrom`.  Or start empty.  Either way a new
line appears in the catalogue.

## Deferred

- `promo:Release` manifest naming coherent sets — pins answer "what
  belongs together"; add only if naming proves needed.
- Cascade-freezing — each artefact re-validates and freezes on its own
  publish.
- SHACL shapes per artefact type at the publish boundary (ADR-006
  re-validation) — the endorsed mechanism when artefact persistence
  lands.
- Reference index for "deletion only if unreferenced".

## Implementation order — all landed 2026-09-17

1. ✅ Type markers + `GET /api/catalogue` (`backend/core/catalogue.py`;
   `ARTEFACT_TYPES` stamped in seed, migrated on load, copied to frozen
   graphs in `freeze_version`)
2. ✅ `RdfContext(store, graph_iris)` + write-block on frozen graphs
   (`is_frozen`/`assert_editable` on `RdfStore`)
3. ✅ Hub page (`backend/static/hub.html`, served at `/`; equation SPA
   moved to `/equation`, ontology stays `/ontology`)
4. ✅ `?graph=` params in the apps — ontology editor + equation editor
   (`api.ts` reads the param once, appends to every call); backend
   helpers `graph_param`/`editable_param`/`resolve_graph`/
   `scoped_context` in `backend/ontology/service.py` are public and
   shared with `backend/equation/service.py`
5. ✅ Fork endpoint (`POST /api/catalogue/fork` re-homes instance IRIs
   to the new graph's namespace; `POST /api/catalogue/new` accepts a
   `uses` pin list)

**R4 refinement beyond the original sketch:** the resolution context is
not just the artefact graph — it is the artefact plus its *transitive*
`usesOntology` closure, computed by `RdfStore.resolution_scope()` (BFS,
cycle-safe, artefact first).  `scoped_context()` builds `RdfContext`
over that set; `?graph=` absent keeps the legacy dataset-wide scope.
Regression test: `test_equation_context_scoped_by_pins`.
