# ProMo math-language ontology comparison

**Status:** design investigation, 2026-09-27. No implementation decision.

## 1. Question

Would ProMo become simpler and more robust if equations were stored as an
IRI-bound representation, while retaining the current ProMo expression language
as the user-facing entry and editing language? How much of the math language
should be ontologised, and can that ontology also remain a distributable
language definition for consumers of the variable/expression ontology?

The primary criterion is a net advantage for the whole system: editing,
checking, refactoring, persistence, distribution, code generation and
versioning. Ontologising something is not by itself sufficient justification.
The governing constraint is to keep both the language and its implementation at
a **very low level of complexity**. Prefer the smallest design that satisfies a
demonstrated need; reject speculative abstraction, extension machinery and
metadata whose benefit is only hypothetical.

## 2. Sources compared

Historical sources:

- CAM10 `processes_001/variableExpression.trig`, named graph `promolg:`.
- CAM10 `processes_HAP_structure_testing/variableExpression.trig`, especially
  the `promo:expression_list_E_*` resources.

Current ProMo14 sources:

- `backend/equation/parser.py` — concrete grammar and parser.
- `backend/equation/symbols.py` — language symbol table.
- `backend/equation/syntax.py` — unbound syntax tree.
- `backend/equation/checker.py` — semantic checking and checked tree.
- `backend/equation/compile_space.py` — IRI-keyed variable/index resolution.
- `backend/equation/codegen.py` — MATLAB, Python, Julia and LaTeX renderers.
- RDF equation persistence — textual `promo:rhs`, IRI `promo:lhs`, and cached
  incidence/LaTeX.

## 3. Historical design

### 3.1 Language graph

The CAM10 `promolg:` named graph gives IRIs to three kinds of language item:

- operators, including `plus`, `minus`, `power`, `Hadamard`, `expandProduct`,
  `reduceProduct`, `reducteSum`, `Instantiate`, `Integral`, `Product`,
  `ParDiff`, `TotalDiff`, `MakeIndex`, `max`, `min` and `in`;
- functions, including `Root`, `abs`, `neg`, `inv`, `sign`, `diffSpace`,
  `left`, `right`, exponential/logarithmic and trigonometric functions;
- delimiters, including round, square and wiggled brackets, comma, `::`, `&`,
  `|` and `_`.

Each item has an IRI, a surface spelling in `rdfs:label`, and a broad
`rdfs:subClassOf` classification. The graph is primarily a vocabulary/catalogue:
it does not record arity, argument roles, precedence, associativity, unit rules,
index rules or a language version.

### 3.2 IRI token lists

The structure-testing file additionally represents equations as ordered RDF
containers. A list interleaves IRIs for variables, indices, operators,
functions and delimiters. For example, the lexical form of
`ParDiff(U, n)` is represented by six members:

1. `promolg:ParDiff`;
2. `promolg:left_round`;
3. the IRI for `U`;
4. `promolg:comma`;
5. the IRI for `n`;
6. `promolg:right_round`.

This is an IRI-bound **lexical token stream**, not a semantic expression tree.
It preserves concrete syntax and can regenerate entered source closely, but a
consumer must still parse it to discover expression structure and meaning.

### 3.3 Historical strengths

- Variable and index references are no longer tied to mutable labels.
- The language vocabulary is independently distributable.
- A consumer can discover the available words and punctuation in RDF.
- Ordered tokens can reproduce the familiar ProMo source language.
- Operators, functions and delimiters share one uniform reference mechanism.

### 3.4 Historical limitations

- The expression must be parsed again after loading.
- Precedence and associativity are implicit in external parser knowledge.
- Parentheses and commas carry syntax rather than mathematical meaning.
- Redundant grouping creates different stored forms for the same expression.
- The RDF vocabulary does not fully specify checker semantics.
- `rdf:_00`, `rdf:_01`, ... form an RDF container convention rather than a
  conventional `rdf:first`/`rdf:rest` list.
- The structure-testing export appears to collapse several variable references
  to domain-level `#V` IRIs; it proves the representation idea but should not
  be treated as a trustworthy migration source.
- There are historical vocabulary details to correct, such as
  `promolg:reducteSum`.

## 4. Current ProMo14 design

### 4.1 Source and parsing

Users enter the established ProMo expression syntax. The parser produces an
unbound syntax tree. Variable and index nodes initially retain source names;
resolution happens during checking against an IRI-keyed `CompileSpace`.

The current parser already anticipates loading its symbol table from a
published `promolg:` graph. The built-in Python table is explicitly a bootstrap
implementation.

### 4.2 Syntax constructs

The current syntax tree distinguishes:

- `Var` — local or `domain!label` reference;
- `Group` — explicit source parentheses retained for round-tripping;
- `Add` — plus or minus;
- `Expand` — disjoint-index expansion, source `:`;
- `Hadamard` — element-wise product, source `.`;
- `Reduce` — indexed contraction, source `*`, optionally with explicit index;
- `Power`;
- `Instantiate` — whole-RHS declaration `Instantiate(proto)`;
- `Integral`;
- `Product` — reduction product over an index;
- `Root` — implicit solve-for expression;
- `MaxMin`;
- `TotalDiff` and `ParDiff`;
- `ReduceSum`;
- `UFunc` — registered unary function;
- `Call` — registered generic/user function.

The parser knows concrete delimiters and grammar. The symbol table knows infix
precedence and associativity plus unary-function unit-rule categories.

### 4.3 Checked representation

The checker wraps every syntax node in a `Checked` node containing derived:

- units;
- ordered index IRIs;
- incidence as variable IRIs;
- checked children;
- temporary labels.

It also applies construct-specific semantics. For example, expansion requires
disjoint index sets, contraction removes a shared index, addition requires
matching units and ordered index structures, and `Instantiate` has empty value
incidence and inherits its prototype's structure.

The checked tree is already the common input to MATLAB, Python, Julia and LaTeX
rendering. Target generators are therefore renderers over a shared semantic
representation, although their tensor and runtime conventions remain genuinely
target-specific.

### 4.4 Current persistence weakness

The RHS is persisted as source text. Its variable references therefore depend
on labels and domain-name qualifiers. The LHS and cached incidence already use
IRIs. A rename or domain move can consequently require textual RHS rewriting,
reparsing and checking to prove that every reference retains its original
binding.

## 5. Vocabulary mapping

| Historical `promolg:` | Current construct | State |
|---|---|---|
| `plus` | `Add("+")` | retained |
| `minus` | `Add("-")` | retained |
| `power` | `Power` | retained |
| `expandProduct` | `Expand` | retained |
| `Hadamard` | `Hadamard` | retained |
| `reduceProduct` | `Reduce` | retained, now optional explicit reduction index |
| `reducteSum` | `ReduceSum` | retained; historical spelling should not be canonical |
| `Product` | `Product` | retained |
| `Integral` | `Integral` | retained |
| `Root` | `Root` | retained |
| `TotalDiff` | `TotalDiff` | retained |
| `ParDiff` | `ParDiff` | retained |
| `Instantiate` | `Instantiate` | retained but semantics changed to whole-RHS `Instantiate(proto)` |
| `MakeIndex` | none | deliberately removed; indices are ontology declarations |
| `max`, `min` | `MaxMin` | retained |
| historical unary functions | `UFunc` | substantially retained |
| none | `Call` | current extension for registered/user functions |
| delimiters | lexer/parser punctuation | retained as concrete syntax, not current semantic nodes |
| `in` | integral grammar token | retained as syntax keyword |
| `left_wiggled`, `right_wiggled`, `ampersand`, `or`, `underline` | none in current grammar | not currently part of accepted source syntax |

Two current inconsistencies need separate review rather than accidental
ontologisation:

- codegen contains a target mapping for `trans`, but `trans` is not registered
  in the current default parser symbol table;
- generic `Call` checking is provisional and currently returns dimensionless
  units with the union of argument indices.

## 6. Candidate canonical representations

### 6.1 Keep source text canonical

This is the current design.

**Advantages:** smallest change; exact entered text is retained; parser remains
the single structural authority.

**Costs:** persistent references remain name-dependent; refactoring requires
text mutation and rebinding checks; dependency scans require parsing or token
matching.

### 6.2 Historical IRI token stream

Persist an ordered list of variable/index/operator/function/delimiter IRIs.

**Advantages:** references are rename-safe; closely reproduces source; directly
uses the distributable language vocabulary.

**Costs:** still requires parsing; persists punctuation; precedence remains an
external contract; ordered RDF token lists are verbose; source grouping and
semantic structure remain mixed.

### 6.3 IRI-bound semantic tree

Persist expression structure with variable/index/function/operator IRIs and
ordered argument roles. Concrete punctuation is regenerated by a ProMo-source
renderer.

**Advantages:** rename-safe; no reparsing merely to discover structure;
dependencies are exact; every renderer consumes the same bound structure;
operator meaning is explicit; validation can reject malformed structures.

**Costs:** exact whitespace and redundant grouping are not naturally retained;
a versioned tree schema is needed; editing requires rendering source and parsing
the edited result; migration must bind every existing textual reference.

### 6.4 Hybrid

Persist the IRI-bound semantic tree as authoritative and optionally retain the
last entered source as a non-authoritative editing/display cache.

This separates stable meaning from author-owned presentation. The cache can be
discarded or regenerated after a rename. It should never be used to determine
binding when the semantic tree is present.

## 7. What should be ontologised

### 7.1 Strong candidates

These concepts require stable identities for distribution and persisted
semantic expressions:

- semantic operators and expression constructors;
- built-in mathematical functions;
- variable, index and function reference kinds;
- ordered argument roles, such as body, left/right operand, reduction index,
  integration variable and bounds;
- arity or argument-shape constraints;
- source spelling;
- precedence and associativity for ProMo-source rendering/parsing;
- language/version membership;
- deprecation and replacement relationships;
- broad semantic categories such as arithmetic, index operation, calculus,
  declaration and solve operation.

### 7.2 Useful descriptive properties

The language ontology may document:

- unit behaviour categories;
- index transformation categories;
- target-language spellings or runtime operation identities;
- human documentation and examples.

The authoritative implementation of nontrivial unit/index rules should remain
trusted checker code initially. Encoding executable semantics declaratively is
a separate design problem and is not required for IRI-bound persistence.

### 7.3 Concrete syntax

Delimiter **roles** and source spellings can be ontologised as part of a
language/syntax profile. Individual delimiter occurrences need not be persisted
in a semantic tree.

For example, the language definition may say that its call syntax uses `(`,
`,` and `)`, while an application node stores only the called operation and its
ordered arguments. This preserves the historical documentation/distribution
purpose without confusing punctuation with mathematical meaning.

### 7.4 What should not be canonical ontology semantics

- Python AST class names;
- target-language variable names;
- generated temporary names;
- cached units, incidence or LaTeX;
- whitespace and comments;
- redundant source grouping, unless exact author formatting is explicitly a
  product requirement.

## 8. Expected system effects

### 8.1 Renaming and domain refactoring

Variable, index and domain labels become render-time concerns. Their IRIs remain
stable, so stored equations need no mutation. A domain move may still be
semantically invalid because visibility or placement rules change, but it
becomes validation of an unchanged binding rather than textual rebinding.

### 8.2 Deletion and usage guards

References can be followed structurally by IRI. Regex scanning over RHS strings
is unnecessary when all equations use canonical semantic storage.

### 8.3 Code generation

MATLAB, Python, Julia and LaTeX remain renderers. Their target-specific tensor
operations do not disappear, but name resolution and source rebinding can be
removed from their input path. A ProMo-source renderer becomes one additional
target.

### 8.4 Distribution

A consumer needs:

1. the variable/expression ontology;
2. the pinned ProMo math-language ontology/version;
3. the expression-tree schema;
4. implementations of the semantics it intends to check or execute.

The ontology is the distributable declaration. Trusted implementation code
binds declared implementation keys to parser constructors, checker rules and
renderers. Loading an ontology term without its required implementation must
produce a capability error, not a partially working language.

### 8.5 Versioning

An equation artefact must identify the language version under which its stored
expression is interpreted. Stable operator IRIs should not silently change
semantics. A changed meaning requires a new term or versioned language graph,
with an explicit migration relationship.

## 9. Provisional direction

The comparison supports further investigation of an **IRI-bound semantic tree**,
not direct adoption of the historical token-list representation.

The old work is valuable because it establishes:

- the language as an independently distributable ontology;
- stable identities for operators, functions and syntax concepts;
- IRI-bound variable and index references inside expressions.

The current implementation contributes:

- an explicit AST;
- a separate semantic checking pass;
- IRI-keyed compile records;
- one checked representation feeding all target renderers.

A likely clean combination is:

```text
ProMo source
    -> parse
unbound syntax tree
    -> resolve/check against pinned artefacts
IRI-bound semantic expression
    -> persist
    -> render to ProMo source / LaTeX / MATLAB / Python / Julia
```

This remains provisional. In particular, the canonical tree must not simply be
the current Python dataclass serialization: it needs an implementation-neutral,
versioned contract tied to the language ontology.

## 10. Extensibility requirement

A wider use of ProMo may expose mathematical constructs that its present
application domains have not required. If such a gap is demonstrated, adding
the necessary construct must not force a redesign of the
parser/checker/persistence/rendering architecture. This is a maintainability
requirement, not a requirement to build a general plugin framework now.

The implementation should add only the smallest extension seam needed by the
current language. More elaborate registries, capability systems or extension
packaging should be introduced only when a concrete extension or external
consumer proves the need. Extensibility must reduce future change cost without
increasing present complexity disproportionately.

### 10.1 Extension categories

Extensions have different implementation costs, but the default policy is **not
to extend the core language**. Its compact set of generic operations is a design
strength. An addition is justified only by a demonstrated mathematical gap that
cannot be expressed cleanly with the existing language.

The following categories help evaluate a proposal; they are not an invitation
to populate each category:

1. **New spelling or alias for an existing semantic operation.** Normally
   reject. Syntactic sugar and convenience operators risk uncontrolled
   multiplicity without adding mathematical capability.
2. **External function using an existing application form.** Potentially admit
   under a tightly constrained function contract. ProMo has historically
   limited external operations to functions, and even these have not yet been
   needed in practice.
3. **New semantic operation fitting an existing grammar form.** Consider only
   after proving that composition of existing operations cannot express the
   required mathematics clearly.
4. **New syntax form or precedence level.** An exceptional language-version
   change requiring evidence of an otherwise unsolvable gap.
5. **New mathematical semantics unsupported by a target.** The language may
   represent it only when the core-language decision has first been made;
   publication/code generation must then report a precise missing capability.

Every accepted extension must be non-interfering: existing expressions retain
their parse, bindings, semantics and rendering. Extension namespaces and
profiles must not silently alter the compact core language.

### 10.2 Language registry

The current `SymbolTable` should remain the minimal runtime language registry
unless a demonstrated extension requires more. For each current operation it
may eventually expose only the metadata needed by actual consumers:

- stable operation IRI and language-version membership;
- source spelling and syntax form;
- arity and ordered argument roles;
- precedence and associativity where applicable;
- semantic/checker implementation key;
- unit and index rule category or implementation key;
- renderer implementation key or declared target mapping;
- documentation, examples, deprecation and replacement terms.

The ontology is the distributable declaration. Trusted implementation code
binds declared implementation keys to parser constructors, checker rules and
renderers. Loading an ontology term without its required implementation must
produce a capability error, not a partially working language.

### 10.3 Component contracts

The implementation should avoid both scattered conditionals and a speculative
plugin architecture. Small explicit dispatch tables are appropriate when they
make an existing extension point clearer; central `isinstance` dispatch may
remain where it is simpler and the operation set is closed. Persistence must
store operation IRIs rather than Python class names, but runtime implementation
structure should otherwise remain as simple as possible.

### 10.4 Capability validation

At startup or when a language artefact is selected, ProMo should validate the
whole enabled language version:

```text
language terms
    -> parse bindings present
    -> semantic/checker bindings present
    -> ProMo-source rendering present
    -> requested target-renderer bindings present
```

A target may advertise partial support, but unsupported operations must be
listed before generation. This lets a distributed ontology be understood and
documented even where a consumer cannot execute every operation.

### 10.5 Versioning and compatibility

Adding an operation without changing existing meanings is a backward-compatible
language extension. Changing precedence, argument roles, checker semantics or
the meaning of an existing operation is a language-version change. Published
equation artefacts must remain pinned to the language version under which they
were checked.

Old operation IRIs must not silently acquire new semantics. Replacement terms
and migrations should be explicit. A consumer can then distinguish:

- language version understood;
- expression operation unsupported;
- renderer target unsupported;
- expression requiring migration.

### 10.6 Extension acceptance test

Every new semantic operation should arrive as one coherent extension package
containing:

- ontology term and metadata;
- parser/source-renderer round-trip cases;
- positive and negative semantic-check cases;
- persistence round-trip cases using the operation IRI;
- renderer cases for each claimed target;
- an explicit unsupported-capability result for targets not implemented;
- compatibility tests proving existing expressions retain their bindings and
  meaning.

The architectural success criterion is that an exceptional, justified operation
requires new registry entries and focused implementations/tests, with no
persistence schema redesign and no unrelated parser, checker or renderer
restructuring. Architectural ease of addition must not weaken the governance
threshold for admitting an addition.

### 10.7 Agreed expression and modelling principles

The canonical representation performs no algebra. It preserves authored operand
and argument order, does not simplify, does not reorder commutative operations,
and does not identify algebraically equivalent trees. Semantically obsolete
brackets are omitted from the canonical tree; the user's exact grouping and
formatting may remain in a non-authoritative source representation. The goal is
one deterministic serialization for one parsed and bound tree, not one normal
form for all equivalent mathematics.

Syntax validation and mathematical checking remain part of the normal expression
entry operation. The parser rejects malformed source, such as an `Integral`
without its required body or bounds. The checker immediately applies units,
index structures, incidence and construct-specific mathematical constraints;
this early feedback is a core property of ProMo, not an optional later step.

SHACL would serve a different boundary: validating persisted or imported RDF
expression graphs independently of the source parser. It can also document the
data model and support conforming interface generation. It is useful if semantic
expressions become exchangeable RDF written by more than one implementation,
but is not required merely to duplicate checks already guaranteed on ProMo's
source-entry path. The first prototype may use ordinary structural validators;
SHACL should be adopted when the RDF expression shape and interoperability need
justify it.

External operations remain restricted to functions rather than arbitrary new
operators. Before enabling them, ProMo needs a constrained contract for identity,
arity, argument roles, unit/index semantics and implementations. Arbitrary
function behavior or executable ontology declarations are not allowed.

Expressions should be short and readable. Long expressions are discouraged not
only for computational limits but because they hide modelling structure. Authors
should introduce meaningful intermediate variables and short equations; machines
can perform substitution when required. This principle is part of the modelling
concept behind ProMo and should influence editor guidance, documentation and
review, without imposing a small hard language limit on otherwise valid models.

## 11. Settled design choices

### 11.1 Canonical expression representation

Persist a semantic expression as an operation IRI with one ordered argument
list. Argument roles and cardinalities are declared by the operation definition
in the language ontology. This keeps the expression schema small and stable;
operation-specific predicates are not required.

References in the argument list are IRIs. For example, `ReduceProduct` has
left operand, right operand and an optional reduction-index reference in that
order. The optional reduction index is a generic property of `*`: it is required
whenever the two operands have more than one common index.

### 11.2 Entered source

Store the accepted source text alongside the canonical semantic expression. It
is non-authoritative but preserves the user's formulation and formatting. The
semantic IRI tree determines bindings and meaning. When a referenced display
name changes, regenerate the affected source from the semantic tree rather than
textually rebinding it.

### 11.3 Canonical semantic names

The approved core identities are:

| Source form | Canonical operation name |
|---|---|
| `+` | `Add` |
| `-` | `Subtract` |
| `^` | `Power` |
| `:` | `ExpandProduct` |
| `.` | `IndexPreservingProduct` |
| `*` | `ReduceProduct` |
| `Product(expr, i)` | `ProductOverIndex` |
| `reduceSum(expr, i)` | `SumOverIndex` |
| `Integral(...)` | `DefiniteIntegral` |
| `TotalDiff(x, y)` | `TotalDerivative` |
| `ParDiff(x, y)` | `PartialDerivative` |
| `Root(expr)` | `SolveRoot` |
| `Instantiate(proto)` | `Instantiate` |

These are semantic ontology names; retaining an established compact source
spelling does not require the ontology IRI to repeat that spelling.

`Instantiate` is classified as a declaration rather than an algebraic
operation. It records that the declared variable is a parameter slot requiring
instantiation by the downstream modelling, simulation or code-generation tool.

### 11.4 Conservative unary-function rules

`inv` remains provisionally scalar. Matrix and tensor inverses are not inferred
from it; their index and unit semantics would require separate demonstrated
needs.

`sqrt` accepts a dimensioned argument only when every SI exponent is even and
returns the halved integer exponents. Odd exponents are rejected with a specific
user-facing explanation. Fractional unit exponents are not introduced.

### 11.5 Differential space is an index concept

`diffSpace` is not an expression operation and there is no canonical
`DifferentialSpace(expr)` node. Differential space is represented by an index
IRI used directly in a variable's fixed index structure. In the controller
example, `x` carries integral index `x`, `dxdt` carries differential index `dx`,
and `A` carries `[dx,x]`; `ReduceProduct` reduces `x` and leaves `dx`.

The ontology must describe differential indices and, where needed, their
relationship to the corresponding integral indices. Equation checking then uses
the declared index IRIs normally; it does not transform an expression from one
space to another.

The current parser/checker registration of `diffSpace(expr)` as a unary function
and its code-generation mapping to `gradient` do not represent this design.
They are implementation/historical artefacts to remove or migrate during the
language audit, not capabilities to reproduce in the canonical ontology.

### 11.6 ReduceProduct, ExpandProduct and IndexPreservingProduct

The names describe the effect on index structure: `ExpandProduct` expands it,
`IndexPreservingProduct` does not eliminate common indices, and `ReduceProduct`
reduces it by contracting one common index. `ReduceProduct` is therefore an
intentional counterpart to `ExpandProduct`, not merely an implementation term.

## 12. Remaining questions

The principal representation choices are settled. The remaining questions are
implementation details to resolve during the non-persisting prototype:

1. Define the minimal RDF classes/properties for operation application, ordered
   arguments, variable references and index references.
2. Define how differential indices are classified and, if required, the
   ontology predicate relating a differential index to its integral counterpart.
3. Audit each existing unary function against its checker and renderer behavior;
   remove `diffSpace` and defer functions whose semantics cannot be stated
   precisely.
4. Decide whether SHACL adds value after the RDF expression shape exists and an
   external producer or interface-generation use case is concrete.

None of these requires expanding the core mathematical language.
