# Equation Editor — Implementation Status

**Last updated:** 2026-09-10

## Current state

Backend is functional — parser, checker, compile space, units, context
protocol, and FastAPI service are implemented and tested.  Frontend is
a placeholder only.

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
| `test_corpus.py` | 73 expressions from ProMo13 `var_equ_rdf.ttl` | ✅ All parse; 28/73 pass full checks |

### Corpus pass-rate (28/73)

All 73 expressions parse successfully.  The 45 checker failures cluster
into two root causes, both related to missing data in the ProMo13 TTL
export — not bugs in the checker:

1. **`index_structures` empty in old export** — `ReduceProduct` and
   `Product` fail because variables have no index structure.
2. **Units absent** — all variables are dimensionless in the corpus, so
   unit errors cannot be detected.
3. **Domain tree missing** — some expressions hit
   `AmbiguousVariableError` because the real authoring network is not
   recorded.

See `docs/equation-editor-known-issues.md` for details.

## Frontend

Placeholder only — `apps/equation-editor/README.md`.

### Planned frontend

- Expression input with syntax highlighting and parenthesis matching.
- Variable palette populated from the ontology context.
- LaTeX preview of parsed expressions.
- Inline error display from parser/checker.
- Equation list and variable-definition management.

## Pending items

- Build React frontend.
- Wire frontend to FastAPI backend.
- Implement `RdfContext` provider (once ontology graph store exists).
- Code generation targets (Python, Matlab, LaTeX).
- RDF vocabulary finalization for equations, operators, variables.

## How to run

```bash
cd /home/heinz/1_Gits/CAM14/ProMo14/backend
pip install -r requirements.txt
python -m pytest equation/          # run all equation tests
python -m pytest equation/test_corpus.py -v  # corpus replay with diagnostics
uvicorn main:app --reload           # start API server
```
