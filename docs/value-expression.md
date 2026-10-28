# Expression-valued cells — `promo:valueExpression`

Status: **draft** — semantics proposed, not implemented.

The §20 cell channel is literal-only today: `promo:value` carries a
number.  An IC that is a *computed* quantity (e.g. "80 % of the tank
volume") currently needs an `initialise` equation whose sole purpose is
to move a parameter-like value into a state pin.  Expression cells let
a value cell carry an expression instead of a literal, evaluated during
instantiation.

## Proposal

A `promo:ValueCell` may carry **either**

- `promo:value` — a literal number (status quo), **or**
- `promo:valueExpression` — a literal *string* in the ProMo expression
  language (`promo:rhs` syntax, `backend/equation/`).

Exactly one of the two must be present — a cell carrying both is a
`bad-cell` problem.

## Scalar-evaluable subset

The cell expression is evaluated **numerically** at `plan()` time, so
only the scalar fragment of the AST is meaningful:

- `Var` — resolved against the *symbol environment* below
- `Group`, `Add` (`+`/`-`), `Power` (`^`), unary `-`
- `UFunc` (`sin`, `exp`, `sqrt`, …) — the `SymbolTable` builtins
- `MaxMin` (`min`/`max`), `Call` — when all args evaluate

Explicitly out of scope (a problem, not silent NaN):

- tensor operators `*`/`:`/`.` (`Reduce`/`Expand`/`IndexPreservingProduct`)
  — they need index semantics that a scalar cell does not carry
- `Instantiate`, `Integral`, `Product`, `ReduceSum`, `Root`,
  `TotalDiff`, `ParDiff` — symbolic constructs

## Symbol environment

The only unresolved design question — three candidate scopes, ordered
by surface area:

1. **Params-only, scalar names** (recommended first cut): symbols are
   the *emitted names* of bindings that already resolved to a scalar
   literal — constants, literal params, and earlier-resolved expression
   cells.  `V_total * 0.8` works; `m[i]` does not (an indexed param's
   name is ambiguous — which element?).
2. **+ indexed access**: allow `Var` to carry a coordinate
   (`m_a` resolves through a table lookup).  Needs index-structure
   resolution at eval time — meaningful work.
3. **+ per-cell binding**: the expression is evaluated once *per cell
   coordinate* with the cell's own index elements bound — i.e. fills
   whose value is a function of the coordinate.  Powerful but turns
   cells into implicit equations; deliberately out of scope.

## Dependency ordering

Option 1 still introduces a partial order: an expression cell may
reference another expression cell's result.  Resolution is therefore a
small fixpoint at `plan()`:

1. Literal cells resolve first (fills included — the existing
   machinery is untouched).
2. Expression cells evaluate in dependency order; an unknown `Var`
   waits, a `Var` that never resolves → `unresolved-cell` problem.
3. A dependency **cycle** → `cell-cycle` problem naming the loop.

Cross-variable references name emitted symbols (`V_5`, `par["V_5"]`'s
key) — stable, already what `par` uses.

## Storage & API

- `promo:valueExpression` — new literal predicate on
  `promo:ValueCell`, parallel to `promo:value`.  Declared in
  `declare_vocabulary` with a `promo:doc`.
- `value_cells()` / `PUT /values` — the map value stays JSON-typed:
  `number` = literal cell, `{"expr": "<string>"}` = expression cell.
  `ValueCellsOut.values` becomes `Dict[str, Any]`; the UI distinguishes
  by shape.  **This is the one API-surface change** — clients that
  assumed `number` read `expr` objects.
- `plan()`/`_value_table` — after fill resolution, a second pass
  evaluates `expr` cells (per the fixpoint) into the same `flat` table.
  `model_data.json` and emitted code see only numbers — the contract
  holds.

## What this removes

The `initialise`-equation workaround for computed ICs: a state IC pin
of `0.8 * V_total` becomes a cell, not an equation — consistent with
ICs-as-data and with `ic`-flavoured fills.

## Non-goals

- Expression cells as *fill* values — a fill carrying an expression
  evaluated per covered coordinate is option 3 above; excluded
  (cells-as-implicit-equations is a bigger design).
- Unit checking of cell expressions — the `checker` pass could type
  them against the var's declared unit; deferred until the channel
  proves out.
