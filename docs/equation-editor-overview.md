# Equation Editor Overview

## Role in the suite

The Equation Editor defines the mathematical behaviour of base
entities.  The user writes expressions in the ProMo math language; the
backend parser and checker validate syntax, units, and index
structures.  A checked expression is trusted by all downstream
consumers (Behaviour Linker, code generator) — no re-checking occurs.

See `docs/suite-overview.md` for the full pipeline and cross-cutting
contracts.

## Core modelling concepts: the var/expr graph

A ProMo model is a **bipartite variable–expression graph** that is built
from the bottom up.

- **Port variables are the foundation.**  To define a variable the user
  first selects a **domain (network)** and a **variable class** that applies
  to that domain.  The port variable is then declared with a name, a
  variable class, a network, physical units, and an index structure.  Port
  variables have **no defining RHS expression**.
- **Derived variables** are created by first selecting a **domain (network)**
  and a **variable class** that applies to that domain, then giving the
  variable a name and a checked RHS expression.  The RHS may only use
  variables that are already declared or already defined, so the graph stays
  acyclic and lower-triangular.
- **Multiple definitions are allowed.**  A derived variable can have many
  checked equations.  Each is an independent `promo:Equation` resource with
  its own expression network and equation class.  The Behaviour Linker
  later selects which definitions are active for a given base entity.
- The Equation Editor’s job is to parse and check each RHS, producing the
  var/expr knowledge graph that downstream tools consume.

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

## User workflow

### 1. Port variable (foundation)

A port variable carries physical meaning directly; it has no defining RHS expression.

1. Click **New variable…** in the left sidebar.
2. Choose **Port variable**.
3. In the multi-step wizard:
   - Select a **domain / network** from the tree.
   - Select a **variable class**.
   - Enter a **name**.
   - Enter the **SI unit vector**.
   - Select the **index structures** from the ProMo ontology indices.  Each index shows its `short_name` (e.g. `N` for `node`) for quick reading.
4. Click **Add variable**. The variable appears in the left palette.

### 2. Dependent variable (RHS definition)

A dependent variable is defined by a checked RHS expression over existing variables.

1. Click **New variable…**.
2. Choose **Dependent variable**.
3. In the wizard, select a **domain / network**, a **variable class**, and enter a **name**.
4. The **Dependent variable editor** opens:
   - The LHS name is already set.
   - Type the RHS expression using the variable palette and the operator/function buttons.
   - Click **Check** (or `Ctrl/Cmd + Enter`) to parse and semantically check the RHS in one step.
   - The **LaTeX preview** shows the expression with index subscripts using the index `short_name`.
   - The **result panel** shows the LHS name, inferred units, index structure, and incidence.
5. Add **documentation** for the variable.
6. Click **Accept** to store the checked equation and create the dependent variable.

### 3. Inspecting, editing and deleting variables

- Click any variable in the left palette to open a **detail popup** with its IRI, network, class, units, index structures (`short_name` + label), and defining equation.
- Click the `×` next to a variable to delete it.  The editor computes and shows the **cascade impact**: all dependent variables and equations that will be removed because they depend on the target directly or indirectly.
- The **Debug equation context (JSON)** popup (opened from the right pane) lets advanced users edit variables, indices, the network tree, and the active expression network directly.  Click **Apply** to load the edited context back into the editor.

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

The frontend is a React + TypeScript + Vite app calling the FastAPI backend:

- **Variable wizard** (`VariableWizard`) — multi-step flow for creating port or dependent variables (domain → class → kind → details).
- **Dependent variable editor** (`DependentVariableEditor`) — expression input, single **Check** action that parses then semantically checks, LaTeX preview with index subscripts, and result panel.
- **Variable palette** (`VariablePalette`) — grouped by network; click to view details, click `×` to delete with cascade impact analysis.
- **Expression input** (`ExpressionInput`) — operator/function buttons and keyboard shortcuts; one **Check** button triggers parse + check.
- **LaTeX preview** (`LaTeXPreview`) — rendered expression, including index subscripts from each variable's `index_structures` mapped through the `short_name` of the index.
- **Result panel** (`ResultPanel`) — shows check result with user-defined LHS label, inferred units, index structure (`short_name` + label), and incidence.
- **Equation list** (`EquationList`) — saved dependent equations.
- **Debug context popup** — the **Equation context (JSON)** editor is hidden behind a button and opens as a modal, keeping the main view focused on the repository.

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
