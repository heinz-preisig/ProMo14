# ADR-005: Equation Editor — Language, Parser, and Browser Architecture

## Status

Draft — findings from ProMo13 `EquationEditor_v01` and proposed direction for the browser-based rewrite.

## Context

The Equation Editor defines the mathematical behaviour of base entities. In the
ProMo13 implementation it is a PyQt application whose core is a TPG (Toy Parser
Generator) parser embedded in `variable_framework.py`. The parser compiles a
context-free expression string into an operator tree; each operator performs
index-structure and SI-unit checking at construction time. The result is a
validated variable/expression structure that feeds the Behaviour Linker and,
later, code generation.

The suite is moving to browser-based frontends with a Python backend. This ADR
records what the existing language looks like, whether the parser should be
replaced, and how the operator layer maps onto the new architecture.

## The ProMo math language

### Tokens

| Token | Pattern | Purpose |
|-------|---------|---------|
| `Variable` | `[a-zA-Z][a-zA-Z0-9]*(![a-zA-Z][a-zA-Z0-9]*)?` | Variable label, optionally qualified as `network!label` |
| `SUM` | `[+-]` | Addition / subtraction |
| `POWER` | `^` | Exponentiation |
| `EXPAND` | `:` | Expand product (disjoint index sets) |
| `REDUCE` | `*` | Reduce product (Einstein-style index reduction) |
| `HADAMARD` | `.` | Hadamard (element-wise) product |
| `UFuncRetain` | `abs|neg|diffSpace|left|right` | Unary functions that retain index structure |
| `UFuncNone` | `exp|log|ln|sqrt|sin|cos|tan|asin|acos|atan` | Unary functions requiring dimensionless input |
| `UFuncInverse` | `inv` | Inverse |
| `UFuncLoose` | `sign` | Sign |
| `MaxMin` | `max|min` | Binary max/min |
| `IN` | `in` | Used inside `Integral` limits |

### Grammar (TPG `VerboseParser` docstring, as implemented)

```text
Expression -> Term ( SUM Term )*
Term       -> Factor ( EXPAND Factor
                     | HADAMARD Factor
                     | REDUCE [Index] Factor
                     | POWER Factor )*
Index      -> Variable
Identifier -> Variable
Factor     -> '(' Expression ')'
            | 'Integral' '(' Expression '::' Identifier 'in' '[' Identifier ',' Identifier ']' ')'
            | 'Product' '(' Expression ',' Index ')'
            | 'Root' '(' Expression ')'
            | MaxMin '(' Expression ',' Expression ')'
            | 'TotalDiff' '(' Expression ',' Expression ')'
            | 'ParDiff' '(' Expression ',' Expression ')'
            | 'reduceSum' '(' Expression ',' Index ')'
            | UnitaryFunction '(' Expression ')'
            | Identifier
UnitaryFunction -> UFuncRetain | UFuncNone | UFuncInverse | UFuncLoose
```

### Grammar (revised — precedence fix)

`POWER` is lifted out of the product loop into its own level above `Term`,
and made right-associative (`a^b^c = a^(b^c)`):

```text
Expression -> Term ( SUM Term )*
Term       -> Power ( EXPAND Power
                    | HADAMARD Power
                    | REDUCE [Index] Power )*
Power      -> Factor ( POWER Power )?
Index      -> Variable
Identifier -> Variable
Factor     -> (unchanged)
```

Now `a * b^c` parses as `a * (b^c)` and `a^b * c` as `(a^b) * c`.

### Quirks to preserve or fix

- **`POWER` precedence — FIXED.** In the old grammar `^` sat in the same
  postfix loop as `*`, `:`, `.`, so `a * b^c` parsed as `(a*b)^c`. The revised
  grammar gives `^` its own level above the product operators and makes it
  right-associative.
- **No numeric literals** — the grammar intentionally has no numbers; constants
  are introduced via `Instantiate(var, value)` or defined as variables.
- **Function-call syntax only** — `Integral`, `Product`, `Root`, `MaxMin`,
  `TotalDiff`, `ParDiff`, `reduceSum`, and unary functions all use `Name(args)`.
- **No unary minus** — negation is the `neg(...)` function, not a prefix `-`.

## AST and semantic checking

The parser's semantic actions instantiate operator classes that carry the
mathematical semantics. These classes are the valuable part and are independent
of TPG.

| Operator | Checks performed |
|----------|------------------|
| `Add` | Units equal; index structures equal |
| `ReduceProduct` | Exactly one common index (or explicit `*i`); result indices = symmetric difference |
| `ExpandProduct` | Index sets disjoint; result indices = union |
| `Hadamard` | Index structures equal; units multiply |
| `Power` | Basis and exponent dimensionless; result indices = basis indices |
| `MaxMin` | Units equal; index structures equal |
| `UnitaryFunction` | `UFuncNone` requires dimensionless argument; `UFuncRetain` keeps indices |
| `Integral` | Integration variable and limits share index structure; units = integrand × differential |
| `Product` | Argument dimensionless; removes the running index |
| `Root` (Implicit) | Variable to solve for must appear in the dependency set |
| `Instantiate` | Copies units and indices from the variable being instantiated |
| `TotDifferential` / `ParDifferential` | Units = dx − dy; indices = union |
| `ReduceSum` | Removes the summed index; units unchanged |
| `Brackets` | Pass-through |

`CompileSpace` supplies variable resolution (`network!label` namespacing),
index lookup, temporary-variable naming, and the target language for rendering.
`Units` is an 8-exponent SI vector (`time, length, amount, mass, temperature,
current, light, nil`) with `+` (equality check) and `*` (exponent addition).

## Variables, identifiers, and namespaces

ProMo13 gives every variable three names, each serving a different purpose:

| Name | Form | Scope | Purpose |
|------|------|-------|---------|
| **Label** | user-chosen symbol, e.g. `x`, `network!x` | unique within its definition network (and heirs) | what the user types in expressions |
| **Internal ID** | `V_<integer>` (variables), `E_<integer>` (equations) | globally unique in the variable/expression knowledge graph | codegen variable names, AST references, incidence lists |
| **IRI** | full RDF IRI | global, ties the variable to the outside world | semantic identity, ontology linkage |

The split is deliberate and worth keeping:

- **Labels are scoped, not unique.** A label is only unique from its definition
  network downwards. Resolution order: unqualified label → current expression
  network first; if undefined there and globally unique, auto-resolve; if
  ambiguous, require `network!label`.
- **Internal IDs are unique and code-safe.** `V_37` is a valid identifier in
  every target language, so generated code never collides with user labels,
  reserved words, or other namespaces. This is what makes codegen trivially
  correct.
- **IRIs are the semantic anchor.** In the RDF-based suite the IRI is the
  canonical identity; the `V_n` ID can be stored as a property
  (`promo:internalID`) or derived from the IRI's local name.

### Mapping to the new architecture

- **Backend owns ID allocation.** `CompileSpace` (or a dedicated registry in
  `backend/core`) hands out `V_n`/`E_n` IDs and mints IRIs. Sequential counters
  need a single allocator — fine, since parsing/checking is server-side anyway.
- **AST nodes reference the variable object**, which carries all three names.
  Serialisation to RDF uses the IRI; codegen uses the internal ID; the UI shows
  the label.
- **Browser UX:** the variable palette already knows the accessible networks,
  so users pick variables rather than type `network!label`. The text syntax
  stays for power users and for round-tripping stored expressions.
- **Temp variables** (`newTemp`) keep working: they get internal IDs but no
  user-facing label or persistent IRI until promoted to a real variable.

### Open points

- Keep `V_<int>`/`E_<int>` sequential counters, or switch to something
  collision-free across sessions (e.g. `V_<uuid>`)? Sequential is simpler and
  matches existing data; a central backend allocator makes it safe.
- Should the internal ID be *derived from* the IRI local name (one source of
  truth) or stored as a separate property (allows renaming IRIs without
  breaking generated code)?

## Publishing and merging knowledge graphs

ProMo13 exports the variable/expression knowledge graph as an RDF multi-graph
that includes the *ontologised grammar* itself. The intent is bigger than
storage: the var/expr ontology is meant to be a standalone contribution —
cleaner variable definitions than QUDT, with expressions as first-class
definitional relations between variables.

Two consequences:

- **Expressions are stored in internal notation** (the source string), together
  with the grammar. Any external compiler can re-parse the expression and feed
  a template machine to emit target code. Codegen is a downstream consumer of
  the graph, not baked into it.
- **The grammar must stay declarative and publishable.** If the grammar is to
  be ontologised, it should exist as data (a BNF-style spec serialisable to
  RDF), not only as code inside a hand-written parser. A hand-written parser is
  still fine — but we should maintain a declarative grammar spec as the
  publishable artifact and test the parser against it. (This is also a point in
  favour of a grammar-file-driven parser such as Lark, where the spec *is* the
  artifact.)

### The merge problem

Combining independently published sets (thermo, mechanics, fluid mechanics)
will inevitably produce conflicts: same labels, different meanings; same
internal IDs; incompatible units or index conventions.

Proposed strategy — isolate by construction, merge explicitly:

- **Named graphs as namespaces.** Each published set is a named graph with its
  own IRI base. Loading N sets is a union of named graphs — nothing collides
  because identity is `(graph, IRI)`. Named-graph membership doubles as
  provenance.
- **Internal IDs are graph-local.** `V_37` in the thermo graph is not `V_37`
  in the mechanics graph. On merge into a working space, either qualify
  (`thermo:V_37`) or re-mint fresh IDs. This reframes the earlier open point:
  the internal ID only needs uniqueness *within a compilation scope* — the
  `CompileSpace` of a combined model can re-allocate IDs at codegen time. The
  IRI is the stable identity across merges.
- **Labels map onto networks.** A published graph corresponds to a network, so
  `thermo!rho` and `fluid!rho` coexist under the existing `network!label`
  mechanism.
- **Equivalence is asserted, never inferred.** Cross-graph sameness
  (thermo's `rho` *is* fluid's `rho`) is an explicit mapping arc
  (`promo:equivalentTo` or `owl:sameAs`-style), created deliberately by the
  user — never deduced from label equality.
- **The checker is the conflict detector.** When expressions from different
  graphs are combined, the existing unit/index checks surface real
  incompatibilities instead of silent wrongness.

### What ProMo13 actually publishes

Found under `ProMo13/packages/Common/ontologies/`:

- **`promo_language.ttl`** — the ontologised language. A *flat vocabulary*:
  each symbol is a class with `rdfs:label` and
  `rdfs:subClassOf promolg:operator | promolg:function | promolg:delimiter`.
  It covers the alphabet (operators, functions, delimiters) but **not** the
  production rules — the grammar's syntax is not itself in RDF.
- **`promo_variables_equations.ttl`** — the schema: classes `promo:variable`,
  `promo:expression`, `promo:equation`, `promo:index`, `promo:blockIndex`,
  `promo:token`; properties `is_defined_by_expression`, `has_index`,
  `has_token`, `has_alias`, `for_domain`, `network`, `label`, `incidence_list`,
  `lhs`, `rhs`.
- **`var_equ_rdf.ttl`** — an instance graph. Variables carry `label`,
  `network`, `port_variable`, `type`, `index_structures`, `expression_list`.
  **Expressions are serialised as token sequences**, e.g.
  `expression_list_E_11 rdf:_0 qudt:EnergyInternal ; rdf:_1 promo:minus ;
  rdf:_2 qudt:Pressure ; rdf:_3 promo:Hadamard ; rdf:_4 qudt:Volume` —
  an ordered token list of IRIs, not an AST tree. External compilers re-parse
  the token stream; the AST is reconstructed, never stored.
- **Variables are referenced by IRI in the token stream** — `qudt:EnergyInternal`
  appears directly as a token, so the IRI is the expression-level identity.

Design consequence: the published grammar artifact is a *symbol vocabulary*.
If we want the full grammar (production rules, precedence) publishable too,
that is new vocabulary to design — but the existing pattern (token-sequence
expressions + symbol vocabulary) already supports external re-parsing.

### The publish–consume contract

The parser-related information in a published graph exists so an external
consumer can **interpret** the expression code — not to re-check it. All
structural checking (syntax, units, index consistency) happens **once, at
authoring time**, inside the equation editor backend. A published set is
therefore *trusted*: downstream consumers and generated numerical code carry
no checking logic. This was a root design goal of the project — it removes
validation overhead from generated model code entirely.

Consequences:

- **The backend checker is the gatekeeper.** Whatever passes the editor's
  checks is contractually consistent; the rigour of the var/expr framework
  (units, index structures, incidence lists) is what makes downstream trust
  possible.
- **A published set is self-contained.** Publishing a thermodynamics semantic
  set means publishing exactly: the variable definitions (IRI, label, units,
  index structures, network), the expression token lists, and the symbol
  vocabulary they reference. Nothing else is required to interpret it.
- **Open: domain rules as mathematics.** How to attach domain-specific
  constraints (e.g. thermodynamic consistency conditions) to a published set
  is unresolved. Candidate: express them as additional expressions/assertions
  in the same graph — they are mathematics, so the same token-sequence
  machinery should carry them. Needs a predicate to mark an expression as a
  *constraint* rather than a *definition*.

### Code generation objective

The target is **one true set of functions** — one per `var := expression` —
in multi-dimensional **tensor notation**, not distributed across model
modules as in legacy model-module software. The var/expr graph is the single
source of truth; the incidence lists and index structures on each variable
are exactly what a tensor-oriented code generator needs to emit indexed
array operations.

This reinforces the consistency condition: because codegen flattens
everything into one function set, any inconsistency that slips through the
editor surfaces as wrong numerics with no structural safety net downstream.

## Core var/expr store and rendered-graphics cache

### Decision: replace `variables_v8.json` with JSON-LD

The working var/expr file becomes a **JSON-LD named graph**. It is the
successor to `variables_v8.json` and the canonical holder of the var/expr
knowledge, not a separate export:

- **JSON for ergonomics** — the editor loads it into a dict/typed object,
  preserves order, and round-trips easily.
- **RDF for semantics** — it is a valid named graph with IRIs, so it can be
  published, merged, and linked to QUDT without conversion.
- **No dual-model drift** — the same graph is edited in memory, saved as
  JSON-LD, and published as Turtle. rdflib can load JSON-LD and serialise
  Turtle in one line.

Contents: variable resources, equation resources, index structures,
expression token lists, the language symbol vocabulary, and graph metadata
such as the next internal-ID counter (`promo:nextVariableID`).

### Rendered-graphics cache stays out of the RDF

LaTeX-rendered PNGs for variables and expressions are **derived artefacts**,
not semantic data. They are kept in a deterministic cache outside the graph:

```
cache/<graph-name>/
├── variables/
│   └── V_12.png
└── equations/
    └── E_4.png
```

Any ProMo module can locate a render by convention from the variable/equation
ID — no `png_file` path is stored in the RDF. If a graphic is missing, it is
regenerated from the `latex` alias already stored in the graph.

This keeps the published var/expr graphs portable and uncluttered by local
filesystem paths.

## Variable schema review

Comparison of the `variables_v8` JSON record against what `var_equ_rdf.ttl`
actually exports.

### JSON record fields → RDF disposition

| JSON field | Content | In old RDF export? | Proposed |
|---|---|---|---|
| `IRI` | external identity (`qudt:Entropy`) | as subject IRI | keep — subject = IRI |
| `label` | user symbol | `promo:label` | keep |
| `aliases` | `global_ID`, `internal_code`, `latex`, `matlab` | **missing** | add — latex needed for graphics regen |
| `units` | 8-exponent SI vector | **missing** | add — required by consistency condition |
| `index_structures` | list of `I_` IDs | `promo:index_structures` (rdf:_n, **emitted empty**) | fix — `rdf:List` of index IRIs |
| `equations` | `E_` records | `promo:expression_list` (rdf:_n token seq) | keep, switch to `rdf:List` |
| `network` | single network name | `promo:network` literal | keep, but as **network resource IRI** |
| `type` | state/frame/effort/transport/… | `promo:type` literal | keep — as class or controlled literal |
| `port_variable` | bool | `promo:port_variable` | keep |
| `doc` | string | `promo:doc` | keep — map to `rdfs:comment` |
| `tokens` | token types carried | **missing** | add |
| `memory` | memory-variable reference | **missing** | add — `promo:memory` → variable IRI |
| `imported` | bool | **missing** | add |
| `created`/`modified` | timestamps | **missing** | add — `dcterms:created`/`modified` |
| `compiled_lhs` | decorated lhs | missing | **drop** — derivable from label + indices |
| `png_file` | local path | missing | **drop** — graphics cache by convention |

### Bugs found in the old export

- **Subject minted from label** (`promo:hA`), not the internal ID — labels are
  only unique within a network, so this collides on merge. Subject should be
  the variable's IRI, else `promo:V_<id>`.
- **`promo:network` as stringified Python list** — one index serialises as
  `"['root', 'physical', ...]"`. Networks must be resources, not literals.
- **`index_structures` emitted empty** — `rdf:_0 promo:` with no value.
- **Schema file issues** (`promo_variables_equations.ttl`): `promo:token`
  declared twice; `rdfs:domain rdfs:index` typo (should be `promo:index`);
  `a rdfs:class`/`a rdf:property` wrong case; `promo:name` vs `promo:label`
  both declared; `promo:network` declared twice; `units`, `aliases`, `type`,
  `port_variable`, `doc` never declared in the schema.
- **`rdf:_n` container properties** without `a rdf:Seq` — and awkward in
  JSON-LD, where `@list` produces `rdf:List` (`first`/`rest`/`nil`). For a
  JSON-LD working format, `rdf:List` is the natural fit for token sequences
  and index structures.

### Decisions on the open points

- **Units: both.** Keep the 8-exponent SI vector as a literal (the checker's
  machine-readable form) *and* the variable's IRI link to
  `qudt:QuantityKind` (the semantic identity). The vector is what unit
  checking runs on; the IRI is what the world sees.
- **`type` vocabulary comes from the ProMo ontology.** Variable types
  (`state`, `frame`, `effort`, `transport`, `properties`, …) are ontology
  resources, not free literals — `promo:varType` points at an ontology class.
  The ontology itself is the next piece to build.
- **Published graphs reference the ontology, they don't include it.** The
  ProMo ontology is itself a published named graph — same pattern as QUDT.
  A domain var/expr set uses ontology IRIs (`promo:physical`, `promo:state`)
  and declares a dependency on an ontology version. Exception: if a domain
  set *extends* the ontology (new variable types, new networks), those
  extension resources live in the domain graph.
- **`tokens` — one predicate.** A token type implies its index
  (`mass` → `species`). `promo:tokens` links an index to the token type it
  carries, and a variable to the list of token types it carries. Same
  predicate, same range.
- **`memory` — dropped.** A half-implemented equation-level consistency
  attribute (all variables in an equation had to share one `memory` value;
  `None` everywhere in the data). Possibly a remnant of an old dynamic-systems
  idea. Not carried into the new schema — noted here in case the concept
  resurfaces when differential equations are designed.

### Equations and aliases

- **Equations are first-class resources**, not nested inside the variable
  record. `promo:Equation` carries `promo:lhs` (the defined variable),
  `promo:rhs` (`rdf:List` of token IRIs), `promo:incidenceList` (`rdf:List`
  of variable IRIs — a stored cache of the rhs dependencies), `promo:network`,
  `promo:eqType`, `rdfs:comment`. A variable's definitions are found via
  `?eq promo:lhs ?var` or a forward `promo:definedBy`.
- **Alternative definitions are real.** Data confirms variables with multiple
  equations (e.g. `V_113 T` has 2). `definedBy` is one-to-many — the var/expr
  graph is a *multi-way* graph where a variable may have several defining
  equations. Selection between alternatives is a modelling decision, not a
  schema constraint.
- **`eqType` is used.** Observed values: `generic` (802), `interface_link_equation`
  (43), plus `instantiate` in the operator layer. Keep it — as an ontology
  resource, like `varType`.
- **Aliases are structured resources.** `promo:hasAlias` →
  `[ promo:forLanguage promo:lang_latex ; promo:value "{S}" ]`. New codegen
  targets are new language individuals, not new predicates. Exception:
  `global_ID` is the internal ID — a direct literal (`promo:internalID`) or
  the subject's local name, not an alias.

## Parser assessment

TPG is a vendored 82 k-line LGPL parser generator. The grammar is small,
context-free, and LL-friendly — TPG is overkill and adds an unnecessary
dependency. The semantic layer (operator classes + `CompileSpace`) is what
matters and is parser-agnostic.

**Recommendation:** replace TPG with a hand-written recursive-descent parser in
`backend/equation/parser.py`. Port the operator classes and `CompileSpace` into
`backend/equation/ast.py`, `units.py`, and `compile_space.py`. Keep the
implementation in Python.

### The parser is dependent on the RDF core

The parser is not standalone — it is parameterised by the graph:

- **Symbol vocabulary in, tokens out.** The lexer maps surface symbols to
  `promolg:` classes from the published language vocabulary; the emitted
  token sequence is a list of IRIs (`qudt:`, `promo:`, `promolg:`).
- **Variable context in.** Identifier resolution needs the graph's variable
  table — `network!label` → IRI, plus units and index structures for the
  semantic checks that run during AST construction.
- **Checked graph out.** A successful parse produces a new equation resource
  (token list + incidence list + inferred units/indices) that is written back
  into the same JSON-LD graph.

So `parser.py` takes a `CompileSpace` built *from* the graph and returns
graph content. The grammar rules are code; everything the grammar talks
about lives in RDF.

## Browser architecture

Moving the frontend to the browser does **not** require rewriting the
operator-dependent part in TypeScript. The canonical parser, index/unit
checker, and variable-structure generator stay in Python behind FastAPI.

### Proposed split

```
backend/equation/
├── parser.py          # hand-written recursive-descent parser (replaces TPG)
├── ast.py             # operator classes (Add, ReduceProduct, …)
├── units.py           # SI unit vector and operations
├── compile_space.py   # variable/index resolution, temp naming
├── service.py         # FastAPI router: /api/equation/parse, /api/equation/check
└── codegen/           # later: LaTeX, Python, Matlab targets

apps/equation-editor/
└── src/               # React UI: expression input, variable palette,
                       # LaTeX preview, error display, equation list
```

### Frontend responsibilities

- Expression input with syntax highlighting and parenthesis matching.
- Variable palette populated from the ontology/modeller context.
- LaTeX preview of the parsed expression.
- Display of parser/semantic errors returned by the backend.
- Equation list and variable-definition management.

### Backend responsibilities

- Parse expression string → AST.
- Run index/unit checks during AST construction.
- Return normalized AST, inferred units, index structures, and errors.
- Serialize the AST to RDF for storage in the ontology/model graph.
- Later: code generation (Python, Matlab, LaTeX).

### Why keep the operator layer in Python

- The existing implementation already encodes the correct index/unit rules.
- The math is easier to verify and extend in Python than in TypeScript.
- The backend will need the same logic for validation and code generation
  anyway; duplicating it in the browser creates two sources of truth.
- A thin client keeps the browser app fast and avoids shipping the whole
  variable network to the client.

A lightweight client-side parser for syntax highlighting or bracket matching
can be added later, but the authoritative check remains the backend.

## Open questions

1. ~~`POWER` precedence~~ — resolved: `^` binds tighter than `*`, `:`, `.` and
   is right-associative.
2. What RDF vocabulary do we use for equations, variables, operators, and
   indices? (QUDT for units/dimensions; ProMo namespace for the rest.)
3. How does the browser editor obtain the variable/index context — from the
   ontology service, the modeller session, or a dedicated equation context?
4. Do we keep the `network!label` qualification syntax, or move to full IRIs
   in the UI with a friendlier display form?
5. Which code-generation targets are needed first (Python, Matlab, LaTeX)?
6. Internal ID scheme: keep `V_<int>`/`E_<int>` sequential counters or move to
   UUIDs? And is the ID derived from the IRI or stored separately?

## Next steps

1. Implement `backend/equation/parser.py` as a recursive-descent parser for the
   grammar above.
2. Port `Units`, `PhysicalVariable`, `Operator` subclasses, and `CompileSpace`
   into `backend/equation/`.
3. Add a test suite that replays expressions from the old test files through
   the new parser and compares ASTs and error cases.
4. Expose `POST /api/equation/parse` and `POST /api/equation/check` in
   `backend/equation/service.py`.
5. Scaffold `apps/equation-editor/` with a minimal React UI that calls the
   backend.
