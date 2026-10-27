# Session handoff — 2026-10-27

## What was done

Design session only — no code changes. The long-open **BL admissibility**
question (handoff queue item 1, ADR-008) was discussed and resolved;
recorded as **§21** in `docs/behaviour-linker-design-discussion.md`.

### §21 — Admissibility: moves preserve the closed-subgraph invariant

Key points settled in discussion with the user:

- **Terminology pinned**: variable / expression / equation
  (`variable := expression`; a variable may own several equations =
  alternative expressions).
- **The lower-triangular sequence IS the data structure** — each
  expression may only reference variables defined earlier in the
  sequence or endpoints. "Defined" is positional (bound at an earlier
  slot), not merely declared. Same principle the equation editor
  already enforces at authoring time.
- Declaration-before-use does not prevent store-level equation cycles
  (`a := f(b)`, `b := g(a)`) — the triangular sequence breaks them by
  construction; the only surviving cycle is the integrator loop.
- **Four endpoints** (all must be matched): state, instantiated,
  port, and **output** — a new endpoint kind: a variable computed for
  observation/measurement/recording that nothing consumes. Outputs
  are roots of the reachability check alongside the base cone.
- **Moves, not edits**: pick / exchange / delete / unmark-output are
  re-closures. Exchange prunes the displaced expression's exclusive
  provider cone and repositions if needed; delete cascades the cone
  and reopens dependents. "Unreachable" is a transient, not a report
  category.
- `lhs_class` folds into candidate filtering (offered expressions are
  those that keep the subgraph completable), not a hard gate — the
  earlier "role filter / perfect-matching" framing was superseded:
  perfect matching is already the triangularity invariant
  (`duplicate_definition` + order violations + reachability in
  `closure.py`).

### Docs updated

- `behaviour-linker-design-discussion.md` — new §21 (terminology,
  invariant, endpoints, moves, engine delta, open items).
- `behaviour-linker-status.md` — design section extended to §21;
  eligibility-hints item marked superseded; fix marking + instantiation
  artefact marked done; new pending item: engine rewrite to moves +
  output endpoint.
- `concepts-and-architecture.md` §8 — fix-marking bullet now records
  §21 as designed with remaining work noted.

## Where to pick up — candidate queue

1. **§21 engine rewrite** (the admissibility design is done — now
   implement): `closure.py` moves from `evaluate()` reporting to
   computing minimal invariant-restoring sequence changes per move.
   Open sub-items: cascade-vs-reopen confirmation on delete;
   `promo:hasOutputVariable` persistence on the assignment artefact.
2. Composites/reuse semantics (design-discussion §8; codegen
   approach 2).
3. Direction-aware donor selection for chained port `c` (§15).
4. Meshing (`distributed-systems-design.md`), empirical model
   selection artefact.
5. Loose ends: `remoteCatalogue` branch→domain last-match-wins bug;
   `inv` on indexed args (5 library equations uncanonicalised);
   stale `root!` qualifiers.

## Quick orientation

- Design: `docs/behaviour-linker-design-discussion.md` §21.
- Engine to change: `backend/behaviour/closure.py`,
  `backend/behaviour/service.py`, SPA hook
  `apps/behaviour-linker/src/hooks/useBehaviourLinker.ts`
  (`resolveWith`/`removeEq` are the move sites).
- Test invocation: `uv run --with pytest --with httpx2 -- pytest ...`
  (pytest not in `.venv`; TestClient needs `httpx2`).
