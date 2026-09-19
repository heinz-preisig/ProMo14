# ADR-008: `Instantiate` as instance declaration; constants as pre-bound variables

Status: accepted (2026-09-19)
Builds on: ADR-005 (equation language), ADR-004 §6 (instantiation stage)

## Context

`Instantiate(expr, shape)` was introduced to carry units and index
structure over from a "shape" variable onto an arbitrary expression —
a typing shortcut.  That conflated two different things (defining an
equation vs. borrowing a type), misused the standard meaning of
*instantiate*, and left the canonical constant form
`Instantiate(var, value)` unwritable (`value` parsed as a variable
reference and failed with `VarError`).

The algebra genuinely needs *instances of variables*: interval bounds
(`t_start`, `t_end` for `Integral(f :: t in [t_start, t_end])`),
initial conditions, and similar — distinct variables that share a
prototype's quantity type.  It also needs a small set of numeric
symbols (`0`, `1/2`, `1`) without breaking the "no numeric literals"
rule.

## Decision

### `Instantiate(proto)` — single argument, declaration only

`Instantiate(t)` as the **entire** right-hand side declares the LHS
variable as a new instance of the prototype variable `t`:

- The argument is a single `Var` (qualified `net!label` allowed) —
  `Instantiate(x + y)` is a parse error.
- Top level only — `sin(Instantiate(t))`, `(Instantiate(t)) + x`,
  `x + Instantiate(t)` are all parse errors.  It is a declaration,
  not a value-producing subexpression.
- The instance **inherits the prototype's units and full index
  structure** (required: `Integral` bounds must share the integration
  variable's index structure).  Everything else — domain, class,
  label, latex alias — comes from the LHS declaration.
- **Empty incidence**: the prototype is a type-level reference, not a
  value dependency.  The equation defines the LHS with no
  dependencies — exactly like a constant declaration.
- **LHS class enforcement**: the declared variable must be class
  `constant` or `parameter` (an instance is a bound-value slot, not a
  computed quantity).  The checker rejects `state`/`effort`/… LHS;
  the editors restrict the class dropdown accordingly.
- Saving an `Instantiate` equation writes `promo:instanceOf` on the
  LHS variable → prototype IRI, and the equation is auto-classified
  `equation_class = "instantiate"`.

### Constants are variables; values are bound at instantiation

Numeric symbols are ordinary variables, keeping the algebra literal-free:

- **Universal constants** `zero`, `one`, `half` are seeded in the
  ontology (network `root`, class `constant`) with `promo:value`
  pre-bound (`0`, `1`, `0.5`) and latex aliases (`0`, `1`,
  `\frac{1}{2}`).  They are permanent — fixed by mathematics, locked
  in the instantiation tool, non-deletable in the editors.
- **Model constants / parameters** get their values at the
  instantiation stage (suite stage 6); `promo:value` stays empty in
  the ontology until then.
- Codegen inlines `promo:value` when present (universals render as
  `0.5` even pre-instantiation); otherwise the `V_N` symbol stands
  as the parameter slot.  `Instantiate` equations render as a
  parameter placeholder (`V_x = None  # parameter: instance of V_t`),
  never as `lhs = proto` — an instance is not a copy of the
  prototype's value.

### Three-layer binding model

| Layer | Where | What |
|---|---|---|
| Variable class | ontology | *default* binding regime — `constant`/`parameter` = bound-value slots; `state`/`transport`/… = computed |
| Fix marking | model artefact (future) | per-occurrence *override* — a computed-class variable fixed in one model |
| Value binding | instantiation artefact (future) | the actual numbers |

Fixing a variable (e.g. a flow) keeps the *same* variable but changes
its regime in that model — a different operation from `Instantiate`,
which creates a *new* variable.  The mark therefore belongs to the
model artefact, not the equation language.  Fixability is two checks:
a role-level filter (interface/boundary quantities) and a structural
one (the equation↔variable incidence must still admit a perfect
matching, with causality consistency per port — effort xor flow).
Both are behaviour-linker concerns and are deferred there.

## Consequences

- The misleading unit-borrowing form is gone; every equation's units
  are honestly inferred.
- `promo:value` (literal) and `promo:instanceOf` (IRI) are new
  vocabulary terms, auto-declared by `declare_vocabulary`.
- `zero` remains dimensionless-only (`x + zero` on dimensional `x`
  still fails the unit check); scalar broadcasting in `Add` is
  unchanged and remains a separate question.
- Existing stores gain the universal constants via an idempotent
  ensure-seeds step in `RdfStore.load()`.
- LaTeX renders `lhs := \mathrm{inst}(t)`; the instance's own symbol
  (`t^0`, `t^e`, `t_s`, …) is the user's latex alias, so notation
  conventions stay with the user.
