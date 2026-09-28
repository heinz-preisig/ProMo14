# Session handoff — 2026-09-28

## What landed

- **`inv` is now elementwise reciprocal** (index-preserving): `inv(x[N]) → [N]`,
  units invert. Matches the MultiDimVar runtime (`rdivide.m` — `1 ./ x`; there
  is no `inv.m`). Touched:
  - `backend/equation/symbols.py` — unit rule `scalar_inverse` → `inverse`.
  - `backend/equation/checker.py` — dropped the scalar-argument rejection.
  - `backend/equation/codegen.py` — matlab/julia emit `1 ./ x` (`/` is
    mrdivide / matrix inverse); python `1 / x`; latex `{x}^{-1}` (unchanged).
  - `apps/equation-editor/src/operatorHelp.ts` — help text updated.
  - Regression tests: `test_inverse_preserves_index_structure`, indexed
    python/matlab codegen cases.
- **`root!` qualifier fixed**: `E_12` RHS source rewritten `root!half` →
  `universe!half` in `data/library.trig` (root domain renamed 2026-09-26).
- **All equations canonical**: 9/9 ontology + 9/9 library — zero literal-only
  `promo:rhs` remain. `RdfStore.load()` migration + `POST /api/ontology/save`
  verified end-to-end.
- **Initial-condition design decision** (replaces the `E_13` blocker):
  - ICs are **not** model algebra. `Instantiate`-as-IC was rejected: it
    conflates type relation with seed role and cannot express computed ICs.
  - `no` + `E_13` deleted from `data/library.trig` (only reference was the
    equation itself).
  - Three regimes: (1) bound IC → `promo:ValueCell` on the state, requested
    by the instantiator; (2) computed IC → **`eqclass_initialise`** equation
    (t=0-only, Modelica `initial equation` style — may pin a state or
    secondary vars); (3) implicit IC (specify secondaries, back-solve the
    fundamental state) → instantiator assembles the t0 system and solves it
    numerically as a root problem; guesses auto-requested. Steady-state
    start = zero `TotalDiff` terms.
  - IC *need* is derivable from canonical ops (`TotalDerivative`,
    `DefiniteIntegral` states; `SolveRoot` LHS vars). Same scheme covers
    root-solver initial guesses.
  - ProMo13 precedent: `ENABLED_COLUMNS["initialise"]` existed in the old
    EquationEditor resources — this restores it.
- **Index-uniqueness invariant sealed** (audit after `inv`/MultiDimVar
  discussion): already enforced by `VariableIn`/`VariableRecord` pydantic
  validators, the checker's `Var` rule, and `Checked.__post_init__`. Two
  wormholes closed: `add_variable_dict` (the single write funnel — seeds
  and internal callers bypass pydantic) now rejects duplicate index IRIs;
  `Variable.__post_init__` (compile_space) rejects them at materialisation,
  so a corrupted `.trig` fails at read time for *every* consumer
  (checker space, rdf_context, instantiate `VarInfo` coordinate keys)
  rather than only when a var is referenced in a checked expression.
- **Equation-class picker landed**: `/context` returns
  `equation_classes` (`RdfContext._load_equation_classes`); the editor's
  class select binds IRIs, `instantiate` is pinned on `Instantiate` RHS.
  `promo:equationClass` is now an IRI link (was a bare literal):
  `RdfStore._equation_class_ref` resolves `promo:`/IRI/label at the
  write funnel — legacy labels migrate on re-save; UI display maps
  IRI→label via `equationClassLabel`.  **ν→codegen verified already
  wired** — `values`→`plan()`→`ParamSlot.values`→array literals in all
  three dialects; the earlier "emitters expect scalar per instance" note
  was stale.
- **Equation classes moved into the seed floor**: `_seed_equation_classes`
  is now a floor step (`apply_seed_floor`), idempotent by deterministic IRI —
  new classes (like `initialise`) reach existing stores on reload, not just
  fresh seeds. `SEED_EQUATION_CLASSES` in `vocab.py`; `SEED_FLOOR` bumped
  `2026-09` → `2026-09-2`. The frozen `ontology/1.0` graph correctly did
  NOT receive the new class (floor applies to the working graph only).

## State

- Backend tests: **366 passed**.
- Backend restarted; store saved; `dirty=false`.
- `data/ontology.trig` now contains `eqclass_initialise` (working graph).
- `data/library.trig`: 9 equations, all with `promo:rhsExpression`.

## Pending / next

- **Instantiation-side IC machinery** (instantiation app is scaffold):
  derive IC need from canonical ops; t0-system assembly; bound-cell +
  initialise-equation coverage; guess requests for implicit solves.
- **Expression-valued cells** — deferred; `initialise` equations cover
  computed ICs for now.
- Question left open: can an `initialise` equation share an LHS variable
  with a generic equation (state carrying both its balance eq and a t0
  pin)? Recommended yes — Modelica allows it; `hasEquation` is plural.

## Commands

- Tests: `uv run python -m pytest backend -x -q`
- Restart + save: `./dev.sh restart backend`, then
  `curl -X POST localhost:8000/api/ontology/save` (or `./dev.sh save`)
- Frontend after `apps/equation-editor/src` edits: `./dev.sh build equation`
