# Session handoff — 2026-11-20

## Delivered

### §41 C-fold machinery — `promo:elements` + `idx_component`

Two commits close the dependency the fold was waiting on (previous
session stopped mid-implementation):

- **`8af3b1f`** — `promo:elements`: literal element sets on index
  records.  `CompileSpace.Index.elements`, `IndexInfo.elements`,
  `index_elements()` returns the declared literals before topology
  resolution, `report.indices` publishes them.  Fixed indices
  declare their elements; topological indices still derive them per
  model.  Test `test_literal_element_index_binds_declared_elements`.
- **`5a306bd`** — `_seed_component` floor migration: `idx_component`
  = `C` = `{x,y,z}`, `index_class "component"` (survives as the
  `index_source` alias so instantiation can tell fixed from
  topological indices; the checker sees a plain index).  No
  selector, no `subIndexOf`.  Element set enforced exactly on
  re-seed (σ/`F_k` precedent — edits cannot drift).  `SEED_FLOOR` →
  `2026-11-20`; `VOCAB_DOCS["elements"]`; test
  `test_seed_component_index`.  Backend restarted, migration applied
  to the live store, `ontology.trig` persisted.

## State

- **566 backend tests green.**  No frontend changes; no dist rebuild
  needed.  Backend running, store clean after save.
- §41 X-side verified complete in the data: `idx_x` + `sigma`
  seeded; `E_4`/`E_41`/`fQx` carry `reduceSum((sigma*effort),X)`;
  `d` is derived (`sign(reduceSum(σ·p_mech,X))`); balances and
  upwinds unchanged.
- `design-principles.md` untouched; ruling status recorded in the
  §41 deferred bullet of `behaviour-linker-design-discussion.md`.
- Note for diff-reviewing `data/*.trig`: this save produced large
  reordering churn (graph order + blank-node renumbering +
  accumulated `VOCAB_DOCS` declarations from `load()`).  Semantics
  verified clean; frozen `ontology/1.0` graph intact.

## Open for next session — the C-fold decisions

The var fold (`vx,vy,vz→v[C]`, `r_x,r_y,r_z→r[C]`) is blocked on a
**component-selection convention** — the language has no way to name
one element of a `C`-indexed variable:

- **`E_6`/`E_9`/`E_10`** (`v_i = ∂r_i/∂t`) collapse cleanly to
  `v = ParDiff(r, t)` elementwise on `[N,C]`.
- **`E_12`/`E_15`/`E_23`** consume `vx` *scalar-wise* — LHS vars
  `kConvX`/`kDiffX`/`kQX` are `[N]` scalars; they need the
  x-component of `v[C]`.
- **`E_26`/`E_27`** (`Axz = r_x·r_z`, `Ayz = r_y·r_z`) multiply
  *distinct* components — strictly `[C,C']` territory.  They are
  **live**: the transport laws consume `geometry!Ayz`/`Axy` as
  cross-sectional areas, so the fold touches working equations.

Options on the table (§41 deferred bullet):

- **Seeded basis vectors `e_x[C]`** — `v_x ≡ reduceSum(e_x * v, C)`.
  σ/`F_k` scheme-object pattern, zero new syntax.  Needs an
  element-keyed literal-value binding on the variable (a new, small
  mechanism — `σ` values are topology-derived, `e_x`'s are fixed
  constants).
- **Selection construct** — `at(v, C, x)`-style syntax.  The §40
  lesson argues against: hidden slot-pairing one level down.
- **Re-author in the `[C]`/`[C,C']` view** — `Axz`/`Ayz` become
  elements of `A[C,C'] = r:r'` once primed copies exist; scalar
  `vx` consumers get a declared "aligned velocity" via the X↔C
  seam (§41's still-open placement metadata).

Adjacent undecided items: momentum `[C]` fold (`P[C]`, `fmom[C]`,
forces — no equations exist yet, lands with the sheet project);
X↔C seam placement metadata; `C'` primed copies + `δ`/`ε` scheme
objects (§42 stage A).

## Standing queue (unchanged)

- §32 stage-2: pairing resolver (`port-domain-ambiguous` tripwire),
  `promo:Mechanism` resource layer.
- Occurrence-path namespacing (§22 Option A, deferred until a real
  referenced composite exists).
- Pin-picker simplification (deferred 2026-11-06, revisit on
  request).
