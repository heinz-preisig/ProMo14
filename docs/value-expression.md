# Expression-valued cells — `promo:valueExpression` — REJECTED

Status: **rejected** (user-ruled 2026-10-28).  Spec drafted
(`faf9f73`), implemented (`5c02e28`), reverted (`e1ca09e`).

## What was proposed

Let a `promo:ValueCell` carry `promo:valueExpression` — a literal
string in the ProMo expression language — instead of `promo:value`'s
literal number.  A scalar-evaluable AST subset (Var/Group/Add/Power/
product ops/UFunc/MaxMin, **no numeric literals**) was evaluated
numerically at `plan()` time over a params-only symbol environment,
with a fixpoint reporting bad-cell/unresolved-cell/cell-cycle.

Motivation at the time: an IC that is a *computed* quantity ("80 % of
the tank volume") needed an `initialise` equation whose sole purpose
was moving a parameter-like value into a state pin.

## Why it was rejected

Relations belong at the **equation-definition level**, not in value
cells.  The cell channel stays literal-only; a computed IC is an
`initialise`-class equation — which is what the equation layer is
for.  Permitting expressions inside cells would have created a second,
weaker equation system with its own symbol environment and cycle
rules — exactly what the symbolic-only boundary (design-principles
§2) exists to prevent.

Kept from the implementation: `/model` runs `plan()` so
bad-fill/fill-conflict problems reach the report (cell-editor badges
were previously dead), with a regression test.
