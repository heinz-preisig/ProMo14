# ProMo Suite Overview

This document captures the cross-cutting architecture of the ProMo
modelling suite — the pipeline, module boundaries, shared contracts,
and decisions that apply across all tools.  Per-tool details live in
`docs/<tool>-overview.md` and `docs/<tool>-status.md`.

## 1. Purpose

ProMo is a physics-based modelling environment.  The suite takes a user
from domain ontology definitions through mathematical behaviour
equations, entity behaviour linking, graphical model composition,
parameter instantiation, and finally numerical code generation.

The suite replaces the legacy ProMo13 (PyQt + TPG parser) with
browser-based frontends and a Python backend, while preserving the
mathematical compiler and semantic checking logic that made ProMo13
sound.

## 2. Pipeline

```
Ontology Editor → Equation Editor → Behaviour Linker → Modeller → Model Reuse → Instantiation → Code Generation
```

| Stage | Module | What it does |
|-------|--------|-------------|
| 1 | Ontology Editor | Defines the framework: domain tree, tokens, classification axes, scales, entity types, connection rules, indices, and abstract graphical symbols. Source of truth for all downstream vocabulary. |
| 2 | Equation Editor | Authors and checks mathematical expressions. Produces a validated var/expr knowledge graph. |
| 3 | Behaviour Linker | Selects equations describing I/O behaviour of a base entity and assigns its concrete graphical representation (level-2 graphics). |
| 4 | Modeller | Assembles base entities into larger models by drawing connections. Produces a flat RDF topology + hierarchy. |
| 5 | Model Reuse | An assembled model can be used as a base entity in a later model. Same format, recursive composition. |
| 6 | Instantiation | Assigns constants and parameters to a model definition. Result is itself reusable. |
| 7 | Meshing (future) | Discretises spatial domains of distributed systems (PDEs) into networks of coupled lumped systems. Only applies to distributed subsystems; lumped and event-dynamic systems skip this step. |
| 8 | Code Generation | Transforms a validated, instantiated (and meshed) model into numerical code. |

Stages 5–8 are downstream of the current implementation focus and are
not yet built.  The meshing concept is documented in
`docs/distributed-systems-design.md`.

## 3. Core modelling concepts: the var/expr bipartite graph

ProMo models are not an unstructured set of equations.  They are a
**bipartite variable–expression graph** that is built from the bottom up and
kept **lower-triangular**.

1. **Port variables — the foundation.**  Port variables are the
   fundamental quantities and constants — the leaves of the dependency graph.
   To define any variable the user first selects a **domain (network)** and
   a **variable class** that applies to that domain.  A port variable is
   then defined by giving it:
   - an IRI and a user-visible label;
   - a variable class, e.g. `state`, `effort`, `transport`, `frame`,
     `constant` or `parameter`;
   - a network / domain in which it lives;
   - physical units (SI vector or QUDT reference);
   - an index structure (the tensor indices it carries).

   Port variables have **no defining RHS expression**.  They are the base of
   the bipartite graph.

2. **Derived variables and equations.**  A non-port variable is introduced by
   giving it a name and then a defining RHS expression.  The RHS may only use
   variables that are already declared or already defined.  This keeps the
   var/expr graph acyclic and lower-triangular.

3. **Multiple definitions.**  A non-port variable may have more than one
   checked definition.  Each definition is a separate `promo:Equation`
   resource with its own expression network, equation class, and RHS.  The
   Behaviour Linker later selects which definitions are active for a given
   base entity, so multiple definitions provide alternative constitutive,
   empirical, or balance relations for the same variable.

4. **Domain and variable class.**  Every variable and every equation is
   authored in a domain (network) and carries a variable class chosen from
   those that apply to that domain.  The domain tree determines which
   variables are visible to a given expression (the expression network plus
   its ancestors).

5. **Checked = trusted.**  The Equation Editor checks syntax, units, index
   structures, and acyclic incidence.  Once a definition passes, it becomes a
   node in the var/expr knowledge graph and is trusted by all downstream
   tools without re-checking.

## 4. Cross-cutting architectural decisions

### 4.1 Browser-based frontends, Python backend

All tools have browser-based frontends (React + TypeScript).  The
mathematical compiler, semantic checker, and ontology logic stay in
Python behind FastAPI.  Frontends are thin clients; the authoritative
check remains the backend.

Motivation: unified tech stack, one spawnable Graphic Object Editor
(ADR-004), unified IRI/catalogue space.

### 4.2 RDF and IRI-based identity

All artefacts — ontology resources, variables, equations, model nodes,
arcs, graphical definitions — are identified by IRIs in RDF named
graphs.  The IRI is the stable identity across versions, merges, and
tools.

### 4.3 Three-name pattern

Every variable, index, token, and equation carries three names:

| Name | Form | Scope | Purpose |
|------|------|-------|---------|
| **IRI** | full RDF IRI | global, stable | semantic identity, graph key, cross-module reference |
| **label** | user-chosen symbol (`rho`, `T`) | unique within a network | what the user types and sees |
| **internal_id** | `V_1`, `E_3`, `I_2` | unique within a compilation scope | code generation, token stream |

The IRI is the canonical key.  Labels are scoped, not globally unique.
Internal IDs are code-safe and allocated by the backend.

### 4.4 Named graphs and ontology versioning

Each published ontology is a versioned named graph.  Ontology resources
are IRI-identified and immutable within a version.  Evolution produces
a new named graph, not in-place edits.  Authored artefacts record which
ontology version they were checked against (`promo:checkedAgainst`).

See ADR-006 for the change classification (additive, annotation,
deprecation, semantic modification, deletion) and migration rules.

### 4.5 Publish–consume contract

A checked expression is **trusted**.  All structural checking (syntax,
units, index consistency) happens once, at authoring time, inside the
equation editor backend.  Downstream consumers (Behaviour Linker,
Modeller, code generator) carry no checking logic.  This removes
validation overhead from generated model code entirely.

Consequence: the backend checker is the gatekeeper.  Whatever passes
the editor's checks is contractually consistent.

### 4.6 External ontology references

The suite mixes external ontology references (QUDT for quantities,
units, dimensions) with ProMo-specific definitions (variable types,
token types, domain tree).  Variables link to public IRIs when they
exist (e.g. `qudt:Entropy`); otherwise ProMo-namespace IRIs are minted.

## 5. Inter-module contracts

These are the seams between modules.  Each contract defines what one
module produces and the next consumes.  Changing a contract requires
coordinating across modules.

### 5.1 Ontology Editor → Equation Editor

**Contract: `EquationContext`** (see `backend/equation/context.py`,
`docs/equation-context-contract.md`)

The equation editor does not read the ontology graph directly.  It
consumes a read-only snapshot:

- `variables()` — keyed by IRI, each with label, network, units, index
  structures, tokens, aliases.  (Variables are authored in the
  Equation Editor; the ontology provides the framework — tokens,
  indices, domain tree, classification axes — not the variables
  themselves.)
- `indices()` — keyed by IRI, each with label, network, token binding.
- `accessible_networks(network)` — the expression network plus all
  ancestors; determines which variables are visible for unqualified
  label resolution.

A `DictContext` provides this from in-memory dicts for testing and the
API.  A future `RdfContext` will sit on top of a triple store.  The
checker code does not change when the provider changes.

### 5.2 Equation Editor → Behaviour Linker

**Contract: var/expr knowledge graph** (see ADR-005,
`docs/ontology-data-model.md`)

The equation editor produces a JSON-LD named graph containing:

- Variable resources (IRI, label, units, index structures, tokens,
  aliases, network, equations).
- Equation resources (LHS variable IRI, RHS token sequence as
  `rdf:List`, incidence list, equation class, expression network).
- Index and token definitions.

The Behaviour Linker consumes this to select which equations describe a
base entity's I/O behaviour.

### 5.3 Behaviour Linker → Modeller

**Contract: base-entity catalogue + graphical assignments + connection
rules** (see ADR-004, `packages/semantic/src/contracts.ts`)

The Behaviour Linker produces, for each base entity:

- Semantic identity (IRI), domain, tokens, interfaces (exposed
  inputs/outputs).
- Graphical definition (shape, fill, stroke, ports, labels).
- Connection rules (which entity types may connect via which arc types).

The Modeller consumes these through two TypeScript interfaces:

- `SemanticCatalogue` — resolves entity types, arc types, graphical
  definitions, domains, tokens, interfaces.
- `ConnectionRuleResolver` — decides which arc types are valid between
  a source and target entity.

In-memory placeholder implementations exist.  A real ontology backend
will supply the same interfaces.

### 5.4 Modeller → Downstream (Reuse, Instantiation, Codegen)

**Contract: flat RDF topology + separate hierarchy + layout**

The Modeller produces:

- A flat RDF knowledge graph of model nodes (referencing base entities)
  and arcs (typed connections).
- A separate hierarchy tree for navigation and grouping.
- Layout data (positions, arc routing, knots).

An assembled model can be published as a reusable entity and inserted
into another model.  Instantiation adds constants/parameters to the
topology.  Code generation consumes the instantiated model.

## 6. Shared infrastructure

### 6.1 `packages/semantic` (TypeScript)

Shared IRI-based contracts used by the Modeller (and eventually the
Behaviour Linker):

- `contracts.ts` — `SemanticCatalogue`, `ConnectionRuleResolver`,
  graphical definition interfaces.
- `placeholderCatalogue.ts` — in-memory placeholder implementations.
- `connectionService.ts` — shared connection-rule query/resolve helpers.

### 6.2 `backend/core` (Python)

Shared backend services (RDF store, IRI minting, ontology client) —
scaffolded, not yet implemented.

### 6.3 Graphic Object Editor

One spawnable graphical editor serves two entry points (ADR-004 §5):

- **Behaviour Linker** spawns it after a base entity's equations and
  I/O behaviour are defined — to assign the entity's graphical
  representation.
- **Modeller** spawns it after a composite model and its exposed
  interface are defined — to assign the composite's graphical
  representation and map visual ports to semantic inputs/outputs.

Both use the same graphical vocabulary and persistence format.  The
Modeller's renderer does not depend on which module spawned the editor.

## 7. Monorepo structure

```
ProMo14/
├── apps/
│   ├── modeller/              # React + Konva model composer
│   ├── equation-editor/       # React + TypeScript + Vite equation editor
│   ├── ontology-editor/       # Frontend scaffold
│   ├── behaviour-linker/      # Frontend scaffold
│   ├── instantiation/         # Instantiation report / codegen viewer
│   └── species/               # Species & reaction artefact editor (§20)
├── packages/
│   └── semantic/              # Shared TS contracts, catalogue, rules
├── backend/
│   ├── equation/              # Parser, checker, compile space, service
│   ├── ontology/              # Scaffold
│   ├── behaviour/             # Scaffold
│   ├── modeller/              # Scaffold
│   ├── instantiate/           # §16 resolver, §19 builder, §20 distribution
│   ├── species/               # §20 species artefact GET/PUT service
│   └── core/                  # Shared backend services (scaffold)
├── docs/                      # All documentation
├── package.json               # npm workspaces root
└── tsconfig.base.json         # Shared TypeScript config
```

## 8. Data flow

```
Ontology Editor
    │  produces: ontology named graph (domain tree, tokens, classification
    │           axes, scales, entity types, connection rules, indices,
    │           abstract graphical symbols)
    │  contract: EquationContext (tokens, indices, domain tree, axes)
    ▼
Equation Editor
    │  consumes: EquationContext (tokens, indices, domain tree, axes)
    │  produces: var/expr knowledge graph (JSON-LD, variables, equations,
    │           checked expressions, incidence lists)
    │  contract: var/expr graph
    ▼
Behaviour Linker
    │  consumes: var/expr graph + ontology (entity types, rules, symbols)
    │  produces: base-entity definitions (behaviour + level-2 graphics +
    │           connection rules)
    │  contract: SemanticCatalogue + ConnectionRuleResolver
    ▼
Modeller
    │  consumes: base-entity catalogue, connection rules, graphical definitions
    │  applies: glasses (domain-specific visual skins, separate artefact)
    │  produces: flat RDF topology + hierarchy + layout + level-3 composite graphics
    ▼
Model Reuse / Instantiation
    │  produces: instantiated model (constants/parameters assigned)
    │
    ├─ lumped / event-dynamic ──→ Code Generation
    │
    └─ distributed (PDE) ──→ Meshing ──→ lumped network ──→ Code Generation
```

Glasses (domain-specific visual skins) are a **separate artefact**,
authored independently, stored in their own named graph.  The Modeller
is the primary consumer.  See `docs/ontology-design-discussion-2026-09-11.md`
§19–21 for the three-level graphics model.

## 9. Documentation map

### Suite-level
- `docs/suite-overview.md` — this document
- `docs/suite-status.md` — suite-wide implementation status

### Per-tool
- `docs/modeller-overview.md` + `docs/modeller-status.md`
- `docs/equation-editor-overview.md` + `docs/equation-editor-status.md`
- `docs/ontology-editor-overview.md` + `docs/ontology-editor-status.md`
- `docs/behaviour-linker-overview.md` + `docs/behaviour-linker-status.md`
- `docs/species-status.md` — §20 species allocation & distribution

### Decision records (ADRs)
- `docs/ADR-001-hierarchy.md` — Modeller hierarchy design
- `docs/ADR-002-state-management.md` — Modeller command automaton
- `docs/ADR-003-multiple-views.md` — Modeller multiple GraphView panels
- `docs/ADR-004-model-and-graphical-architecture.md` — model composition, graphical assignment, shared Graphic Object Editor
- `docs/ADR-005-equation-editor.md` — equation language, parser, browser architecture
- `docs/ADR-006-ontology-evolution.md` — ontology versioning and change classification
- `docs/ADR-007-model-persistence.md` — modeller RDF topology, hierarchy/layout persistence boundaries
- `docs/ADR-008-instantiate-and-constants.md` — `Instantiate(proto)` instance declaration, universal constants, three-layer binding model

### Detailed technical references
- `docs/equation-context-contract.md` — EquationContext protocol and CompileSpace resolution rules
- `docs/ontology-data-model.md` — variable/index/equation/token RDF schema, loader contract
- `docs/ontology-editor-design.md` — ontology editor UI layout and workflow
- `docs/behaviour-linker-design-discussion.md` — living BL design doc: state emergence, tokens, reference coordinates (§15), arc sub-indices (§16), scale regimes + seed contract (§17)
- `docs/versioning-and-session-design.md` — artefact lines, `usesOntology` pins, resolution-scope rulings R1–R5
- `docs/distributed-systems-design.md` — meshing concept for distributed PDE systems (future)

