# Session handoff — 2026-09-24

State of the ProMo14 workspace at end of session.  Branch `main`,
remote `heinz-preisig/ProMo14`.  Supersedes
`session-handoff-2026-09-23.md`.

**Before switching machines:** the day's later work is *uncommitted* —
run `./dev.sh save` (persists the in-memory store into the tracked
`data/*.trig` files), then `git add -A && git commit && git push`.
On the other machine: `git pull && uv sync && npm install && ./dev.sh
start`.  Do **not** `wipe-restart` — `data/` is the sync channel.

## What landed today

**Classification axes settled** (design discussion, commits `d58e962`,
`5db7649`, `ea882e8` + uncommitted redefinition):

- Physical branch: `determination` {constant, variable} — temporal
  fixity — and `function` {state, fundamental-state, secondary-state,
  effort, flow, frame, reaction, parameter}.  Information branch keeps
  `role` {state, differential-state, input, output, constant,
  parameter}.
- **`port`/`derived` are structural, not axis terms** — port is the
  `promo:portVariable` flag (bipartite-graph position, fundamental for
  the §19 builder); derived is implied by having a defining equation.
- **`parameter` is a `function` term** — a characteristic value in a
  function, part of the function definition, often embodying a specific
  assumption.  `determination=variable + function=parameter` =
  rebindable parameter; `constant + parameter` = fixed coefficient.
- `variability` axis dissolved — 'variable' was just 'not given' and
  could contradict determination (constant+derived).
- Seed (`graph_store.py`), `data/ontology.trig`, and `test_seed_axes`
  updated in place — zero `axisValue` triples existed to migrate.

**Equation editor classification UI** (`5db7649` + uncommitted):

- `/api/equation/context` serves `axes` + `domains`; `VariableIn`
  round-trips `classifications` (axis IRI → term IRI →
  `promo:axisValue`).  `_class_from_classifications` bridges to the
  legacy `variableClass` (constant|parameter label wins, else `state`).
- `axisClassifications.tsx` — `AxisClassifications` component (one
  dropdown per applicable axis, domain-ancestry filtered),
  `applicableAxes`/`deriveType`/`findTermIri` helpers,
  `FIELD_LABEL_STYLE`, `hiddenAxes` prop.
- Wired into `DependentVariableEditor`, `PortVariableEditor`,
  `VariableDetailDialog` — flat class select kept as fallback when no
  axes apply.  Port editors hide `determination` (structural);
  Instantiate forcing sets `function=parameter`.

**UI fixes** (`42df668` + uncommitted):

- `NetworkTreeSelect` rendered root's children twice — now computes
  true roots (keys nobody lists as a child).  `maxHeight` prop added.
- `_spa_index` serves `index.html` with `Cache-Control: no-cache` —
  stale cached index 404'd the hashed bundle after rebuilds.
- Both variable editors: two-row header (title+actions / domain tree +
  stacked Name→LaTeX→axis dropdowns, aligned label cells).

## State

- Backend tests: 313 pass (`uv run pytest backend/ -x -q`); ontology
  suite 64 pass.  `tsc --noEmit` clean; app rebuilt and served from
  `apps/equation-editor/dist` via the backend.
- Uncommitted: axis redefinition (determination{constant,variable},
  parameter→function), editor layout + alignment, doc updates,
  `data/library.trig` (dirty from use).

## Deferred / open

- `VariableEditor.tsx` + `DependentVariableDialog.tsx` remain dead code
  (live paths: PortVariableEditor, DependentVariableEditor,
  VariableDetailDialog).
- `variable_class` still written alongside `classifications` — the
  checker/builder read it; the bridge is the transition mechanism.
