# Equation Editor — Implementation Status

**Last updated:** 2026-09-18 (end of session)

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
| `VariableWizard` | `components/VariableWizard.tsx` | Multi-step flow for creating port or dependent variables (domain → class → details). |
| `VariableEditor` | `components/VariableEditor.tsx` | Direct port-variable editor — currently unreferenced (kept for the debug context popup). |
| `DependentVariableEditor` | `components/DependentVariableEditor.tsx` | RHS expression input, Check, LaTeX preview, and result panel. |
| `VariablePalette` | `components/VariablePalette.tsx` | Variable list grouped by network; click to view details, click `×` to delete with cascade impact. |
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
  - **Vendored assets:** `templates/resources/` holds old-ProMo's
    `defs.tex`/`defvars.tex`/`header.tex`/`automata_tables.tex`
    (RepositoryInfrastructure) — `\input` lines are inlined by
    `document.py` so the served `.tex` compiles standalone.
    `templates/legacy/` keeps the unported sources (equation-list
    variants, `template_main.python`, compile scripts) for reference.
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
