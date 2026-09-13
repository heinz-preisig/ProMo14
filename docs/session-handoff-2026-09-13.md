# Session Handoff — 2026-09-13

This file captures the state of the ProMo14 workspace at the end of the
2026-09-13 session, so the work can be continued on another machine.

## TL;DR

- Ontology editor v1 **implemented and verified** — backend, frontend,
  and seed data all working.  TypeScript and Vite builds pass clean.
  Backend API returns all seed entities.  Frontend served both via
  Vite dev server (port 3002) and via backend static serving
  (`/ontology/` on port 8000).
- Design discussions continued:
  - Scales as first-class concept (§13, §25 in design discussion doc).
  - Triple domain lives within time scale hierarchy (Option B).
  - Behaviour Linker design discussion started
    (`docs/behaviour-linker-design-discussion.md`).
- No code changes were made this session — the session was primarily
  design discussion + verification that the v1 implementation from
  Sep 12 still works.
- Next: end-to-end testing (manual UI verification), then wire equation
  editor to RdfContext.

## Environment

- Repo: `/home/heinz/1_Gits/CAM14/ProMo14`
- Data (legacy v8 + no-interface TriG):
  `/home/heinz/1_Gits/CAM13/Ontology_Repository/processes_distributed_no_interface_eqs`
- Python: `uv sync` (creates `.venv` automatically, uses `uv.lock`)
- Node: managed by `nvm`; `npm install` from repo root.

## Quick start on a new machine

```bash
cd /home/heinz/1_Gits/CAM14/ProMo14

# Node / frontends
npm install
npm run build        # workspace build; should pass

# Python / backend
uv sync

# Compile-space unit tests
uv run python -m backend.equation.test_compile_space

# Backend server
uv run uvicorn backend.main:app --port 8000 &
curl http://localhost:8000/api/health   # -> {"status":"ok"}

# Ontology editor (Vite dev server)
cd apps/ontology-editor && npx vite --port 3002
# Open http://localhost:3002/ontology/

# Or: build and serve via backend
cd apps/ontology-editor && npx vite build
# Then http://localhost:8000/ontology/
```

## Verification results (2026-09-13)

| Check | Result |
|------|--------|
| Backend imports | OK |
| Seed data (257 triples) | 2 domains, 7 tokens, 8 entity types, 27 scale values, 3 rules, 2 axes, 11 terms |
| `/api/ontology/context` | Returns all entities correctly |
| `/api/ontology/tokens` | Returns 7 tokens |
| `/api/ontology/domains` | Returns 2 domains with token bindings |
| `/api/ontology/scale-values` | Returns 27 scale values with hierarchy |
| TypeScript (`tsc --noEmit`) | Pass |
| Vite build (ontology-editor) | Pass (169.86 kB JS) |
| Vite dev server (port 3002) | Serves correctly |
| Backend static serving (`/ontology/`) | Serves correctly |

## What was done this session

### Design discussion (no code changes)

1. **Scales as first-class concept (§13)** — Time scale and length
   scale are NOT variable classification axes.  They classify base
   entities.  Scales have dimensions (time, length, user-defined) with
   hierarchical value trees.  Entity types become compositions of
   scale values, not hardcoded CWA 17960 fields.  CWA 17960's
   temporal×spatial becomes a seed/default, not a schema.

2. **Triple domain as scale values — Option B (§25)** — The temporal
   triple domain (constant / dynamic / event-dynamic) lives WITHIN the
   time scale hierarchy as child values of each scale level.  Time
   scale: 4 levels (molecular, nano, milli, macro), each with 3
   children.  Length scale: 4 levels (infinitesimal, microscopic,
   macroscopic, infinite), each with spatial sub-values.  Legacy
   `temporal_type`/`spatial_type`/`spatial_size` kept for backward
   compat; canonical definition is scale value composition.

3. **Behaviour Linker design discussion started** — Core mechanic
   defined: BL reads ontology + var/expr bipartite graph, user selects
   state-defining equation, RHS variables resolved recursively.
   Hint/binding pattern: ontology tags are hints, BL selections are
   bindings.  State is emergent (structural property of equation
   subgraph, not a label).  Transport system has no state (no cycle).
   See `docs/behaviour-linker-design-discussion.md`.

4. **Other design topics** — Graphical language (§14), glasses
   (§15, §20), three-level graphics model (§19-21), downstream
   coupling (§17), CWA 17960 in perspective (§18).

### Updated documents

- `docs/ontology-design-discussion-2026-09-11.md` — added §13 (scales),
  §14 (graphical language), §15 (glasses), §17-21, §25 (triple domain
  Option B).
- `docs/behaviour-linker-design-discussion.md` — new design discussion
  doc started.

## Current state of the codebase

No code changes from Sep 12.  The ontology editor v1 implementation
from Sep 12 is intact and working:

- `backend/core/graph_store.py` — PROMO vocabulary, CRUD methods,
  `seed_default_ontology()` with 257 triples.
- `backend/ontology/service.py` — REST endpoints for domains, axes,
  axis terms, entity types, connection rules, tokens, scale dimensions,
  scale values, indices, networks, save.
- `backend/ontology/rdf_context.py` — RdfContext with domains(),
  axes(), entity_types(), connection_rules() accessors.
- `apps/ontology-editor/src/App.tsx` — 765 lines, 7 stage tabs:
  Tokens, Domains, Axes, Scales, Entity Types, Indices, Rules.
- `apps/ontology-editor/src/api.ts` — 282 lines, API functions for
  all endpoints.
- `apps/ontology-editor/src/types.ts` — 181 lines, full type
  definitions.

## Next concrete tasks

1. **End-to-end testing** — Start backend + Vite dev server, open
   browser, verify:
   - Seed data loads in all 7 tabs.
   - Create/edit/delete works for each entity type.
   - Save ontology produces `ontology.trig`.
   - Multi-axis classification tagger works for variables (if
     variables tab is still present — it may have been removed per
     the Sep 12 architecture correction; check `App.tsx`).

2. **Wire equation editor to RdfContext** — Switch
   `/api/equation/context` to use `RdfContext` instead of legacy
   loader.  This is the next backend task.

3. **Behaviour Linker** — Design discussion in progress.  Open
   questions to resolve (see
   `docs/behaviour-linker-design-discussion.md`):
   - Unit of selection (per entity type, variable class, or equation
     class)
   - Assignment artefact structure (RDF named graph predicates)
   - Interface/port definitions (ontology or equation editor?)
   - Equation eligibility metadata
   - Validation scope
   - Graphics assignment
   - Mathematical role classification axis

4. **Remaining design items** (not blocking):
   - Q10: Mechanical device modelling at different abstraction levels
   - Event dynamic equation editor (equation-level, not ontology)
   - Q17: Downstream coupling — check BL and code gen for hardcoded
     CWA 17960 assumptions
   - Q23: Graphic Object Editor internal design

5. **Ontology v2 items** (from v1 ticket §7):
   - User-defined validation rules for axis values
   - Drag-and-drop token binding
   - User-defined entity types beyond CWA 17960
   - Ontology versioning (ADR-006)
   - QUDT integration for units

## Useful references

- `docs/session-handoff-2026-09-11.md` — previous handoff (Sep 12)
- `docs/ontology-design-discussion-2026-09-11.md` — design discussion
  (all questions resolved, §13/§25 added Sep 13)
- `docs/behaviour-linker-design-discussion.md` — BL design discussion
  (started Sep 13)
- `docs/ontology-editor-v1-ticket.md` — implementation ticket (v1
  complete, see §7 for v2 scope)
- `docs/ontology-data-model.md` — existing RDF schema
- `docs/ontology-editor-design.md` — existing UI design
- `docs/ADR-004-model-and-graphical-architecture.md` — modeller contract
- `docs/suite-status.md` — suite-wide status
- `docs/equation-editor-status.md` — equation editor status
- `docs/equation-context-contract.md` — EquationContext protocol
