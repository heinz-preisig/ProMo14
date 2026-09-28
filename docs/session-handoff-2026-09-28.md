# Session handoff — 2026-09-28

State of the ProMo14 workspace at end of day.  Branch `main`, remote
`heinz-preisig/ProMo14`.  Supersedes `session-handoff-2026-09-27.md`
(morning section below; afternoon section added EOD).

**Before switching machines:** work is committed but **6 commits are
unpushed** — run `git push`.  `git status` is clean, `dist/` for the
instantiation app is built, store was clean at last check (run
`./dev.sh save` if unsure).  On the home machine: `git pull && uv sync
&& npm install && ./dev.sh start`.  Do **not** `wipe-restart` —
`data/` is the sync channel.

## What landed — afternoon session

- **Instantiation app is no longer scaffold** (`46b3204`): value-cell
  editor (`ValuesCard` — per-coordinate inputs on parameter/state
  bindings, `PUT /api/instantiate/values`, `|`-joined element-IRI keys)
  and the t=0 solve UI (`SolveCard` — `ic_needs` table, par inputs,
  steady-state toggle, per-state `y0` output).  `api.ts`/`types.ts`
  wire `putValues`/`solveInitial`/`InitialOut`.  Two fixes worth
  noting: par keys are **emitted names** (`emitName` mirrors
  `plan.emit_name` — `V_5`, `ic0_V_1`), not display labels; and
  `VarBinding.indices` element sets are nullable (unbound extent).
- **Value-cell convention documented** (`91bd1dc`): the
  coordinate-enumeration question discussed at length — a flat list
  has no inherent order, so the contract is pinned and now
  self-describing:
  - `docs/value-cells.md` — the **normative doc**: coordinate→value
    map is authoritative (`promo:coordinate` JSON ordered list +
    `atIndexElement` nav links on each `ValueCell`); flat enumerations
    are C order, last index fastest, in `indexStructure` order;
    per-target `_array_lit` table (python native, julia/matlab
    reshape-reverse+permute); `par` caller contract; silent-scramble
    failure mode.
  - `VOCAB_DOCS` in `backend/core/vocab.py` — `promo:doc` notes on
    `ValueCell`/`valueCell`/`coordinate`/`atIndexElement`/`value`,
    stamped by `declare_vocabulary`.
  - **`load()` now re-declares vocabulary on every non-version
    graph** (`persistence.py`) — docs self-migrate into `data/*.trig`
    on next save; frozen version graphs skipped (immutable).
  - `test_value_cell_layout_convention` — golden emitter literals on a
    **non-square 2×3** table + numpy column-major simulation (square
    dims can't detect a transpose bug).
- **Design Q&A settled** (no code): `promo:value` is literal-only
  (constants + cells); expression-valued cells would need a new
  predicate (`promo:valueExpression`) on `ValueCell`, never a
  polymorphic `promo:value` and not `promo:rhsExpression` (equation
  vocabulary).  Deferred — `initialise` equations remain the computed-
  IC channel; cells stay leaf data.

## What landed — morning session

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

- Backend tests: **390 passed** (`uv run pytest backend/ -x -q`).
- Today's commits: `ed9f3ae`, `e62774d`, `e141d93`, `6336d97`
  (IC machinery), `46b3204` (instantiation app UI), `91bd1dc`
  (value-cell convention docs) — **unpushed at EOD**.
- `data/ontology.trig` contains `eqclass_initialise` (working graph);
  `data/library.trig`: 9 equations, all `promo:rhsExpression`.
- `VOCAB_DOCS` doc triples reach `data/*.trig` on next
  backend-restart + save (load declares them; a running pre-change
  backend won't have them in memory).
- Instantiation app `dist/` built and served at hub `:8000` —
  value-cell editor + t=0 solve are live.

## Pending / next

- **Expression-valued cells** — the only IC channel gap.  Design
  settled this session (new `promo:valueExpression` predicate if
  done; cells stay leaf data otherwise — see afternoon notes).
- **Exercise the instantiation UI** end-to-end against a real model
  graph (`:8000` → instantiation, `?graph=` + `?vars=`).
- **Sequential `E_N` minting** — frontend still uses `E_${Date.now()}`.
- Deferred queue unchanged: reaction-domain equations, SHACL at
  publish boundary, behaviour-linker UI, multi-pin `usesSpecies`,
  external-IRI links on variables (predicate choice pending),
  LaTeX→image cache, RDF vocabulary finalization.
- Resolved this session: value-cell editor UI (was scaffold), the
  `initialise`-shares-LHS question (yes — `initial_equations` gathered
  separately), emitters-vs-cells wiring (was already wired).

## Commands

- Tests: `uv run python -m pytest backend -x -q`
- Restart + save: `./dev.sh restart backend`, then
  `curl -X POST localhost:8000/api/ontology/save` (or `./dev.sh save`)
- Frontend after `apps/equation-editor/src` edits: `./dev.sh build equation`
- Frontend after `apps/instantiation/src` edits:
  `./dev.sh build instantiation` — **always rebuild before refreshing**,
  the hub serves `dist/` not `src/`
