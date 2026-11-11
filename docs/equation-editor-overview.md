# Equation Editor Overview

Living — realigned to rulings through 2026-11-11.

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

- **Var/expr knowledge graph** containing variable and equation resources.
  Equations persist a canonical, ordered, IRI-bound semantic expression
  (`promo:rhsExpression` → `promo:Expression`/`promo:hasOperation`/
  `promo:hasArguments`) — landed 2026-09-27 — beside the textual `promo:rhs`
  source cache; reads treat the tree as authoritative and regenerate source
  (amended 2026-11-10).
- **Checked expressions** — each carries inferred units, ordered index
  structures, and a variable incidence list; the checked tree is what
  `rhsExpression` persists.

## Language

The ProMo math language is a context-free expression language with
index-structured tensor operations.  Key characteristics:

- No numeric literals — numeric symbols are variables: universal
  constants (`zero`, `one`, `half`) are seeded with pre-bound
  `promo:value`; model constants/parameters get values at the
  instantiation stage (ADR-008).
- `Instantiate(proto)` declares the LHS variable as a new instance of
  the prototype variable `proto` — whole-RHS declaration only, LHS must
  be class `constant` or `parameter` (ADR-008).
- Function-call syntax only (`Integral(...)`, `Product(...)`, etc.).
- No unary minus (negation is `neg(...)`).
- Operators: `+`/`-` (sum), `*` (reduce product), `:` (expand product),
  `.` (index-preserving product; historically called Hadamard), `^` (power,
  right-associative).
- Functions: `exp`, `log`, `ln`, `sin`, `cos`, ... require dimensionless
  input; `sqrt` accepts units only when every exponent is even; `abs`, `neg`,
  `left`, `right`, `sign`, and the index-preserving elementwise
  reciprocal `inv` are also available (amended 2026-11-10 — `inv` is
  elementwise since 2026-09-28, not scalar-only).
  Differential space is represented by ontology indices, not an expression
  function; the historical `diffSpace(expr)` function has been removed.
- Higher-order: `Integral`, `Product`, `Root` (implicit solve),
  `TotalDiff`, `ParDiff`, `reduceSum`, `MaxMin`.
- Variable qualification: `network!label` for cross-network references.

Full grammar and token table: see ADR-005.

## User workflow

### 1. Port variable (foundation)

A foundation variable is declared without a defining RHS expression.
Port-ness is independent: the connectable flag may be set on either
a foundation or a dependent variable (amended 2026-11-11, §34).

1. Click **New variable…** in the left sidebar and pick
   **foundation** on the mode switch at the top of the dialog (a
   declared variable — no expression panel is shown).
2. In the dialog header, select a **domain / network** from the tree, a
   **variable class**, and enter a **name** (letters, digits and
   underscore; must not start with a digit — names are case-sensitive).
   Optionally set a **LaTeX symbol**.
3. In the body, enter the **SI unit vector**, select the **index
   structures** from the ProMo ontology indices (each index shows its
   `short_name`, e.g. `N` for `node`), and declare **tokens**
   (carriesToken + token vector).  **Port (connectable)** marks the
   variable as connectable across an entity boundary.
4. Click **Save variable** — enabled once name and domain are
   set. The variable appears in the left palette.

### 2. Dependent variable (RHS definition)

A dependent variable is defined by a checked RHS expression over existing variables.

1. Click **New variable…** in the left sidebar and pick
   **dependent** (the default mode).
2. In the editor header, select a **domain / network**, a **variable
   class**, and enter the **LHS name** (same identifier rules as port
   variables).  Optionally set a **LaTeX symbol**.  Units, index
   structures and the token vector are **not** picked here — they
   derive from the checked expression; the **Port (connectable)**
   flag remains available for cross-entity supply (§34).
3. Type the RHS expression using the variable palette and the operator/function buttons.
4. Click **Check** (or `Ctrl/Cmd + Enter`) to parse and semantically check the RHS in one step.
   - The **LaTeX preview** shows the expression with index subscripts using the index `short_name`.
   - The **result panel** shows the LHS name, inferred units, index structure, and incidence.
5. Add **documentation** for the variable.
6. Click **Accept** — enabled once name, domain and class are set and
   the RHS has passed Check — to store the equation and create the
   dependent variable.

The editor remembers the last mode, domain and class choice, and
warns when the name collides with an existing variable (exact match
overwrites; a case-only difference is flagged since names are
case-sensitive).

**Fixed-signature rule** (§18): a variable that is not referenced by
*other* equations can be redefined — a new or rewritten equation may
change its units and index structures (owning definitions does not
count as "used": the variable's own equations are its definition,
so rewriting one is the sanctioned way to change the signature).
A variable referenced inside another equation's rhs has a fixed
signature: any equation attached or rewritten on it must derive
exactly the stored units and index structures, and a
signature-mismatched Check result blocks Accept.  The write path
independently 409s structural edits on foreign-referenced
variables.

### 3. Inspecting, editing and deleting variables

- Click any variable in the left palette to open a **detail popup** with its IRI, network, class, units, index structures (`short_name` + label), and defining equation.  The lock banner also lists **which equations reference it** — its own definitions (`lhs`) versus foreign uses inside another variable's rhs.
- Token **advisories** under a check result carry structured **fixes** (ruled 2026-11-11): e.g. an empty token signature offers "Declare 'V' signature-neutral (keep membership)" per contributing operand; clicking a fix shows the impacted equations (the reference list) before applying.  Signature-only writes pass the §18 lock; membership (`carriesToken`) stays locked — licensed-but-neutral membership (`carriesToken` + empty `tokenVector`) is legal.
- Click the `×` next to a variable to delete it.  The editor computes and shows the **cascade impact**: all dependent variables and equations that will be removed because they depend on the target directly or indirectly.
- The **Debug equation context (JSON)** popup (opened from the right pane) lets advanced users edit variables, indices, the network tree, and the active expression network directly.  Click **Apply** to load the edited context back into the editor.

## Semantic checks

The parser builds a syntax tree, then the checker performs units, ordered-index,
incidence and construct-specific semantic checks:

| Operator | Checks |
|----------|--------|
| `Add` | Units equal; index structures equal |
| `ReduceProduct` | Operands share exactly one index; that index is removed |
| `ExpandProduct` | Index sets disjoint; result = ordered union |
| `IndexPreservingProduct` | Units multiply; result = ordered union without eliminating common indices |
| `Power` | Basis and exponent dimensionless |
| `Integral` | Integration variable and limits share index structure |
| `TotalDiff` / `ParDiff` | Units = dx − dy; indices = union |
| `Root` | Target variable must appear in dependency set |
| `Instantiate` | Argument is a single `Var`; instance inherits the prototype's units and index structure; incidence empty; LHS class must be `constant`/`parameter` |
| `sqrt` | Every unit exponent even; result exponents are halved |
| `inv` | Index-preserving elementwise reciprocal — `inv(x[N]) → [N]`; units inverted |

Units are 8-exponent SI vectors (`time, length, amount, mass,
temperature, current, light, nil`). Index structures are ordered sequences of
unique index IRIs; duplicate indices are rejected for declared variables and
checked expression results.

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
└── test_*.py          # parser, checker, compile_space, units tests
```

### Why the operator layer stays in Python

- The existing implementation encodes correct index/unit rules.
- The math is easier to verify and extend in Python than TypeScript.
- The backend needs the same logic for validation and code generation;
  duplicating it in the browser creates two sources of truth.
- A thin client keeps the browser app fast.

### Browser architecture

The frontend is a React + TypeScript + Vite app calling the FastAPI backend:

- **Variable editor** (`DependentVariableEditor`) — one dialog with a
  creation-mode switch: **foundation** offers the manual signature
  pickers (SI units, index structures, tokens) and no expression
  column; **dependent** offers the variable palette plus expression
  input, a single **Check** action that parses then semantically
  checks, LaTeX preview with index subscripts, and a result panel.
  The **Port (connectable)** flag is available in both modes.
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
| Historical token-list proposal | ADR-005 | Superseded before implementation; the current store uses textual RHS, and the new design direction is an ordered semantic expression rather than a lexical token list. |
| Publish–consume contract | ADR-005 | Checked = trusted; no downstream validation. |
| `EquationContext` protocol | `equation-context-contract.md` | Ontology seam; checker unchanged when provider changes. |
| Network hierarchy resolution | `equation-context-contract.md` | Local-first, then accessible ancestors, then global unique fallback. |
| Units: both SI vector and QUDT IRI | `ontology-data-model.md` | Vector for checking; IRI for semantic identity. |
| Canonical IRI semantic expression | `math-language-ontology-comparison.md`; status 2026-09-27 | `promo:rhsExpression` stores operation IRI + ordered arguments; `promo:rhs` kept as non-authoritative source cache; reads regenerate source with current labels (amended 2026-11-10). |

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
- `docs/math-language-ontology-comparison.md` — historical comparison and the
  agreed requirements for compact language semantics and canonical IRI-bound
  expression storage.

### Token signature key identity (2026-11-11)

Token algebra normalises full token IRIs, `token_mass`-style keys and
bare fragments to the same fragment identity (`mass`).  Mixed persisted
key forms therefore cancel correctly; check results and adopted derived
signatures emit canonical fragment keys.  Membership declarations remain
separate from these advisory algebraic signatures.


## Global consistency check

Use **Check consistency…** in the header to check all equations in the
selected artefact and its pinned scope. The report opens inside the editor
and distinguishes structural errors, token advisories, untracked results
and consistent equations. An untracked result is not a verified token pass.
This complements the definition/deletion construction rules; it does not
replace them (ruled 2026-11-11, discussion §36).

Expand a result to inspect its expression, owner artefact, declared/derived
signatures, conflicting terms and operand declarations. Open the relevant
variable or equation directly; owning-artefact links let you correct a pin
at its source instead of creating a local shadow.

Where feasible, a suggested token signature correction offers an impact
preview and confirmation. The preview lists potentially affected equations
through the in-scope dependency chain and direct references across artefacts.
Apply changes only the signature, then rechecks the full scope. Membership,
units, indices and equations remain unchanged. Suggestions are not proof of
semantic correctness: inspect the cause before adopting a derived result.
Alternative definitions that disagree, frozen resources, missing membership
or a foreign owning graph block application and explain the next step.

Edits make the report out of date; **Check / recheck** refreshes it. The
backend independently rejects a stale correction. Corrections update the
in-memory store; use **Save** to persist them. Structural problems still
require authoring decisions—there is no automatic equation rewrite or
"fix everything" button. Control semantics is unchanged.
