# Behaviour Linker — Implementation Status

**Last updated:** 2026-09-22

## Current state

Backend core implemented (closure engine + assignment artefact
endpoints, 16 tests).  Frontend is still an empty scaffold.  Design is
resolved — see `behaviour-linker-design-discussion.md` §1–18.

## Backend

`backend/behaviour/`:

- `closure.py` — pure-Python closure engine (`evaluate`), no
  rdflib/FastAPI deps.  Implements the §8/§12/§13 mechanics:
  - selection state = ordered equation `sequence` + `base_equation`
    (state-defining, must head the sequence; `None` for stateless
    entities like transport systems) + `instantiated` + `ports`;
  - per-variable resolution: defined by a selected equation /
    to-be-instantiated / external port, else *unresolved* with the
    candidate equations that could define it;
  - cycle check: only the loop through the state variable is allowed
    (the integrator loop); every other back-edge is reported;
  - conflicts: duplicate definition, defined+instantiated,
    defined+port, instantiated+port, unknown equation;
  - order check (§13 lower-triangular): non-base equations may only
    consume state, earlier-defined, instantiated, or port variables;
  - warnings (non-blocking): unused markings, equations unreachable
    from the base cone;
  - `closed` requires a non-empty sequence with no unresolved inputs,
    cycles, conflicts, or order violations.
- `service.py` — FastAPI router (`/api/behaviour`):
  - `GET /context?graph=` — entity types (with scale values),
    equations (lhs + incidence), variables of the scoped var/expr
    graph;
  - `POST /evaluate?graph=` — runs the engine on a posted selection,
    returns the report plus a `labels` map (IRI → display label);
  - `GET /assignment?entity_type=&graph=` — read the stored assignment
    (404 if none);
  - `PUT /assignment?graph=` — evaluates, then persists the §13
    artefact: `promo:BehaviourAssignment` resource with
    `forEntityType`, `hasBaseEquation`, `hasStateVariable`,
    `hasEquationSequence` (`rdf:List`, discovery/computation order),
    `hasPortVariable`, `hasInstantiatedVariable`, and a `closed` flag
    so work-in-progress selections can be saved;
  - `DELETE /assignment?entity_type=&graph=`.
- Assignment artefact graph: `{var/expr graph}/assignments`
  (`promo:Assignment` type, pinned to the graph's resolution scope);
  unscoped mode uses `https://w3id.org/promo/assignments`.  Created
  lazily on first PUT.
- `test_closure.py` — 16 tests: engine semantics (state loop allowed,
  other cycles rejected, conflicts, ordering, warnings) + endpoint
  roundtrips incl. rdf:List replacement on re-PUT.

## Frontend

`apps/behaviour-linker/` — minimal working SPA (React + Vite, dev on
:3003, `npm run dev:behaviour` / `./dev.sh start behaviour`):

- Sidebar: entity types with stored-assignment badges (closed/wip).
- Base-equation radio list (incl. "none — stateless" for transport
  systems); picking one moves it to the head of the sequence.
- Computation sequence list with ↑/↓ reorder and remove.
- Unresolved-inputs panel driven by `POST /evaluate` (debounced on
  every change): each unresolved variable offers its candidate
  equations (`+ E_n` inserts before the earliest non-base consumer,
  keeping the §13 lower-triangular order), plus "instantiate" and
  "port" markings.
- Roles panel (state / ports / instantiated with unmark), problems
  panel (cycles, conflicts, order violations, warnings), header
  open/closed badge + store-dirty badge + Save (PUT assignment, then
  store save) and Delete.
- `?graph=` session param honoured like the other apps.

## Design

Role is defined in ADR-004; the full mechanics are resolved in
`behaviour-linker-design-discussion.md` (§8 closure algorithm, §12
validation scope, §13 assignment artefact, §14 tokens/ports, §15
reference coordinates, §16 arc sub-indices, §17 scale regimes/seed
contract, §18 variable mutability).

## Pending items

1. ~~Frontend SPA~~ **Done (2026-09-22):** minimal guided-resolution
   UI live on :3003.
2. Graphical assignment interaction (Graphic Object Editor) — design
   exists, implementation not started.
3. Equation-eligibility hints from ontology (regime/scale filtering of
   candidate lists) — engine accepts any equation today.
4. Port satisfaction check against connection rules (§14) — needs the
   Modeller-side arc check (ADR-008 deferred item).
5. Fix marking (three-layer binding model, ADR-008) — per-occurrence
   override belongs to the model artefact.
6. UI polish: KaTeX rendering of equation RHS, drag-reorder of the
   sequence, entity-type search/filter.

## Dependencies

- Equation Editor backend (var/expr graph — consumed via
  `scoped_context`, honours `?graph=` pin scoping).
- Ontology (entity types, scale values, tokens, connection rules).
- Graphic Object Editor (shared component, not yet built).
