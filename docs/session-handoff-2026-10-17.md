# Session handoff — 2026-10-17

## What was done

The §19 instantiation feature closed out end-to-end: fix marking
(ADR-008 layer 2), the `promo:Instantiation` persistence artefact, and
pinned-plan codegen. Plus arc-token display and the documentation stack
earlier the same day.

Commits: `c01cd92` (arc tokens), `61c7cab` (fix marking + instantiation
artefact), `76b9f43` / `a64c59c` (docs), `d5c2ec9` (modeller fix
gesture), `c68d6bc` (pinned-plan codegen).

### Fix marking (ADR-008 layer 2) — complete chain

- **Storage**: `promo:fix` on `ModelNode`, one triple per variable IRI.
  `ModelNodeDoc.fixes` round-trips through modeller PUT/GET.
- **Gesture**: selecting a leaf shows a *"Fix (bound at this node)"*
  checklist fed by `GET /api/instantiate/entity-variables?entity_type=`
  (expands the assignment's sequence lhs/inputs + state + instantiated +
  ports → `{var, label, role}`). `toggleNodeFix` command; fixes
  serialize in `ModelNodeDoc`.
- **Engine**: `NodeInfo.fixes` → binding `fixed`, which **overrides the
  class regime and wins over a defining equation** (equation dropped,
  `fix-conflict` reported; the LHS stays discoverable via `fixed_lhs`).
  Marks aggregate per entity type — marking only some nodes widens to
  the type-level binding and reports `fix-partial`. A fixed var without
  data reports `fixed-unbound`; the service retracts that kind when
  value cells exist (`Problem` gained a `var` field for this).
- **Plan**: fixed + `promo:value` → constant param slot (inlined);
  fixed without value → input slot (cells or `par`).

### Instantiation artefact + pinned replay

- `promo:Instantiation` added to `ARTEFACT_TYPES`.
- `POST /api/instantiate/instantiations?graph=<model>` computes
  report+plan and persists an artefact graph: `generatedFrom` → model,
  the full pin set (ontology/library/assignment/species),
  `promo:plan` = JSON of `asdict(CodePlan)`, `promo:computedAt`,
  `promo:problems` = JSON problem-kind list.
- `GET /instantiation-plan?iri=` reads it back.
- **Pinned replay**: `GET /code?instantiation=<iri>` and
  `POST /initial?instantiation=<iri>` emit from the persisted plan —
  no recompute. `code_plan_from_dict` (`plan.py`) rebuilds the plan
  (restores tuples in `MatrixLit.entries` and `loops`). The emitter's
  var/expr `CompileSpace` comes from the artefact's `usesLibrary` pin;
  `?vars=` still overrides.

### Arc-token display

Backend `resolve-connection` already returned `matched_tokens`; now
carried as `matchedTokens` on `AllowedConnection` through
`RemoteRuleResolver` and shown in the connect-gesture arc-type list and
the selected-arc panel.

### Docs

- `problem-catalogue.md`: `fix-conflict`, `fix-partial`,
  `fixed-unbound` documented.
- `concepts-and-architecture.md` §8 updated — fix marking and
  instantiation artefact now recorded as done (incl. UI + pinned
  replay).

## Verified

- `backend/instantiate/test_builder.py`: **70 passed** (includes
  fix-binding tests and `test_code_plan_round_trip`: rt == cp).
- `backend/modeller/test_service.py`: 9 passed (78 total earlier).
- Modeller: `tsc --noEmit` clean, 35 vitest tests pass.
- Test invocation: `uv run --with pytest --with httpx2 -- pytest ...`
  (pytest is not in `.venv`; starlette TestClient needs `httpx2`).

## Where to pick up — candidate queue

In rough priority order; the first is the only design-gated item:

1. **BL admissibility checks** (ADR-008): role filter + perfect-matching
   enforcement in the Behaviour Linker. Design discussion needed —
   user was not yet up to speed on this issue; revisit
   `docs/behaviour-linker-design-discussion.md` first.
2. **Composites/reuse semantics**: referenced-model composites, port
   surfacing (design-discussion §8; codegen approach 2).
3. **Direction-aware donor selection** for chained port `c` — carry-over
   from 2026-10-16; consumes §15 reference direction per contact.
4. **Meshing** (`distributed-systems-design.md`), **empirical model
   selection artefact** (energy-function + EOS pattern).
5. Loose ends: `remoteCatalogue` branch→domain last-match-wins bug;
   `inv` on indexed args literal-only (5 library equations
   uncanonicalised); stale `root!` qualifiers.

## Quick orientation for the next session

- Report: `GET /api/instantiate/model?graph=https://w3id.org/promo/model/`
- Persist: `POST /api/instantiate/instantiations?graph=...`
- Replay: `GET /api/instantiate/code?instantiation=<iri>&target=python`
- Key files: `backend/instantiate/{builder,plan,service}.py`,
  `apps/modeller/src/{App.tsx,state/ModelState.ts,modelPersistence.ts}`.
