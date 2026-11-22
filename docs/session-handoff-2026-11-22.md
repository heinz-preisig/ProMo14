# Session handoff — 2026-11-22

## Delivered

### Design review 2026-11-22 (`docs/design-review-2026-11-22.md`,
commit `eef82af`)

Third run of the workflow over `a67f03f..a0b914b` (58 commits).
574 tests green; all 16 principles conform.  `design-principles.md`
gained the §45 ruling under §8 plus the new open gap
(component-selection convention); `equation-editor-overview.md`
gained §45 + σ spelling.  Proposed-not-applied: energy-balance
conventions (recorded §46 instead), `index_source` enum note,
`E_dUdt` class (now set to `balance`).

### §46 — mechanical + total energy balances (data)

Balances are independent objects: `dHdt` thermal, `dEmdt` mechanical
(Bernoulli-with-friction), `dEtotdt` total/1st-law — same inputs may
appear in several, nothing is summed.  Flow work stays inside
enthalpy; shaft work `fWs` is an imposed boundary port; friction
`fl [A_conv,N]` is a second imposed port whose aggregate `al` is a
**transfer term** (−mech, +thermal).  New vars: `fKin`/`fPot`/`fPflow`
`[A_conv,N]` advected flows (`fmc·v²/2`, `fmc·g·r_z`, `fmc·p/ρ`),
`al`/`amech`/`akp` aggregates, `dEmdt`, `dEtotdt`; `dHdt` gained
`+ al`.  Consistency 65/4 bound-scope/0.

### `g` seeded — first physical constant

`SEED_CONSTANTS` is now a 5-tuple (`frag, label, value, latex,
units`); `const_g` 9.81 m·s⁻² lands in the ontology via the floor
migration (`SEED_FLOOR` → 2026-11-22, backend restart).

### Equation-editor dialog — viewport clipping fixed

`DependentVariableEditor.tsx`: the declaration column grew
unbounded and, as a non-shrinking flex child, squeezed the
expression workspace to a thin slice — "finishing is nearly
impossible" per user.  Header block now `minHeight:0 +
overflowY:auto` (scrolls internally); workspace keeps a
`minHeight:300` floor.  Dist rebuilt.

## State

- **574 backend tests pass.**  Backend running (seed floor applied).
- Consistency: 65 consistent / 4 bound-scope / 0 errors.
- `data/*.trig` saved and committed (shaft work + energy balances +
  `const_g`); `assignments.trig` churn is bnode renumbering only.
- `g` verified live: `ontology#const_g`, units `[-2,1,0,…]`, value
  9.81, network `root`/`universe`.

## Open for next session

- **Dialog UX round 2** — the scroll fix restores reachability, but
  the navigation order is still inverted (domain → name → fields →
  expression-panel-below → Check → Accept), foundation chrome stays
  visible in dependent mode, and the expression lives outside the
  dialog frame.  A dependent-creation redesign is the natural next
  pass.
- **`fl` is imposed** — a λ·(L/d)·ṁ·v²/2 constitutive law could
  replace the boundary port when friction-factor variables exist.
- **Component-selection convention** (§41/§42 open gap) still blocks
  the `v[C]`/`r[C]` folds.
- Radiation: `A_rad`/`F_rad` seeded but `fRx`/`ahr` unauthored.
- `E_dUdt` IRI rename → `E_dHdt` done as part of the `dHdt` update.
