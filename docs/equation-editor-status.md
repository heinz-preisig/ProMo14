# Equation Editor — Implementation Status

**Last updated:** 2026-09-11 (end of session)

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
| FastAPI service | `service.py` | ✅ Complete — `/parse`, `/check` endpoints |

## API endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/equation/parse` | POST | Syntax-only parse; returns AST as JSON |
| `/api/equation/check` | POST | Parse + semantic check; returns units, indices, incidence |

The check endpoint accepts the context (variables, indices, network
tree) in the request body.  Once the ontology graph store is available,
it will resolve the context from a graph IRI instead.

## Tests

| Test file | Coverage | Status |
|-----------|----------|--------|
| `test_parser.py` | Parser syntax, precedence, error cases | ✅ Passing |
| `test_checker.py` | Semantic checks: units, indices, operators | ✅ Passing |
| `test_compile_space.py` | Variable resolution, network hierarchy, temps | ✅ Passing |
| `test_units.py` | SI unit vector arithmetic | ✅ Passing |

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
| `VariableEditor` | `components/VariableEditor.tsx` | Direct port-variable editor (used by the debug context popup). |
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
- Code generation targets (Python, Matlab, LaTeX).
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
