# Ontology Editor v1 — Implementation Ticket

## Context

The ontology design discussion (see `docs/ontology-design-discussion-2026-09-11.md`)
has resolved the core conceptual questions. The existing scaffolding
(backend: `backend/ontology/`, `backend/core/graph_store.py`; frontend:
`apps/ontology-editor/`) provides a working starting point with CRUD for
networks, variables, indices, tokens, and equations, backed by an RDF
store with TriG persistence.

This ticket covers the changes needed to align the editor with the
design decisions.

## Design reference

- `docs/ontology-design-discussion-2026-09-11.md` — all resolved questions
- CWA 17960:2022 — entity type taxonomy (5 physical + 3 information)
- Flexibility principle: minimal fixed core, user-defined structure

---

## 1. RDF vocabulary extensions

**File:** `backend/core/graph_store.py`

Add new PROMO vocabulary terms for the design concepts. Keep the
namespace (`http://example.org#`) but introduce meaningful predicates:

```
# Domain tree
promo:Domain          rdf:type  — a domain in the tree
promo:branch          — "physical" or "information" (top-level only)
promo:hasToken        — links a domain to tokens that live in it

# Classification axes
promo:ClassificationAxis  rdf:type  — an axis definition
promo:axisName           — axis label (e.g. "role", "extensivity")
promo:axisTerm           rdf:type  — a term in an axis hierarchy
promo:axisValue          — links a variable to an axis term
promo:hasAxis            — links a domain to an axis it defines

# Entity type taxonomy
promo:EntityType      rdf:type  — an entity type (CWA 17960)
promo:temporalType    — "constant" | "dynamic" | "event-dynamic"
promo:spatialType     — "uniform" | "distributed" (physical only)
promo:spatialSize     — "infinite" | "finite" | "infinitesimal" (physical only)

# Connection rules
promo:ConnectionRule  rdf:type  — a connection rule definition
promo:ruleType         — "physical-same" | "physical-cross" | "signal"
promo:sharedTokens     — tokens that must be shared for physical rules

# Equation classes (hierarchical)
promo:EquationClass   rdf:type  — an equation class node
promo:equationClass   — links an equation to its class (IRI, not string)
```

The existing `promo:parent` predicate is reused for all hierarchies
(domain tree, token tree, axis terms, equation classes).

**`variable_class` field migration:** The existing `promo:variableClass`
predicate (string literal) is replaced by `promo:axisValue` linking to
an `promo:axisTerm` in the "role" axis. A migration helper should
convert existing string values to axis term IRIs.

---

## 2. Backend model updates

**File:** `backend/ontology/models.py`

### 2.1 Domain tree

Rename `NetworkRecord` → `DomainRecord` (keep `NetworkRecord` as alias
for backward compat):

```python
class DomainRecord(BaseModel):
    iri: str
    name: str
    label: Optional[str] = None
    parent: Optional[str] = None
    branch: Optional[str] = None  # "physical" or "information" (top-level only)
    children: List[str] = Field(default_factory=list)
    tokens: List[str] = Field(default_factory=list)  # token IRIs bound to this domain
```

### 2.2 Classification axes

New models:

```python
class ClassificationAxisRecord(BaseModel):
    iri: str
    domain: str  # domain IRI where this axis is defined
    name: str    # e.g. "role", "extensivity", "origin"
    parent: Optional[str] = None  # inherited from parent domain

class AxisTermRecord(BaseModel):
    iri: str
    axis: str  # axis IRI
    label: str
    parent: Optional[str] = None  # hierarchical (tree)
```

### 2.3 Variable record

Update `VariableRecord` to extend the existing data model from
`docs/ontology-data-model.md` — add `classifications`, keep all
existing fields:

```python
class EquationRecord(BaseModel):
    """Nested inside a variable, one per expression network."""
    iri: str
    internal_id: Optional[str] = None  # E_N code name
    lhs: str                           # variable IRI being defined
    rhs: str = ""                      # token stream (global_ID form)
    rhs_latex: str = ""                # generated LaTeX, cached
    equation_class: str = "generic"    # IRI of EquationClass node (hierarchical)
    network: str = "root"              # expression definition network
    incidence_list: List[str] = Field(default_factory=list)  # derived, cached
    doc: str = ""
    created: Optional[str] = None
    modified: Optional[str] = None

class VariableRecord(BaseModel):
    # Identity & naming (three-name pattern)
    iri: str
    label: str
    internal_id: Optional[str] = None
    aliases: Dict[str, str] = Field(default_factory=dict)
    # extensible: internal_code, latex, matlab, python, modelica, ...

    # Domain / location
    network: str = "root"
    classifications: Dict[str, str] = Field(default_factory=dict)
    # Replaces variable_class: map of axis IRI -> axis term IRI
    port_variable: bool = False
    imported: bool = False  # ontology-editor metadata

    # Semantics
    doc: str = ""
    units: List[int] = Field(default_factory=lambda: [0] * 8)
    tokens: List[str] = Field(default_factory=list)

    # Index structure
    index_structures: List[str] = Field(default_factory=list)

    # Equations (nested, one per expression network)
    equations: Dict[str, EquationRecord] = Field(default_factory=dict)

    # Codegen metadata (not consumed by equation editor)
    compiled_lhs: Optional[Dict] = None
    memory: Optional[Dict] = None

    # Audit
    created: Optional[str] = None
    modified: Optional[str] = None
```

Keep `variable_class` as a computed property for backward compat:
`classifications.get("<role-axis-iri>")`.

### 2.4 Equation record

Equations are nested inside variables (see `EquationRecord` above),
matching the existing data model in `docs/ontology-data-model.md`.
The `equation_class` field changes from a flat string to an IRI
referencing a hierarchical `promo:EquationClass` node.

Equation class values from the existing model: `generic`,
`instantiate`, `balance`, `empirical`, `user_function`.  These
become top-level nodes in the equation class hierarchy, with
sub-classes added per domain.

### 2.5 Entity type

New model:

```python
class EntityTypeRecord(BaseModel):
    iri: str
    label: str
    temporal_type: str  # "constant" | "dynamic" | "event-dynamic"
    spatial_type: Optional[str] = None  # "uniform" | "distributed" (physical only)
    spatial_size: Optional[str] = None  # "infinite" | "finite" | "infinitesimal"
    branch: str  # "physical" | "information"
    description: str = ""
```

### 2.6 Connection rule

New model:

```python
class ConnectionRuleRecord(BaseModel):
    iri: str
    rule_type: str  # "physical-same" | "physical-cross" | "signal"
    source_domain: Optional[str] = None  # for physical-cross
    target_domain: Optional[str] = None
    shared_tokens: List[str] = Field(default_factory=list)  # token IRIs
    direction: Optional[str] = None  # "bidirectional" | "unidirectional"
    description: str = ""
```

---

## 3. Backend service updates

**File:** `backend/ontology/service.py`

### 3.1 New endpoints

```
# Classification axes
GET  /api/ontology/axes          — list all axes (with domain)
POST /api/ontology/axes          — create/update an axis
GET  /api/ontology/axes/{iri}    — get one axis with its terms
DELETE /api/ontology/axes/{iri}  — delete an axis

# Axis terms
GET  /api/ontology/axis-terms          — list all terms
POST /api/ontology/axis-terms          — create/update a term
DELETE /api/ontology/axis-terms/{iri}  — delete a term

# Entity types
GET  /api/ontology/entity-types          — list all entity types
POST /api/ontology/entity-types          — create/update an entity type
DELETE /api/ontology/entity-types/{iri}  — delete an entity type

# Connection rules
GET  /api/ontology/connection-rules          — list all rules
POST /api/ontology/connection-rules          — create/update a rule
DELETE /api/ontology/connection-rules/{iri}  — delete a rule

# Tokens (upgrade from read-only)
POST /api/ontology/tokens          — create/update a token
DELETE /api/ontology/tokens/{iri}  — delete a token
```

### 3.2 Updated endpoints

```
# Domains (was networks)
GET /api/ontology/domains  — list domains with branch + tokens
POST /api/ontology/domains — create/update with branch + token binding

# Variables — classifications instead of variable_class
GET /api/ontology/variables  — include classifications map
POST /api/ontology/variables — accept classifications map

# Context — include axes, entity types, connection rules
GET /api/ontology/context — full context with all new entities
```

### 3.3 Graph store methods

Add to `RdfStore`:

- `add_domain(graph, name, branch, parent, tokens)` — domain with
  branch type and token bindings
- `add_classification_axis(graph, iri, domain, name, parent)`
- `add_axis_term(graph, iri, axis, label, parent)`
- `add_entity_type(graph, iri, label, temporal, spatial, size, branch)`
- `add_connection_rule(graph, iri, rule_type, ...)`
- `add_equation_class(graph, iri, label, parent)`

### 3.4 RdfContext updates

**File:** `backend/ontology/rdf_context.py`

Add methods:
- `axes()` — returns `Dict[str, ClassificationAxis]` with terms
- `entity_types()` — returns `Dict[str, EntityType]`
- `connection_rules()` — returns `List[ConnectionRule]`
- `domain_tokens(domain)` — returns tokens bound to a domain

Update `variables()` to load classifications map instead of
`variableClass` string.

---

## 4. Frontend updates

**File:** `apps/ontology-editor/src/`

### 4.1 New tabs

Add tabs for the new concepts:

```
Variables | Indices | Domains | Tokens | Equations | Axes | Entity Types | Rules
```

### 4.2 Domain tree (left panel)

- Show two explicit root nodes: **physical** and **information**
- Subdomains nested under their parent
- Token badges on each domain node (showing which tokens live there)
- Click a domain to filter variables/indices/equations

### 4.3 Variable editor

Replace the single "Class" text input with a **multi-axis tagger**:
- For each axis defined in the variable's domain (inherited from
  parents), show a dropdown (tree-picker) for that axis
- Show inferred defaults (from domain, equation class, token binding)
  as pre-selected values
- User can override any axis value
- Bulk tagging: select multiple variables, set one axis value for all

### 4.4 Axes tab

- List axes per domain (tree view)
- For each axis: show the term hierarchy (tree)
- CRUD: create/edit/delete axes and terms
- Inheritance indicator: show which axes are inherited from parent domains

### 4.5 Entity types tab

- Show the CWA 17960 taxonomy as a table (5 physical + 3 information)
- Read-only for v1 (the taxonomy is fixed from the standard)
- Future: allow user-defined entity types

### 4.6 Connection rules tab

- List the 3 rule types
- For each rule: show source/target domain, shared tokens, direction
- CRUD: create/edit/delete rules
- Validation: warn if a rule references non-existent tokens or domains

### 4.7 Tokens tab

- Show token tree (hierarchical, with `promo:parent`)
- Show which domains each token is bound to
- CRUD: create/edit/delete tokens (currently read-only)
- Drag tokens onto domains to bind them (future)

### 4.8 Types updates

**File:** `apps/ontology-editor/src/types.ts`

Add interfaces for `ClassificationAxisRecord`, `AxisTermRecord`,
`EntityTypeRecord`, `ConnectionRuleRecord`. Update `VariableRecord`
with `classifications` map, nested `EquationRecord` (matching
`docs/ontology-data-model.md`), and all existing fields (aliases,
imported, compiled_lhs, memory, equations, timestamps). Update
`NetworkRecord` → `DomainRecord` with `branch` and `tokens`.

Update `EquationRecord` interface to match the existing data model:
`iri`, `internal_id`, `lhs` (variable IRI), `rhs` (token stream),
`rhs_latex`, `equation_class` (IRI), `network`, `incidence_list`,
`doc`, `created`, `modified`.

### 4.9 API updates

**File:** `apps/ontology-editor/src/api.ts`

Add functions for all new endpoints (axes, axis-terms, entity-types,
connection-rules, token CRUD, domain CRUD).

---

## 5. Seed data

On first load (no `ontology.trig`), seed:

- Two root domains: `physical` (branch=physical) and `information`
  (branch=information)
- Default tokens for physical: `energy`, `mass`, `momentum`, `charge`,
  `entropy`, `component_mass`
- Default token for information: `signal`
- Default "role" axis on both branches:
  - Physical: `state`, `effort`, `transport`, `frame`, `constant`,
    `parameter`
  - Information: `state`, `input`, `output`, `constant`, `parameter`
- 8 entity types (5 physical + 3 information from CWA 17960)
- 3 connection rule types (physical-same, physical-cross, signal)

---

## 6. Implementation order

1. **RDF vocabulary** — add predicates to `graph_store.py`
2. **Backend models** — update `models.py` with new record types
3. **Graph store methods** — add CRUD methods for new entity types
4. **Backend service** — add/update API endpoints
5. **RdfContext** — update to load new entities
6. **Seed data** — bootstrap the default ontology
7. **Frontend types + API** — update TypeScript
8. **Frontend domain tree** — two-branch tree with token badges
9. **Frontend variable editor** — multi-axis tagger
10. **Frontend new tabs** — axes, entity types, connection rules, tokens CRUD

---

## 7. Out of scope for v1

- Event dynamic equation editor (equation-level, not ontology)
- Mechanical device modelling abstraction (Q10, not yet analysed)
- User-defined validation rules for axis values (v2)
- Drag-and-drop token binding (v2)
- User-defined entity types beyond CWA 17960 (v2)
- Ontology versioning and named graph evolution (ADR-006, separate)
- QUDT integration for units (separate ticket)
