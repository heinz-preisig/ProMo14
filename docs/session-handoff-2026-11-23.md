# Session handoff — 2026-11-23

## Delivered

### §41 component selection RULED — seeded basis vectors `e_i`

The component-selection convention (the last blocker for the
`v[C]`/`r[C]` fold) is decided and implemented: **`v_i ≡
reduceSum(e_i * v, C)`** — the σ/`F_k` scheme-object pattern, no new
syntax, no checker changes.

- **`_seed_basis`** (`backend/core/seed.py`): `e_x`/`e_y`/`e_z` —
  `[C]`-indexed, dimensionless, constant+parameter (verified-empty
  under the §4 bound-kind ruling), token-neutral and index-membership
  enforced on re-seed (F_k/σ precedent).  `SEED_FLOOR` → `2026-11-23`.
- **First seeded value-cell tables** — each `e_i` carries
  `{x:1, y:0, z:0}` &c. via `promo:ValueCell`, keyed on
  `idx_component`'s **literal** element names.
- **Scope resolution** — `_binding_cells` (`instantiate/service.py`)
  now unions cells across `resolution_scope`, least→most specific:
  pin tables < occurrence's own value source < host artefact.  Floor
  tables reach every pinning artefact; local cells still win.
- **`atIndexElement` guard** (`graph_store.set_value_cells` + fill
  path) — literal element names are not resources; linking them as
  relative URIRefs would corrupt TriG round-trips.  `promo:coordinate`
  stays the authoritative key (navigation links skipped).
- Mechanics read-through: gravity becomes an explicit authored term
  (`fmc*g*reduceSum(e_z*r,C)`), `|v|²` = `reduceSum(v*v,C)`, momentum
  `P[C]` folds natively, `E_26`/`E_27` need no `[C,C']` machinery.
- **Docs** (ruling landed twice): `design-principles.md` component-fold
  bullet, BL-discussion §41 deferred bullet, `value-cells.md` gained
  a **Scope resolution** section + the literal-element caveat.

### Equation-editor dialog — round 2 (`DependentVariableEditor.tsx`)

- **Permanent summary line, single toggle** — one `Variable details
  ▸` / `Hide ▾` button in a fixed position; declaration fields
  open/close beneath it (expand *and* collapse now live in the same
  place — was split top/bottom).
- **Rendered identity in the summary** — KaTeX-rendered LHS symbol
  (alias + derived/declared index subscripts, `astToLatex` on a `Var`
  node) plus rendered units via new `unitsToLatex()` in
  `variableUtils.ts` (`[kg·m·s⁻²]`, `[—]` when dimensionless).
- **Sticky commit footer** — `Save variable` / `Accept` moved out of
  the header into a bordered footer under the workspace; the blocked
  reason sits inline left of the disabled button.  Vertical layout
  kept (portrait-safe).
- **Save dirty-gates** — `Save equation` now requires
  `equationDirty || variableDirty` (rhs text or resolved class must
  differ; stored classes resolve label↔IRI before compare).  A no-op
  save no longer bumps `modified`/re-canonicalises.  `Save variable`
  was already `variableDirty`-gated; Accept on new/attach unaffected.

## State

- **576 backend tests pass** (`uv run pytest backend/ -x -q`), incl.
  `test_seed_basis_vectors` and `test_binding_cells_resolve_pin_scope`
  (floor table resolves through a `usesOntology` pin; local override
  wins on the same coordinate).
- Backend running; floor applied live (`ontology#e_x` cells verified
  `{x:1,y:0,z:0}`); `./dev.sh save` persisted — `data/*.trig` snapshot
  committed (assignments/library churn is mechanical).
- `@promo/equation-editor` dist rebuilt — refresh to get the dialog.

## Open for next session

- **The fold itself** — `v[C]`/`r[C]` consumer rewrites in `test_01`
  (equation-editor, dependent mode): `E_6`/`E_9`/`E_10` collapse to
  `v = ParDiff(r,t)` on `[N,C]`; `E_12`/`E_15`/`E_23` →
  `reduceSum(e_x*v,C)` forms; `E_26`/`E_27` →
  `reduceSum(e_x*r,C)*reduceSum(e_z*r,C)`; `fPot` →
  `fmc*g*reduceSum(e_z*r,C)`.
- **Dialog UX** — working per user, pending confirmation from other
  users; radios-to-footer move still unbuilt if it feels off.
- **Standing queue** — §32 stage-2 pairing resolver +
  `promo:Mechanism` layer; §33 submodel reuse; §21 closure-moves;
  friction `fl` constitutive law; radiation `fRx`/`ahr`; cross-artefact
  consistency review.
