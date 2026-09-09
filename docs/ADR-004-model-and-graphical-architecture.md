# ADR-004: Model Composition and Graphical Assignment

## Status

Draft — agreed direction for the Modeller prototype

## Context

The Modeller is the core composition module of the ProMo suite. ProMo separates the definition of reusable entities from the assembly of model instances:

1. The ontology defines the fundamental entity types, domains, arc types, subtype relationships, and connection rules.
2. The Equation Editor defines mathematical equations.
3. The Behaviour Linker selects equations that describe the input/output behaviour of a base entity and assigns its graphical representation.
4. The Modeller assembles references to these base entities into larger models.
5. An assembled model can itself become a reusable model entity and be inserted into a later model.
6. A later instantiation stage assigns model-defining constants and parameters. The resulting instantiated model can itself become a reusable model entity and be inserted into a later model.
7. Code generation transforms a validated, instantiated model into code for numerical solution.

The details of the RDF representation used by the Equation Editor and Behaviour Linker are deferred until those modules are rebuilt. The physical-behaviour formalism is likewise outside the Modeller: it is expected to build on Hamiltonian/Lagrangian mechanics and contact geometry for thermodynamics, while transport systems are represented as distributed systems with event dynamics. In that interpretation, model arcs express continuity conditions in effort variables and token flows.

## Decision

### 1. Flat model topology

The authoritative model topology is a flat RDF knowledge graph. It stores model-node instances and actual arcs between them. Each model node references a separately defined base entity; the base entity's equations and behaviour graph are not embedded in the model topology.

Conceptually:

```typescript
interface ModelNode {
  iri: string
  baseEntityIri: string
  domainIri: string
}

interface ModelArc {
  iri: string
  sourceIri: string
  targetIri: string
  arcTypeIri: string
}
```

Every actual connection occurs exactly once in the flat topology. A hierarchical view may project an arc through a composite graphical node, but this does not create another semantic arc.

### 2. Separate hierarchical mapping

A separate strict hierarchy maps and partitions the flat topology for grouping, navigation, local editing, and scalable rendering. Its leaves reference nodes in the flat model graph. Internal hierarchy nodes represent composites and do not replace the underlying topology.

A `GraphView` is computed from:

- the flat RDF topology;
- the attached hierarchy;
- layout data; and
- the current view context.

The hierarchy and view projection make it possible to work with models containing millions of nodes without rendering the complete topology at once.

### 3. Domains, tokens, and connection rules

Each model node belongs to exactly one network/domain. The criteria for defining a domain depend on the kind of system being modelled.

In physical systems, a domain is essentially characterized by the tokens present and their state. Tokens represent the quantities handled by model entities and connections. Fundamental token categories include species or mass, energy, momentum, and charge, while the ontology may define more specific token types, state descriptions, and subtype relationships. Differences in token kind or relevant state may therefore establish boundaries between physical domains.

In control and generic information-processing systems, structural and functional considerations dominate domain definition rather than conserved physical tokens alone. Control domains may correspond to the part of the physical system being governed, the scope of coordination, or the decision horizon. Controllers may range from local regulation through plant- or system-wide coordination, and from event-level responses through short-term control to long-term planning. The ontology must consequently support domain-definition criteria appropriate to each abstraction, without requiring one universal physical interpretation.

Entities may transport or conserve tokens, and some behaviours generate tokens of another type from one or more input tokens. Chemical reactions transform input species into output species; mass-to-energy conversion is a cross-category transformation. These transformations are semantic behaviour definitions, not graphical-editor logic.

An arc is either internal to one domain or crosses between two domains; this can be derived from the domains of its endpoints. Its permitted token transport must be compatible with the source and target interfaces and with any transformation declared by the connected entities.

All connections are governed by ontology-defined rules. Rule resolution may depend on:

- source and target entity types, including inherited types;
- source and target token types;
- whether the relevant behaviour transports, conserves, consumes, produces, or transforms tokens;
- arc type;
- source and target domain types; and
- whether the connection is domain-internal or cross-domain.

The generic editor asks a rule resolver which arc types are valid.

### 4. Generic graphical object vocabulary

The Modeller remains domain-independent. The mathematical formalism, equation semantics, token-flow laws, effort-variable continuity conditions, and event dynamics must not be implemented in its rendering or interaction code. Those concerns belong to ontology, behaviour, and validation services. The Modeller consumes only generic entity references, resolved graphical definitions, interface descriptions, and connection-rule results.

It implements a finite vocabulary of graphical primitives and interaction capabilities, such as nodes, arcs, labels, ports, knots, handles, shapes, line styles, selection, dragging, and connection. An arc is graphically a typed connection even when its physical semantics are a continuity condition; the renderer does not interpret that condition.

### 5. Graphical assignment workflow

Graphical assignment is performed by the same Graphic Object Editor, which can be spawned from two entry points:

- The Behaviour Linker spawns it after a base entity's equations and input/output behaviour have been defined.
- The Modeller spawns it after a composite model and its exposed interface have been defined.

The Graphic Object Editor uses the same graphical vocabulary and persistence format in both cases. It receives the target entity or model as context and returns its graphical-definition assignment; the Modeller's renderer therefore does not depend on which module spawned the editor.

Composite graphical ports map to the composite model's exposed semantic inputs and outputs. Changes to that interface must invalidate or revalidate the graphical port mapping.

### 6. Recursive model reuse

Fundamental entities, assembled model definitions, and instantiated models present a common composable interface to the Modeller. Once a composite model is defined and published, it can be selected and used like a base entity when constructing another model. A model whose constants and parameters have already been instantiated can likewise be inserted into a later model, retaining those assignments unless the composition workflow explicitly permits overrides.

The receiving model still stores a flat instantiated topology and an attached hierarchy. Provenance records whether inserted model parts originated from a reusable model definition or from an instantiated model, together with the source identity and version. The precise import/materialisation, identity, and parameter-override mechanisms remain open design items.

### 7. Separation of persistent and transient information

Persistent semantic/catalogue information:

- flat RDF topology;
- base-entity references;
- domain membership;
- ontology-defined node classifications, including time scale and length scale;
- typed arcs;
- parameter and constant assignments;
- reusable model metadata;
- graphical-definition assignments for base entities and reusable composites;
- token definitions, domain association, and transformation semantics;

Node classification is deliberately open-ended. Time scale and length scale are known classification dimensions, but further dimensions may be introduced at higher abstraction levels or by future ontologies. The Modeller therefore must not encode them as a closed TypeScript union or fixed set of fields. It preserves ontology predicates and values as semantic attributes and obtains their interpretation, inheritance, validation, and graphical consequences from external catalogue and resolver contracts.

Persistent view information:

- hierarchy mapping;
- positions and arc routing;
- permitted instance-specific presentation overrides.

Transient editor information:

- computed `GraphView` projections;
- resolved graphical attributes;
- `SceneObject[]`;
- selection, hover, drag, pan, and zoom state.

## Data flow

```text
Ontology + base-entity catalogue + graphical assignments
                         |
                         v
Flat RDF topology + separate hierarchy + layout
                         |
                         v
                  computed GraphView
                         |
                         v
            graphical/type/rule resolution
                         |
                         v
                    SceneObject[]
                         |
                         v
                    SceneRenderer
```

Downstream processing is:

```text
Model composition -> parameter instantiation -> validation -> code generation
```

## Consequences

- `ModelNode.entityType` in the prototype will eventually become or be supplemented by a `baseEntityIri` and domain reference.
- Hard-coded `TypeA`, `TypeB`, `TypeC`, `ArcType1`, and `ArcType2` values are temporary placeholders.
- Hard-coded scene styles will be replaced by resolved graphical definitions.
- Connection validation will move behind an ontology-backed rule resolver.
- The hierarchy remains separate from the RDF topology.
- Composite graphical assignment requires a stable exposed interface and port mapping.
- Large models require on-demand graph and hierarchy access rather than loading the complete RDF graph into browser `Map` objects.
- Node typing and classification must support open-ended ontology predicates rather than only base-entity type and domain membership.
- Tokens are ontology-defined semantic quantities that live in domains; token transport and transformation participate in interface and connection-rule validation.
- Domain semantics are ontology-defined: physical domains are primarily characterized by tokens and state, whereas control and information-processing domains may be primarily structural, functional, or temporal.
- Physical and mathematical formalisms are outside the Modeller boundary; replacing or extending them must not require changes to generic scene construction, rendering, or interaction handling.

## Open questions

1. RDF vocabulary and storage boundaries for model topology, base-entity references, and reusable composite definitions.
2. Materialisation, identity, provenance, and parameter-override rules when inserting a reusable definition or instantiated model.
3. RDF representation of token types, token instances or values, domain association, conservation, and transformation rules.
4. RDF or external format for graphical definitions and graphical port mappings.
5. Lifecycle and versioning when a base entity or composite interface changes.
6. Query/storage technology for models containing millions of nodes.
