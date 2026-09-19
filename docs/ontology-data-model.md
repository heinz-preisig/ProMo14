# Ontology Data Model for the Equation Editor

This document records the old ProMo13 structure that the equation editor
consumes, the defects in the current `var_equ_rdf.ttl` export, and the
ProMo14 RDF topology that the graph-store provider will implement.  The goal
is a single, stable contract with the equation editor:
:ref:`backend/equation/context.py`.

> **Scope note (2026-09-13):** This document covers the var/expr RDF\nschema (variables, indices, equations, tokens, domain tree) that is\nshared between the Ontology Editor and Equation Editor.  It does **not**\nyet cover the newer ontology concepts: classification axes, scale\ndimensions, entity types, connection rules, or abstract graphical\nsymbols.  These are defined in\n`docs/ontology-design-discussion-2026-09-11.md` (§8–9, §13, §19) and\nwill be added to the RDF schema once the design stabilises.

## 1. What the old ProMo13 code stores

### 1.1 Variable record (`variables_v8.json`)

Variables have three names (see "Three names" note below).  The JSON is
keyed by the old internal ID, but the equation editor uses the IRI as the
stable key.  Grouped by purpose, the fields are:

```json
{
  "V_1": {
    "IRI": "iri_V1",
    "label": "label_V1",
    "internal_id": "V_1",
    "aliases": {"internal_code": "V_1", "latex": "V_1"},

    "network": "macroscopic",
    "variable_class": "state",
    "port_variable": false,

    "doc": "doc_V1",
    "units": [0, 0, 0, 1, -3, 0, 0, 0],
    "tokens": [],

    "index_structures": ["I_1", "I_2"],

    "equations": {
      "E_1": {
        "lhs": "iri_V1",
        "rhs": {"global_ID": " O_1 D_0 V_2 D_7 V_3", "latex": ""},
        "equation_class": "generic",
        "network": "macroscopic",
        "incidence_list": [],
        "doc": "",
        "created": "...",
        "modified": "..."
      }
    },
    "compiled_lhs": {},
    "memory": null,

    "created": "...",
    "modified": "..."
  }
}
```

### Three names, three jobs

Every variable, index, token, and equation has three names at different
boundaries:

- **IRI** — the identity. Graph key, incidence lists, `CompileSpace`
  dictionaries.  Stable across versions.
- **label** — the surface name the user types and sees (`rho`, `T`,
  `chemPot`).
- **internal_id** (`V_1`, `I_3`, `E_1`) — the *code name*.  Appears in the
  `global_ID` token stream and is what the numerical code generator emits as
  the variable/index identifier.

The checker only ever needs the IRI; `internal_id` and `label` are consulted
at the emit boundary (token stream, codegen, `internal_code` alias) or at
parse time (label → IRI resolution).

### Field groups

#### Identity & naming
- `IRI` — stable graph key.
- `label` — user-facing surface name.
- `internal_id` — code/token name (`V_1`).
- `aliases` — language-specific surface names.  This is an **extensible
  map** from a target-language name to the string used in that language.
  Well-known keys are:
  - `internal_code` — short code used in the expression language and
    generated code (e.g. index `N`).
  - `latex` — the LaTeX *symbol* for the variable/index (e.g. `\rho`).
    **Generated when the variable is defined** — the variable editor
    auto-derives it from the label (Greek letters, subscripts, …) and the
    user may override it.  The equation editor only *reads* it to assemble
    full equation LaTeX and generate pictures.
  - other keys (e.g. `matlab`, `python`, `modelica`) can be added by
    user-defined templates or external compilers.

#### Domain / location
- `network` — the **variable definition network**.  The user must first
  select a domain from the ontology's domain tree; the variable is then
  defined in that network.  It is not a free-form string.
- `variable_class` — variable class chosen from those valid for the
  selected domain (`state`, `effort`, `transport`, `frame`, `network`, ...).
  In the old JSON this field is called `type`; in the Python dataclass it is
  `Variable.type` because `class` is a reserved keyword.  The RDF predicate
  should be `promo:variable_class`.
- `port_variable` — `true` for the fundamental quantities and constants
  that **are the foundation** of the var/expr graph.  Port variables are
  declared with a name, units, and index structure, but have **no defining
  RHS expression**.
- `imported` — *ontology-editor metadata*: marks a variable brought in from
  another ontology (e.g. a base physical ontology imported into a
  domain-specific one).  **Not consumed by the equation editor** — kept on
  the ontology record for versioning/editability, not part of the
  `EquationContext` contract.

#### Semantics
- `doc` — human description.
- `units` — 8-integer SI exponent vector.
- `tokens` — token types this variable may carry (e.g. `mass`, `species`,
  `signal`).  Refinement (e.g. `mass` → `species A/B/C`) is handled by the
  token ontology hierarchy (`promo:Token` with `promo:parent`), not by the
  variable record.  The checker only uses `tokens` for validation; the actual
  indexation comes from `index_structures`.

#### Index structure
- `index_structures` — an **ordered** list of **index IRIs** the variable is
  defined over.  The sequence is fixed and consistent across all variable
  definitions — this is what makes index compatibility a cheap list
  comparison in the checker.  In the old JSON these are `I_1`, `I_2`
  internal IDs; the loader maps them to index IRIs.

#### Equations
- `equations` — dict `E_N` → equation record.  A variable may have several
  equations, one per expression network.  Each equation has its own
  `network` — the **expression definition network** — which is essential for
  `CompileSpace.accessible_networks`.
  Equation record fields:
  - `lhs` — the parent variable (IRI reference).  In the old JSON this is
    an object with `global_ID` / `latex`; that is a duplication of the
    variable's identity and latex alias.  The new model stores the IRI
    only; latex is generated from the variable's `latex` alias.
  - `rhs` — the expression as a token sequence and its rendered LaTeX:
    - `global_ID` — the token stream / internal form (`O_1 D_0 V_2 …`).
    - `latex` — **generated** from the AST and the variables' `latex`
      aliases, then stored as a cache.
    For `equation_class: "empirical"` / `"user_function"` the `rhs` is a
    **function reference** (IRI to the implementation), not a token stream.
  - `equation_class` — equation classification: `generic`, `instantiate`,
    `balance`, `empirical`, `user_function`, …  In the old JSON this field
    is called `type`.  `empirical` / `user_function` equations are external
    implementations (equations of state, correlations) — the ontology
    editor registers their signature but does not parse their body.
  - `network` — expression definition network.
  - `incidence_list` — list of variables used in the RHS, **derived by
    walking the AST** and cached for the `Root` deep-incidence check.
    Safe to omit and recompute.
  - `doc` — human description.
  - `created`, `modified` — timestamps.
- `compiled_lhs` — cached **LHS metadata for code generation**.  It is the
  precompiled assignment target for this variable, typically expressed in
  terms of the variable's `internal_id` or `internal_code` alias.  The
  equation editor does not consume it; it is produced by the code generator
  and stored for reuse.
- `memory` — *codegen/runtime metadata*: records whether the variable's
  value comes from a **node or an arc** in the model graph.  Not consumed by
  the equation editor; kept on the ontology record for code generation.
  Arcs themselves are **model-level** (flowsheet connections), not part of
  the core ontology — see `ontology-editor-design.md`.

#### Audit
- `created`, `modified` — timestamps.

### 1.2 Index record (legacy)

Old indices are stored in a separate ``indices`` block inside the ontology.
Grouped by purpose, a typical index carries:

#### Identity & naming
- `IRI` — stable graph key.
- `label` — surface name (e.g. `species`).
- `short_name` — optional single-letter (or short) display label used in the
  equation editor UI and in generated LaTeX subscripts (e.g. `N` for `node`,
  `C` for `species_conversion`).  Distinct from `internal_code`, which names the
  index in the token stream / generated code.
- `aliases` — language-specific surface names, e.g.
  `{"internal_code": "N", "latex": "N"}`.  The `internal_code` alias is the
  index's short code name in the token stream.

#### Domain
- `network` — single network or list of networks where the index is valid.
- `index_class` — `"index"` or `"block_index"`.  In the old JSON this field
  is called `type`; renamed for consistency with `variable_class` /
  `equation_class`.

#### Token
- `token` — the token type this index carries (e.g. `promo:species`).

Example index records:

```json
{
  "I_1": {
    "IRI": "iri_I1",
    "label": "species",
    "short_name": "S",
    "aliases": {"internal_code": "N", "latex": "N"},
    "network": ["physical", "macroscopic"],
    "index_class": "index",
    "token": "promo:species"
  },
  "I_dx": {
    "IRI": "iri_Idx",
    "label": "differential_space",
    "aliases": {"internal_code": "dx", "latex": "d"},
    "network": "physical",
    "index_class": "index",
    "token": "promo:differential_space"
  }
}
```

`differential_space` is an index like any other — it is what `TotalDiff`
differentiates over, and its `internal_code` (`dx`) is what appears in the
token stream.

### 1.3 Ontology domain tree (`ontology.json` / `ontology_container.ontology_tree`)

The domain tree is a rooted hierarchy of **networks** (also called
**domains**).  Each network represents a physical domain or modelling
level: `root`, `physical`, `macroscopic`, `microscopic`, `reactions`,
`thermo`, `liquid`, `gas`, etc.  In the new RDF model each network is a
`promo:Network` resource with a `promo:parent` edge.

A network record carries:

- `IRI` — stable graph key, e.g. `promo:macroscopic`.
- `label` — human name.
- `internal_id` — short code name.
- `parent` — zero or more parent network IRIs.
- `aliases` — e.g. `{"internal_code": "macroscopic"}`.

The tree is used to compute **accessible networks** for an expression.
Given the expression network `E`, a variable defined in network `D` is
visible if and only if `E` is a descendant of `D` (including `D` itself):

```
accessible_networks(E) = { D | E ∈ descendants(D) ∪ {D} }
```

In ProMo13 the same dictionary is called `heirs_network_dictionary`.  It
maps a network to **all its descendants** (including itself); the equation
editor then checks whether `E` is in that set for a candidate definition
network `D`.

Example tree:

```
root
└── physical
    ├── macroscopic
    ├── microscopic
    │   └── reactions
    ├── thermo
    │   ├── liquid
    │   └── gas
    └── energy
```

When editing an equation in `macroscopic`, variables defined in `physical`
or `macroscopic` are visible; variables defined in `thermo` are not
(unless explicitly qualified with `network!label`).

### 1.4 Tokens (`resources.py`)

Tokens are the operators, delimiters, functions, and typed-token markers
used in the equation surface syntax and in the internal token stream.  Each
token has:

- `IRI` — stable graph key, e.g. `promo:Hadamard` or `promolg:TotalDiff`.
- `label` — surface name, e.g. `Hadamard` or `d`.
- `internal_id` or `internal_code` — short code, e.g. `.` for Hadamard,
  `D_7` for `TotalDiff`.
- `global_id` — the token used in the internal stream, e.g. `O_42`.
- `token_type` — `operator`, `delimiter`, `function`, or `typed_token`.
- `parent` (optional) — parent `promo:Token` IRI for the token hierarchy;
  refinements live in the hierarchy, not on the variable record.
- `network` (optional) — the domain where this token is valid.

Token record example:

```json
{
  "O_42": {
    "IRI": "promo:Hadamard",
    "label": "Hadamard",
    "internal_code": ".",
    "global_id": "O_42",
    "token_type": "operator",
    "network": "root"
  },
  "D_7": {
    "IRI": "promolg:TotalDiff",
    "label": "TotalDiff",
    "internal_code": "d",
    "global_id": "D_7",
    "token_type": "function",
    "network": "root"
  }
}
```

The parser does not need the old token table at runtime, but the
**export/import** path does: it must map `global_id` strings ↔ surface
strings and IRIs.

### 1.5 Entities (`entities.json`)

Entities hold a **bipartite variable–equation graph** and per-variable
state/attribute information.  An entity is essentially the link between the
ontology (variables and equations) and a specific model that uses them.

Content:

- `variable_states` — a dictionary keyed by variable internal ID; each entry
  stores state information used by the modeller (e.g. which variables are
  calculated, prescribed, or port variables).
- `graph` — an incidence graph: variable `V_i` → equation `E_j` edges.
  This is used for the `Root` operator's deep-incidence check: `Root(expr)`
  must resolve to the LHS variable, and the solver needs to know that the
  LHS and all variables in the RHS are part of the same equation closure.

The graph is built from the per-equation `incidence_list` fields.  In
ProMo14 it may be a **model-level** artifact (computed when a model is
assembled) rather than an ontology-level record, because the same variable
and equation set can be reused across different models.  For now it is kept
in `entities.json` for backward compatibility.

## 2. What the ProMo13 TTL export (`var_equ_rdf.ttl`) actually contains

### 2.1 Variable block

```turtle
qudt:EnergyInternal a promo:variable ;
    promo:doc "fundamental state -- internal energy" ;
    promo:expression_list promo:expression_list_V_108 ;
    promo:index_structures promo:index_structures_V_108 ;
    promo:label "U" ;
    promo:network "physical" ;
    promo:port_variable true ;
    promo:type "state" .
```

Note what is **missing** from this export:

- `promo:units`
- `promo:aliases`
- `promo:tokens`
- `promo:internal_id`
- `promo:imported`
- `promo:compiled_lhs`
- `promo:memory`
- `promo:created`
- `promo:modified`
- `promo:lhs` / `promo:rhs` / per-equation `network`

The expression list is linked through `expression_list_V_N` but only the
RHS token stream is present.

### 2.2 Index block

Indices are exported as bare IRIs with `promo:type "index"`:

```turtle
promo:species promo:label "species" ;
    promo:network "['physical', 'macroscopic', ...]" ;
    promo:type "index" ;
    rdf:_4 promo:global_index_list .
```

`promo:global_index_list` is an RDF sequence of all indices.

### 2.3 Expression list

```turtle
promo:expression_list_V_102 rdf:_0 promo:expression_list_E_1 .

promo:expression_list_E_1 rdf:_0 promo:Instantiate ;
    rdf:_1 promo:left_round ;
    rdf:_2 promo:value ;
    rdf:_3 promo:comma ;
    rdf:_4 promo:value ;
    rdf:_5 promo:right_round .
```

### 2.4 Known export defects

- `promo:index_structures_V_N` objects are empty:
  `promo:index_structures_V_108 rdf:_0 promo: .` — the
  `Variable.index_structures` list is lost.
- `promo:units` is absent — every variable becomes dimensionless.
- The per-equation `network` (expression definition network) is absent; only
  the variable's own network is present.
- The domain tree is not exported at all.

## 3. Proposed ProMo14 RDF topology

We keep the existing predicates where they already work and add the missing
fields.  Everything lives in a single named graph per ontology version, e.g.
``<http://promo.example/ontologies/thermodynamics/v1>``.

### 3.1 Classes

- `promo:Variable` — a declared physical quantity.
- `promo:Index` — a running/block index.
- `promo:ExpressionList` — an RDF sequence of tokens.
- `promo:Token` — an operator/delimiter/function.
- `promo:Equation` — one equation (LHS variable + RHS expression list +
  metadata).
- `promo:OntologyVersion` — version metadata, domain tree, and rules.

### 3.2 Variable predicates

Grouped by purpose, mirroring the ``Variable`` dataclass.

#### Identity & naming

| Predicate | Type | Maps to `EquationContext` |
|---|---|---|
| `promo:iri` | IRI | `Variable.iri` |
| `promo:label` | xsd:string | `Variable.label` |
| `promo:internal_id` | xsd:string | `Variable.internal_id` |
| `promo:has_alias` | `rdf:List` or blank nodes with `promo:language` / `promo:value` | `Variable.aliases` |

#### Domain / location

| Predicate | Type | Maps to `EquationContext` |
|---|---|---|
| `promo:network` | xsd:string | `Variable.network` |
| `promo:variable_class` | xsd:string | `Variable.type` (Python field name; values: `state`, `effort`, ...) |
| `promo:port_variable` | xsd:boolean | `Variable.port_variable` |
| `promo:imported` | xsd:boolean | ontology-only metadata — not in `EquationContext` |

#### Semantics

| Predicate | Type | Maps to `EquationContext` |
|---|---|---|
| `promo:doc` | xsd:string | `Variable.doc` |
| `promo:units` | xsd:string or `rdf:List` of 8 ints | `Variable.units` |
| `promo:has_token` | `promo:Token` (multiple) | `Variable.tokens` |
| `promo:value` | xsd:string | `Variable.value` — pre-bound value slot; universal constants carry it permanently, parameters get it at the instantiation stage (ADR-008) |
| `promo:instanceOf` | `promo:Variable` (IRI) | provenance — this variable was declared an instance of the linked prototype by an `Instantiate` equation (ADR-008) |

`promo:units` is an 8-integer SI exponent vector.  Keep it simple: an
`rdf:List` ``[0, 0, 0, 1, -3, 0, 0, 0]`` (order: time, length, amount,
mass, temperature, current, light, nil) and the loader converts it to
`Units`.

The universal constants `zero`, `one`, `half` are seeded into every
ontology (network `root`, class `constant`, deterministic IRIs
`…#const_zero` / `…#const_one` / `…#const_half`) with `promo:value`
pre-bound — see ADR-008.

#### Index structure

| Predicate | Type | Maps to `EquationContext` |
|---|---|---|
| `promo:has_index_structure` | `promo:Index` (multiple) | `Variable.index_structures` (IRIs) |

#### Equations

| Predicate | Type | Maps to `EquationContext` |
|---|---|---|
| `promo:has_equation` | `promo:Equation` (multiple) | link to equations |
| `promo:compiled_lhs` | xsd:string / JSON | `Variable.compiled_lhs` |
| `promo:memory` | xsd:string / JSON | `Variable.memory` |

### 3.3 Index predicates

#### Identity & naming

| Predicate | Type | Maps to `EquationContext` |
|---|---|---|
| `promo:iri` / IRI itself | IRI | `Index.iri` |
| `promo:label` | xsd:string | `Index.label` |
| `promo:short_name` | xsd:string | `Index.short_name` |
| `promo:has_alias` | `rdf:List` | `Index.aliases` |

#### Domain

| Predicate | Type | Maps to `EquationContext` |
|---|---|---|
| `promo:network` | xsd:string or `rdf:List` | `Index.network` |
| `promo:index_class` | xsd:string | `Index.index_class` (`index` / `block_index`) |

#### Token

| Predicate | Type | Maps to `EquationContext` |
|---|---|---|
| `promo:has_token` | `promo:Token` | `Index.token` |

Indices are typed as `promo:Index` (not bare IRIs).

### 3.4 Equation predicates

#### Identity & naming

| Predicate | Type | Purpose |
|---|---|---|
| `promo:iri` | IRI | stable equation IRI (``E_N``) |
| `promo:internal_id` | xsd:string | legacy `E_N` token / code name |

#### Relationship

| Predicate | Type | Purpose |
|---|---|---|
| `promo:lhs` | `promo:Variable` (IRI) | the variable being defined; avoid duplicating `internal_id` / `latex` |
| `promo:rhs` | `promo:ExpressionList` | token sequence (the `global_ID` form) |
| `promo:rhs_latex` | xsd:string | **generated** LaTeX of the RHS, cached after first render |

#### Context

| Predicate | Type | Purpose |
|---|---|---|
| `promo:network` | xsd:string | **expression definition network** |
| `promo:equation_class` | xsd:string | `generic` / `instantiate` / `balance` / ... |

#### Content

| Predicate | Type | Purpose |
|---|---|---|
| `promo:incidence_list` | `rdf:List` | **derived** list of variable IRIs in the RHS; cached for `Root` incidence checks |
| `promo:doc` | xsd:string | equation documentation |

#### Audit

| Predicate | Type | Purpose |
|---|---|---|
| `promo:created` | xsd:dateTime | creation timestamp |
| `promo:modified` | xsd:dateTime | last modification |

This replaces the old `expression_list_V_N` / `expression_list_E_N`
indirection.  The RHS token list stays an `rdf:List` or `rdf:Seq`.

### 3.5 Domain tree

Store the tree as a single per-ontology `rdf:List` of nodes, or as
`skos:broader` / `promo:parent` edges between `promo:Network` resources:

```turtle
promo:physical a promo:Network ;
    promo:parent promo:root .

promo:macroscopic a promo:Network ;
    promo:parent promo:physical .

promo:reactions a promo:Network ;
    promo:parent promo:physical .
```

The loader walks from an expression network up to root to compute
`accessible_networks`.

### 3.6 Tokens

```turtle
promo:Hadamard a promo:Token ;
    promo:label "Hadamard" ;
    promo:internal_code "." ;
    promo:global_id "O_42" ;
    promo:token_type "operator" .
```

`promo:token_type` is one of `operator`, `delimiter`, `function`.

## 4. Loader contract

The graph-store provider is the seam between the ontology layer and the
equation editor.  It implements `EquationContext` from
`backend/equation/context.py` and must answer one query per context, not per
resolve call, so `CompileSpace` keeps an in-memory snapshot.

Required interface:

```python
class RdfContext(EquationContext):
    def __init__(self, graph_iri: str, version: str,
                 expr_network: str, var_network: str):
        ...

    def variables(self) -> Dict[str, Variable]:
        """Return all variables visible in this context, keyed by IRI."""
        ...

    def indices(self) -> Dict[str, Index]:
        """Return all indices, keyed by IRI."""
        ...

    def accessible_networks(self, network: str) -> Set[str]:
        """All networks from which `network` may resolve unqualified labels.
        Includes `network` and its ancestors up to root."""
        ...
```

The provider must load:

1. **Network hierarchy** — walk `promo:parent` edges to build the tree and
   compute `accessible_networks`.
2. **Variables** — materialise all `promo:Variable` resources with their
   predicates, grouped as in section 3.2.
3. **Indices** — materialise `promo:Index` resources, their `short_name`,
   and their `internal_code` aliases.
4. **Equations** — for each variable, materialise its `promo:Equation`
   resources, including the RHS token stream and `equation_class`.
5. **Tokens** (for import/export) — map `global_id` and `internal_code`
   values to surface strings and IRIs.

A concrete `DictContext` is already implemented for in-memory provision and
testing.  The future `RdfContext` will sit on top of an RDF triple store
(e.g. `rdflib` or a persistent graph database).

## 5. Ontology graph semantics (implemented 2026-09-14)

The editable ontology graph (`https://w3id.org/promo/ontology`) follows these
rules, enforced by `backend/ontology/service.py` and
`backend/core/graph_store.py`:

### Containment vs reference

- **Containment predicates** — deleting the object deletes the subject
  recursively: `promo:parent` (subdomains, sub-tokens, sub-terms,
  sub-scale-values), `promo:hasAxis` (terms → axis), `promo:hasScale`
  (values → dimension), `promo:hasDomain` (axes/dimensions → domain).
- **Reference predicates** — deleting the object only removes the link:
  `promo:hasToken`, `promo:hasScaleValue`, `promo:sourceDomain`,
  `promo:targetDomain`, `promo:sharedTokens`, `promo:axisValue`,
  `promo:token`.
- `_cascade_delete` implements both: contained descendants are deleted
  recursively; all other incoming triples are removed so no dangling
  references remain.

### Token inheritance

- `promo:hasToken` links a domain to the tokens active in it.
- A subdomain inherits all tokens active in its ancestors; the API
  exposes them as `DomainRecord.inherited_tokens` (resolved by walking
  `promo:parent`).  Inheritance is additive — a subdomain can activate
  additional tokens from the global list but cannot remove inherited
  ones.
- `add_domain` replaces the full `hasToken` set on update (not
  append-only); same for `sharedTokens` on connection rules.

### Connection rule resolution

`GET /api/ontology/resolve-connection?source&target` returns the rules
applicable to a domain pair:

- A rule applies when its `source_domain`/`target_domain` equals the
  endpoint domain or one of its ancestors (rules are inherited down the
  domain tree, not copied).
- `bidirectional` rules also match the swapped pair.
- The `scope` attribute filters on the branch pair: `same` requires the
  endpoints to share a common ancestor domain, `cross` requires they do
  not (i.e. different branches), `any` imposes no constraint.  Rules
  without `scope` fall back to the legacy rule-type names.
- `physical-cross` was retired (2026-09-15): a `token-flow` arc with
  `scope=cross` can never apply — cross-branch pairs share no tokens.
  `physical-same` covers all intra-physical continuity, including the
  different-subdomain (liquid–gas) case the old name referred to.
- Results are ordered most-specific first (closest ancestor wins over
  wildcard rules).

## 6. Open questions

1. **Units representation** — do we store raw SI exponents, QUDT quantity
   kinds, or both?  If QUDT, the loader needs a `quantity_kind → Units` map.
2. **Index `network` multiplicity** — an index can be valid in several
   networks (e.g. `t` is valid everywhere).  Should we store a list literal
   or a `promo:valid_in` edge per network?
3. **Expression persistence** — when the user writes a new equation, do we
   create a new `promo:Equation` resource or mutate an existing one?  ADR-006
   says ontologies are versioned, so writes should append a new version.
4. **Entities / incidence graph** — should the modeller own the bipartite
   graph, or is it part of the ontology graph?

## 7. Files / references

- `backend/equation/context.py` — the contract.
- `docs/equation-context-contract.md` — the contract description.
- `docs/ADR-005-equation-editor.md` — serialisation defect.
- `docs/ADR-006-*.md` — ontology versioning.
- ProMo13:
  - `packages/Common/ontologies/var_equ_rdf.ttl`
  - `packages/Common/ontology_container.py`
  - `tests/developer/common/io/storage/test_files/repositoryOK/ontologyOK/variables_v8.json`
  - `tests/developer/common/io/storage/test_files/repositoryOK/ontologyOK/entities.json`
