# Equation Editor — Implementation Status

**Last updated:** 2026-09-25

## Current state

Backend and frontend are functional.  The parser, checker, compile
space, units, context protocol, and FastAPI service are implemented and
tested; the React + TypeScript + Vite frontend in
`apps/equation-editor/` is also implemented.

## Backend

| Component | File | Status |
|-----------|------|--------|
| Parser (recursive-descent) | `parser.py` | ✅ Complete — replaces ProMo13 TPG |
| AST nodes | `syntax.py` | ✅ Complete |
| Symbol table | `symbols.py` | ✅ Complete |
| Semantic checker | `checker.py` | ✅ Complete — units, indices, incidence |
| Compile space | `compile_space.py` | ✅ Complete — variable resolution, temp naming, hierarchy-aware |
| Context protocol | `context.py` | ✅ Complete — `EquationContext` + `DictContext` |
| Units | `units.py` | ✅ Complete — 8-exponent SI vector |
| Errors | `errors.py` | ✅ Complete |
| FastAPI service | `service.py` | ✅ Complete — `/parse`, `/check`, `/context`, `/variables` |

## API endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/equation/parse` | POST | Syntax-only parse; returns AST as JSON |
| `/api/equation/check` | POST | Parse + semantic check; returns units, indices, incidence |
| `/api/equation/context` | GET | Variables, indices, network tree for the selected graph's pin set |
| `/api/equation/variables` | POST/PUT/DELETE | Variable CRUD in the selected artefact graph |

All endpoints accept `?graph=<iri>` (2026-09-17).  The context resolves
against the artefact plus its transitive `usesOntology` closure
(`RdfStore.resolution_scope`, R4); variable writes land in the selected
artefact graph and mint IRIs under `{graphIRI}#`; frozen version graphs
are rejected with 403.  Without `?graph=` the legacy dataset-wide scope
applies and writes go to the working ontology.

## Tests

| Test file | Coverage | Status |
|-----------|----------|--------|
| `test_parser.py` | Parser syntax, precedence, error cases | ✅ Passing |
| `test_checker.py` | Semantic checks: units, indices, operators | ✅ Passing |
| `test_compile_space.py` | Variable resolution, network hierarchy, temps | ✅ Passing |
| `test_units.py` | SI unit vector arithmetic | ✅ Passing |
| `test_codegen.py` | Codegen: python/matlab/latex targets | ✅ Passing |
| `test_document.py` | LaTeX document rendering | ✅ Passing |

119 tests pass in `backend/equation` (2026-09-18).

The ProMo13 corpus replay (73 expressions, 70/73 passing) has been
archived to `archive/test_corpus.py`.  The new regression baseline will
be expressions re-entered through the equation editor.

## Frontend

Implemented as a React + TypeScript + Vite app in
`apps/equation-editor/`.  It calls the FastAPI backend via
`POST /api/equation/parse` and `POST /api/equation/check`.

### Components

| Component | File | Purpose |
|-----------|------|---------|
| `PortVariableEditor` | `components/PortVariableEditor.tsx` | Single-dialog port variable definition: domain tree, class, name, LaTeX symbol, SI units, index structures. |
| `VariableEditor` | `components/VariableEditor.tsx` | Direct port-variable editor — currently unreferenced (kept for the debug context popup). |
| `DependentVariableEditor` | `components/DependentVariableEditor.tsx` | RHS expression input, Check, LaTeX preview, and result panel. |
| `VariablePalette` | `components/VariablePalette.tsx` | Variable list grouped by network — filter box, collapsible groups, alphabetical sort (2026-09-20); click to view details, `×` to delete with cascade impact. |
| `VariableTable` | `components/VariableTable.tsx` | Sortable/filterable repository browser in the main pane; expandable rows show a variable's equations (2026-09-20). |
| `ExpressionInput` | `components/ExpressionInput.tsx` | Operator/function buttons and keyboard input. |
| `LaTeXPreview` | `components/LaTeXPreview.tsx` | Rendered expression with index subscripts. |
| `ResultPanel` | `components/ResultPanel.tsx` | Check result with units, index structure, incidence, and candidate suggestions on error. |
| `EquationList` | `components/EquationList.tsx` | Saved dependent equations. |
| `ContextEditor` | `components/ContextEditor.tsx` | JSON editor for variables, indices, and the network tree (debug popup). |

### Features

- Port and dependent variable creation.
- Domain / network tree selection.
- SI unit vector entry.
- Index structure selection with `short_name` display.
- Single **Check** action that parses then semantically checks the RHS.
- Inline parser / checker error display with candidate suggestions.
- LaTeX preview with index subscripts.
- Save and reload checked equations.
- Debug equation context (JSON) popup.
- Index records carry optional `sub_index_of` / `selector` fields
  (2026-09-20, BL doc §16) — plumbed through `IndexIn`, context
  serialization, check-time `Index` construction, and the frontend
  `Index` interface.  Seven arc sub-indices are seeded (`A_mass`,
  `A_energy`, `A_diff`, `A_conv`, `A_heat`, `A_rad`, `A_work`); the
  checker treats them as plain distinct indices.
- **Multi-axis classifications (2026-09-24):** `/context` serves
  `axes` + `domains`; `AxisClassifications` (`axisClassifications.tsx`)
  renders one dropdown per applicable axis (resolved via domain
  ancestry) in all three variable editors.  Variables round-trip a
  `classifications` map (axis IRI → term IRI → `promo:axisValue`);
  the legacy `variableClass` is derived on save
  (`_class_from_classifications`: `constant`/`parameter` label wins,
  else `state`).  `hiddenAxes` prop hides axes that are structural —
  `determination` is hidden on port variables (port-ness is the
  `port_variable` flag, not a pick).
- **Axis merge (2026-09-24):** physical axes are `determination`
  {constant, variable} + `function` {…, parameter} — `variability`
  dissolved, `port`/`derived` dropped as terms (structural: flag +
  equation presence).  Parameter is a *function* term — a
  characteristic value in a function, often embodying an assumption.
- **Domain tree fix (2026-09-24):** `NetworkTreeSelect` rendered
  root's children twice (nested + top-level); now computes true roots.
  `maxHeight` prop added (editors pass 220).
- **SPA caching (2026-09-24):** `_spa_index` serves `index.html` with
  `Cache-Control: no-cache` — a stale cached index 404'd the hashed
  bundle after rebuilds (blank page).
- **Editor header layout (2026-09-24):** two-row header in both
  variable editors — title + actions on top; domain tree left,
  Name/LaTeX/axis dropdowns stacked right with aligned fixed-width
  label cells (`FIELD_LABEL_STYLE`).
- **Variable selection and validation UX (2026-09-25):** palette chips
  show bare labels under their network headings; groups sort by relevance
  to the expression domain, filtering also matches network names, and
  insertion qualifies foreign variables as `network!label`.  Disabled
  Accept/Add actions now show the blocking reason inline.  Check requests
  omit an invalid unnamed draft LHS, and non-2xx/FastAPI validation bodies
  are converted to readable result-panel errors instead of a blank “Error”.
- **KaTeX/LaTeX normalization (2026-09-25):** preview and backend emit
  standard commands (`\arcsin`, `\arccos`, `\arctan`, `\sqrt`, and
  `\left|…\right|` for `abs`) rather than undefined macros.  Raw LaTeX
  aliases normalize unbraced subscript runs (`F_conv` → `F_{conv}`;
  `\hat{m}_conv` → `\hat{m}_{conv}`) consistently in preview, codegen,
  and the printable variable table; already braced `_{…}` and escaped
  `\_` remain unchanged.
- **Focused domain/role correction (2026-09-25):** the existing-variable
  dialog keeps role classifications editable even when equations reference
  the variable.  Domain remains editable when references are only its own
  defining LHS equations (which move with it), but is locked when foreign
  equations reference it.  Units and index structures remain usage-locked.
  The backend enforces the same field-level policy.  Legacy variables with
  an empty `classifications` map show an explicit warning and editable blank
  role selectors; roles are not guessed from the lossy legacy class.

## Pending items

- ~~`RdfContext` reads only the seeded `ontology_graph`.~~ **Done
  (2026-09-15):** `RdfContext` reads all named graphs in the dataset
  (ontology graph + var/expr graphs) using the ProMo14 vocabulary
  (`promo:Variable`/`promo:Index`, `promo:hasEquation`,
  `promo:unitVector`).  The network tree is built from
  `promo:Domain`/`promo:parent` with a synthetic `root` and cycle
  breaking.  Ontology `indexClass` source kinds (node/arc/...) map to
  the checker's `index`/`block_index`.  The legacy v8 loader
  (`backend/core/loader.py`) and all legacy vocabulary handling were
  removed — archived to `archive/loader.py`.
- ~~Wire the frontend to the real ontology graph store~~ **Done:** the
  frontend already calls `GET /api/equation/context`; verified
  end-to-end (variable create → context → `/check` infers units).
- ~~`?graph=` session param~~ **Done (2026-09-17):** `api.ts` reads the
  hub's `?graph=<iri>` once and appends it to every call; the backend
  scopes context to the artefact's pin set and writes to the artefact
  graph.
- ~~Persistence UX: variables created via POST live in memory until the
  ontology's Save / `POST /save` — dirty-state handling still pending.~~
  **Done (2026-09-18):** store-global dirty tracking (middleware flags
  `RdfStore.dirty` on successful mutations; `GET /api/ontology/status`);
  header shows "● unsaved" badge + a Save button calling
  `POST /api/ontology/save`; `beforeunload` warns on tab close.
- ~~Code generation targets (Python, Matlab, LaTeX).~~ **Done
  (2026-09-18):** `backend/equation/codegen.py` renders the `Checked`
  tree (per-node index IRIs drive `tensordot` axes / `einsum` labels);
  `POST /api/equation/generate` (same context contract as `/check` +
  `target`); code targets name variables by `internal_id`, LaTeX by
  label + index subscripts; `total_diff`/`par_diff`/`fsolve` emit named
  helpers the runtime must supply.  UI: target select + code view in
  `DependentVariableEditor` after a successful check.  37 tests in
  `test_codegen.py`.
  - **Matlab** targets the `MultiDimVar` library (Einstein notation):
    `einsum(a,b)` for Hadamard/expand, `einsum(a,b,{'N'})` for
    contraction, `reducesum`/`reducemult` for index reductions — all
    keyed by index `internal_code` labels.  The library is vendored at
    `runtime/matlab/@MultiDimVar` (from CAM13 `static_assets`; see
    `runtime/matlab/README.md`).
  - **Python** is provisional NumPy/SciPy — no operator runtime exists
    yet (old-ProMo's `python_simulation` helpers: `IndexSet`,
    `khatriRao`, `blockReduce`).  Whole-simulation codegen is
    post-instantiation work, not per-expression.
- ~~Printable LaTeX documentation (variables + equations).~~ **Done
  (2026-09-18):** `GET /api/equation/document` renders a landscape
  article via Jinja2 (`backend/equation/templates/document.latex`,
  ported from old-ProMo `EquationEditor_v01` templates — single-file
  variant).  Variables table (symbol, label, doc, type, units, eq
  cross-refs) + equations table (`lhs := rhs`, doc, layer), sectioned
  by network, hyperlinked `v:N`/`e:N`.  Each RHS is re-rendered through
  parse→check→latex; cached `rhs_latex`/verbatim fallback.  UI:
  "LaTeX doc" header link.  5 tests in `test_document.py`.  `jinja2`
  added to backend deps.
  - **PDF output (2026-09-22):** `?format=pdf` compiles the `.tex`
    server-side via `document.py compile_pdf` — pdflatex ×2 in a temp
    dir (hyperref/TOC settle on pass 2), `-no-shell-escape`, 90 s
    timeout; `PdfCompileError` returns the `!`-error log tail as a 500
    plain-text body.  Requires TeX Live on the host (dev machines have
    it); `?format=tex` remains for source.  UI: "PDF doc" + ".tex"
    header links — the PDF opens in the browser's built-in viewer.
    2 compile tests (skipped without pdflatex).
    **Capability gating:** `GET /context` reports
    `capabilities: {pdf: bool}` (`document.py pdf_available` =
    `shutil.which("pdflatex")`); the "PDF doc" link renders only when
    true, so TeX-less hosts degrade silently.  Docker: the default
    image has no TeX — build with `--build-arg WITH_TEX=true` to
    install `texlive-latex-base` + `-recommended` (~400 MB).
  - **Vendored assets:** `templates/resources/` holds old-ProMo's
    `defs.tex`/`defvars.tex`/`header.tex`/`automata_tables.tex`
    (RepositoryInfrastructure) — `\input` lines are inlined by
    `document.py` so the served `.tex` compiles standalone.
    `templates/legacy/` keeps the unported sources (equation-list
    variants, `template_main.python`, compile scripts) for reference.
- ~~Underscore in surface names breaks LaTeX.~~ **Fixed (2026-09-20):**
  sub-index `internal_code`s like `A_heat` landed raw inside `_{...}`
  → double-subscript error (KaTeX preview + `.tex` compile).  Surface
  names are atomic, not math, so `_` is escaped to `\_` at emission:
  `codegen.tex_escape` (var subscripts, `\sum`/`\prod`/reduce indices),
  `document.py` `_var_symbol` + `{{ net|tex }}` on `\subsection` titles
  (network names hit text mode there), frontend `latex.ts` `texEscape`
  (subscripts + unresolved Var fallback).  Matlab/python keep raw
  aliases.  Regression tests in `test_codegen.py`/`test_document.py`.
- ~~Equations persistence into `VariableRecord.equations`.~~ **Done
  (2026-09-18):** the chain already existed — `saveVariable` sends the
  equation dict, `add_variable_dict`→`add_equation` writes
  `promo:Equation` + `hasEquation`, `_variable_equations` reads them
  back.  The one blocker: `EquationRecord.rhs_latex` was `str` and
  rejected the frontend's `null` → 422 on every equation save; now
  `Optional[str]`.  Verified end-to-end: equation round-trips and
  renders in `/document`.  Polish item: frontend uses `E_${Date.now()}`
  internal IDs — sequential `E_N` minting would be cleaner.
- ~~Index short-name capitalisation (arc→A, node→N, …).~~ **Done
  (2026-09-18):** seed indices in `graph_store.py` now use `S`/`N`/`A`
  (species/node/arc); persisted `data/ontology.trig` migrated —
  `shortName` + `internal_code` alias: arc→A, node→N, reaction→Q,
  species→S.  `internal_code` is the expression-language surface token
  *and* the LaTeX subscript / Matlab label — matches the
  `demoContext.ts` convention which already used capitals.
- ~~Per-variable LaTeX symbol (`latex` alias).~~ **Done (2026-09-18):**
  `promo:latex` stores a raw-LaTeX symbol per variable (the
  `internal_code`/`latex`/`matlab` alias predicates were already
  schema-supported — `_aliases()` reads them, `_add_aliases` writes
  them).  UI: "LaTeX symbol" field in `VariableWizard` (port step),
  `VariableEditor`, `DependentVariableDialog`, and `DependentVariableEditor`
  (draft variable carries `aliases.latex` through check/generate/accept;
  the preview resolves the draft LHS); editable field in the `App.tsx`
  variable detail modal (re-POSTs the variable).  Renderers: frontend
  `latex.ts` `Var` case uses `aliases.latex` verbatim; backend codegen
  `_var_name` + `document.py` `_var_symbol` prefer the alias over
  `\mathit{label}`.  `add_variable_dict` clears the direct-alias
  predicates before writing → replace semantics (clearing the field
  removes `promo:latex`).
- ~~`Instantiate(expr, shape)` unit-borrowing form.~~ **Redesigned
  (2026-09-19, ADR-008):** `Instantiate(proto)` — single `Var`
  argument, valid only as the entire RHS.  Declares the LHS variable
  as a new *instance* of the prototype: inherits the prototype's units
  and index structure, incidence is empty (type-level reference, not a
  value dependency), LHS class enforced to `constant`/`parameter`
  (checker + restricted class dropdown in `DependentVariableEditor`,
  defaulting to `parameter`).  Codegen renders a parameter placeholder
  (`V_x = None  # parameter: instance of V_t`); LaTeX renders
  `lhs := \mathrm{inst}(proto)` — the instance's symbol is the user's
  latex alias.  Saving writes `promo:instanceOf` → prototype IRI and
  auto-classifies `equation_class = "instantiate"`.
- **Universal constants (ADR-008):** `zero`, `one`, `half` seeded in
  the ontology (network `root`, class `constant`) with pre-bound
  `promo:value` (`0`/`1`/`0.5`) and latex aliases — permanent,
  non-deletable in the palette (shown with a `=value` badge).
  `RdfStore._seed_constants` is idempotent and also runs from `load()`
  as a migration for pre-existing `ontology.trig`.  Codegen inlines
  `promo:value` when present (`half . M` → `0.5 * V_3`); unbound
  parameters keep their `V_N` slot until the instantiation stage.
- **Variable-definition UX (2026-09-19):** the sidebar now has two
  buttons — *New port variable…* and *New dependent variable…* — that
  open their editors directly (the multi-step `VariableWizard` is
  gone).  `PortVariableEditor.tsx` is a single dialog with the same
  header widgets as the dependent editor (domain tree, class, name,
  LaTeX symbol) plus the SI unit vector, index-structure picker and a
  doc field.  Accept/Add is gated on the base requirements: port —
  name + domain + class (units default to dimensionless, indices to
  scalar); dependent — name + domain + class + a successful check.
  Names are validated against the lexer identifier rule
  `[a-zA-Z_][a-zA-Z0-9_]*` (shared `validation.ts`, enforced again by
  a `VariableIn.label` validator in `service.py`); the last
  domain/class choice is remembered across both editors.
  **Names are case-sensitive end-to-end:** the minted IRI preserves
  case (`promo:Rho` ≠ `promo:rho`), matching the lexer and the
  `rdfs:label` lookup — previously `toLowerCase()` in the mint made
  `Rho`/`rho` silently collide on one IRI.  Both editors warn on an
  exact-name collision (save overwrites) and on a case-only variant
  (`findNameCollision` in `validation.ts`).
- LaTeX→image cache (deferred, noted 2026-09-18): old-ProMo rendered
  per-variable/equation PNGs (`V_N.png`/`E_N.png`, standalone .tex →
  latex → pnglatex.bash) into the ontology's LaTeX dir, invalidated by
  PNG-mtime vs. record `modified`.  ProMo14 renders previews client-side
  via KaTeX, so a server cache is only needed for Konva canvas images,
  external embedding, or full-LaTeX macros KaTeX can't do.  When
  opportune: `GET /api/equation/png/{internal_id}` → codegen latex →
  standalone tex → latex/dvipng (or vendored pnglatex.bash) → cache
  keyed by internal_id + `modified`; consider SVG over PNG.
- RDF vocabulary finalization for equations, operators, variables.
- External-IRI links on variables (noted 2026-09-22): old-ProMo could
  link a variable to external IRIs (e.g. QUDT quantity kinds, external
  ontology terms).  Needs a predicate choice (`promo:seeAlso` /
  `owl:sameAs`-style), a field in the variable schema
  (`VariableIn`/`add_variable_dict`), and a UI affordance in the
  variable detail modal.

## How to run

### Backend

```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
uv sync

# Run equation tests
uv run python -m backend.equation.test_compile_space

# Start API server
uv run uvicorn backend.main:app --port 8000
```

### Frontend

```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
npm install
npm run dev:equation  # Vite dev server on http://localhost:3001
```

The dev server proxies `/api` to `http://localhost:8000`.
