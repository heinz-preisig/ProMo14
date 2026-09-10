# Equation Editor Overview

## Role in the suite

The Equation Editor defines the mathematical behaviour of base
entities.  The user writes expressions in the ProMo math language; the
backend parser and checker validate syntax, units, and index
structures.  A checked expression is trusted by all downstream
consumers (Behaviour Linker, code generator) — no re-checking occurs.

See `docs/suite-overview.md` for the full pipeline and cross-cutting
contracts.

## Consumes

- **Ontology context** via the `EquationContext` protocol
  (`backend/equation/context.py`): variables (keyed by IRI, with units,
  index structures, tokens, network), indices (keyed by IRI, with token
  bindings), and the domain tree (for accessible-network resolution).
- **Language symbol vocabulary** — operators, functions, delimiters as
  IRIs from the published language ontology.

## Produces

- **Var/expr knowledge graph** (JSON-LD named graph) containing:
  variable resources, equation resources (LHS variable IRI + RHS token
  sequence as `rdf:List` + incidence list), index and token definitions.
- **Checked expressions** — each carries inferred units, index
  structures, and a variable incidence list.  Stored as token sequences
  of IRIs, not AST trees.

## Language

The ProMo math language is a context-free expression language with
index-structured tensor operations.  Key characteristics:

- No numeric literals (constants are variables or `Instantiate`).
- Function-call syntax only (`Integral(...)`, `Product(...)`, etc.).
- No unary minus (negation is `neg(...)`).
- Operators: `+`/`-` (sum), `*` (Einstein reduce product), `:` (expand
  product), `.` (Hadamard), `^` (power, right-associative).
- Functions: `exp`, `log`, `ln`, `sqrt`, `sin`, `cos`, ... (dimensionless
  input); `abs`, `neg`, `diffSpace`, `left`, `right` (index-structure
  retaining); `inv`, `sign`.
- Higher-order: `Integral`, `Product`, `Root` (implicit solve),
  `TotalDiff`, `ParDiff`, `reduceSum`, `MaxMin`.
- Variable qualification: `network!label` for cross-network references.

Full grammar and token table: see ADR-005.

## Semantic checks

The checker runs during AST construction (not as a separate pass):

| Operator | Checks |
|----------|--------|
| `Add` | Units equal; index structures equal |
| `ReduceProduct` | Exactly one common index; result = symmetric difference |
| `ExpandProduct` | Index sets disjoint; result = union |
| `Hadamard` | Index structures equal; units multiply |
| `Power` | Basis and exponent dimensionless |
| `Integral` | Integration variable and limits share index structure |
| `TotalDiff` / `ParDiff` | Units = dx − dy; indices = union |
| `Root` | Target variable must appear in dependency set |
| `Instantiate` | Copies units and indices from source variable |

Units are 8-exponent SI vectors (`time, length, amount, mass,
temperature, current, light, nil`).

## Architecture

```
backend/equation/
├── parser.py          # hand-written recursive-descent parser (replaces TPG)
├── syntax.py          # AST node dataclasses
├── symbols.py         # operator/function/delimiter symbol table
├── checker.py         # semantic checker (units, indices, incidence)
├── compile_space.py   # variable resolution, network!label, temp naming
├── context.py         # EquationContext protocol + DictContext
├── units.py           # SI unit vector and operations
├── errors.py          # VarError hierarchy
├── service.py         # FastAPI router: /parse, /check
└── test_*.py          # parser, checker, compile_space, units, corpus tests
```

### Why the operator layer stays in Python

- The existing implementation encodes correct index/unit rules.
- The math is easier to verify and extend in Python than TypeScript.
- The backend needs the same logic for validation and code generation;
  duplicating it in the browser creates two sources of truth.
- A thin client keeps the browser app fast.

### Browser architecture

The frontend will be a React app calling the FastAPI backend:

- Expression input with syntax highlighting and parenthesis matching.
- Variable palette populated from the ontology context.
- LaTeX preview of parsed expressions.
- Inline error display from parser/checker.
- Equation list and variable-definition management.

## Key design decisions

| Decision | ADR / doc | Summary |
|----------|-----------|---------|
| Replace TPG with hand-written parser | ADR-005 | TPG is overkill for a small LL-friendly grammar. |
| JSON-LD as working format | ADR-005 | Replaces `variables_v8.json`; same graph is edited, saved, and published. |
| Token sequences, not AST trees | ADR-005 | Expressions stored as `rdf:List` of IRIs; external compilers re-parse. |
| Publish–consume contract | ADR-005 | Checked = trusted; no downstream validation. |
| `EquationContext` protocol | `equation-context-contract.md` | Ontology seam; checker unchanged when provider changes. |
| Network hierarchy resolution | `equation-context-contract.md` | Local-first, then accessible ancestors, then global unique fallback. |
| Units: both SI vector and QUDT IRI | `ontology-data-model.md` | Vector for checking; IRI for semantic identity. |

## Interaction with other modules

- **Receives from:** Ontology Editor (variables, indices, domain tree
  via `EquationContext`).
- **Sends to:** Behaviour Linker (var/expr knowledge graph).
- **Shared with code generator:** the var/expr graph is the single
  source of truth for tensor-oriented code generation.

## Detailed references

- `docs/ADR-005-equation-editor.md` — full language spec, parser
  assessment, variable schema review, publishing/merging strategy.
- `docs/equation-context-contract.md` — `EquationContext` protocol and
  `CompileSpace` resolution rules.
- `docs/ontology-data-model.md` — RDF schema for variables, indices,
  equations, tokens; loader contract.
- `docs/equation-editor-known-issues.md` — deferred issues from corpus
  replay.
