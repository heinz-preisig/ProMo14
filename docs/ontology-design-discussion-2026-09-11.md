# Ontology Design Discussion — 2026-09-11

**Status:** In-progress design discussion.  Captures decisions and open
questions from the 2026-09-11 session.  These will be folded into the
ontology editor design docs once finalised.

## Context

After archiving the legacy corpus test and cleaning up the repository,
the session pivoted to a design discussion for the ontology editor.  The
goal is to define what the ontology contains and how it is structured
before building the editor frontend.

## Key decisions

### 1. Two-branch ontology structure

The ontology has two branches:

**Structure branch** — *what exists in a domain*
- A domain is implicitly defined by which tokens live in it (mass,
  energy, momentum, charge, species, signal, ...).
- Structural elements: nodes, arcs, tokens, conversion, signals.
- Each structural element can give rise to indices (see §2).

**Behaviour branch** — *how things behave in a domain*
- Defines variable classes (state, effort, transport, ...) for each
  structural element and domain/subdomain.
- **Inheritance applies**: a subdomain inherits variable classes from
  its parent domain and may add or specialise them.
- E.g. `thermo` defines `state` and `effort`; `liquid` (child of
  `thermo`) inherits both and may add `transport`.

The domain tree serves both branches:
- **Structurally**: a domain is characterised by its tokens.
- **Behaviourally**: variable classes are defined per domain with
  inheritance down the tree.

### 2. Index sources

Indices arise from multiple structural elements, not just tokens:

- **Nodes** — spatial discretisation or network topology (node 1, 2, … N).
- **Arcs** — connections between nodes (arc indices for
  incidence/adjacency).
- **Tokens** — physical quantities carried by the system (species,
  mass, energy, momentum, charge).
- **Conversion** — transformation processes (e.g. reaction → product).
- **Signals** — information/control quantities.  Kept as a single
  category without sub-refinement for now.  The token hierarchy
  (`promo:parent`) allows refinement later without schema changes.

An index is essentially "what does this dimension enumerate?" — and the
answer can be a structural element (node/arc), a physical quantity
(token), a process (conversion), or an information quantity (signal).

### 3. Two arc types

**Physical arcs** — bidirectional
- Continuity conditions on flow and effort variables.
- Closely tied together (flow and effort are coupled).
- Both sides of the connection are equal partners.

**Information arcs** — unidirectional
- Output of one function is input to the next.
- Directly uses the corresponding variable (no continuity condition).
- Direction matters: source → target.

**Cross-domain interaction** (information → physical)
- Information inputs can manipulate physical flows (e.g. valves).
- Observations are done by something like an instrument (physical →
  information).
- This is an exception to the pure bidirectional/unidirectional split
  and crosses domain boundaries.

### 4. Domain tree dual role

The domain tree has two roles:

- **Semantic** — different top-level domains (physical vs control vs
  information) have different tokens and physics.  These are
  fundamentally different kinds of systems.
- **Structural** — subdomains within one physics domain share the same
  physical properties (same tokens, same variable classes).  The
  subdivision is mainly organisational and may provide a frame for
  special equations (e.g. boundary conditions, interface equations).

### 5. Arcs are model-level, not ontology-level

Arcs are not defined in the ontology editor.  Physical domain arcs
(continuity conditions) and information flow arcs (output = input) are
expressed as equations in the equation editor.  The actual graph
connections are drawn in the Modeller, which generates the linking
equations.  The ontology editor only needs to know which variable
classes / tokens can carry a flow.

### 6. Property functions are classification, not topology

Transformation functions (thermodynamic relations, geometric relations)
are **not network nodes**.  They are sub-routines called *within* a
capacity or transport computation.

The model network consists of:
- **Capacities** (dynamic state equations on nodes) — e.g. `dU/dt = ...`
- **Transports** (linking equations on arcs) — e.g. flow = f(effort₁, effort₂)

Each capacity or transport node's equations can be solved independently
(often parallelisable).  Property functions (e.g. `U → T`, `V → A`) are
function calls *inside* a node's equation, not separate nodes in the
network.

Two categories of property functions:
- **Thermodynamic relations** — conserved quantities (tokens: mass,
  energy, momentum) → effort variables and intensive quantities
  (T, P, μ, ...).
- **Geometry-related relations** — structural quantities (volume,
  length) → derived geometric quantities (area, hydraulic diameter).

The old ProMo attempt to put these in a separate domain was not clean
because it implied they were network elements with topology position.
They are reusable calculation steps, not network elements.

### 7. Hierarchical variable and equation classes

Variable classes and equation classes should be **hierarchical**, not
flat enums.  For example:

```
state
├── conserved          (U, M, P — fundamental quantities / tokens)
├── effort             (T, P, μ — derived from conserved via thermo)
├── intensive          (ρ, h, s — also derived from conserved)

transport
├── flow               (F, ṁ — arc quantities)
├── flux               (J — distributed transport)

property_function
├── thermodynamic
│   ├── energy_function
│   ├── equation_of_state
│   └── physical_property_relation
├── geometric
│   ├── area_relation
│   └── volume_relation
```

Benefits:
- Equation classification is more specific (e.g. `thermodynamic.energy_function`
  instead of just `generic`).
- Property function library can be queried by category.
- Behaviour branch inheritance works down the hierarchy.

Implications:
- `equation_class` becomes a path, not a flat string.
- Equation editor needs a tree-dropdown class picker.
- `promo:variable_class` and `promo:equation_class` become hierarchical
  resources (with `promo:parent`) rather than string literals.

### 8. Multiple classification axes

A single variable class hierarchy cannot capture the different ways
variables need to be classified.  A variable like `U` is simultaneously:
- `state` (role in the model — `dU/dt = ...`)
- `conserved` (physical nature — mass, energy, momentum)
- `extensive` (scales with system size)

And `T` is:
- `effort` (driving force for transport, contact geometry)
- `intensive` (doesn't scale with size)
- `derived` (computed from state via property function)

These are **orthogonal classifications** — overlapping but independent
dimensions.  A single tree cannot express that `U` is both `state` and
`conserved` and `extensive` without duplicating it in three branches.

The ontology should allow **multiple classification axes**, each
potentially hierarchical.  A variable carries one value per axis.

Example axes (thermo/transport domain):
- **Role**: state, effort, transport, ...
- **Physical nature**: conserved, intensive, extensive, ...
- **Origin**: fundamental (port variable), derived (computed), ...

### 9. Domain-dependent classification axes

The classification axes themselves are domain-dependent, not just the
values within them.  The axes above (role, extensivity, origin) are
shaped by thermodynamics and transport phenomena.  Other domains have
different needs:
- **Molecular modelling** — state might be positions and momenta;
  "effort" maps to forces; extensive/intensive may not apply.
- **Mechanical/fluid systems** — stress, strain rate, and other
  quantities play roles that don't fit the thermo taxonomy cleanly.

This reinforces the flexibility principle (§10): the ontology editor
should let the user define classification axes per domain, not impose
a fixed set.

### 10. Flexibility principle

The ontology structure should remain **flexible and user-defined**,
with minimal fixed imposition.  The editor provides:

- **A small fixed core** — IRIs, labels, the domain tree, the fact that
  variables have classifications, indices have token bindings,
  equations have classes.  These are scaffolding.
- **User-defined hierarchies** — variable class trees, equation class
  trees, token trees, classification axes.  The user defines the
  branches and leaves.  The editor provides the tree editor, not a
  fixed enum.
- **User-defined relationships** — which variable classes are valid in
  which domains, which equation classes produce which variable classes.
  These are constraints the user authors, not hardcoded rules.

The checker validates against the user's own definitions, not against
a fixed physics model baked into the code.

Rationale: the ontology editor was originally built to allow
experimentation with structure.  The design is still evolving (this
discussion has already produced the two-branch model, hierarchical
classes, multiple axes, property function distinction).  Freezing the
schema now would be premature.  Impose only the scaffolding; let the
user define the physics structure.

### 11. Event dynamic modelling

Event dynamics has not yet been discussed in detail.  This is a
distinct modelling paradigm that needs to be accommodated in the
ontology.  To be addressed in future sessions.

### 12. Book

The ontology design is working towards a book that documents the
ProMo modelling approach.  The ontology structure and the design
decisions recorded here will feed into that book.  To be kept in mind
as the design evolves.

## Resolved questions

1. **Variable classes per structural element** — **Resolved (Sep 12).**
   Variable classes are defined per structural element (node/arc) per
   domain.  Nodes carry the rich physics-specific variable classes
   (`state`, `effort`, `transport`, `property_function`, ...).  Arcs
   are simpler and more generic:
   - **Physical domain arcs**: continuity conditions (flow in = flow
     out, effort₁ = effort₂).  The arc's main role is the
     linking/transport equation.
   - **Information domain arcs**: input = output, unidirectional.  The
     arc passes a variable through.
   - **Exception**: where signals appear on a physical arc (e.g. a valve
     controlling flow), the arc carries both a bidirectional physical
     continuity and a unidirectional signal.

2. **Structure ↔ behaviour interaction** — **Resolved (Sep 12).**
   The structure branch IS the domain hierarchy.  It defines which
   tokens exist in each domain.  The behaviour branch defines variable
   classes per structural element within each domain, with
   inheritance.  The structural element type (node vs arc) and the
   domain (which tokens are present) together determine which variable
   classes are available.

3. **Node/arc indices: structural (model-level) or ontological?** —
   **Resolved (Sep 12).**  Ontological.  The graph approach (nodes and
   arcs) is fundamental to the modelling paradigm.  The concept that
   a variable can be indexed by node or arc is an ontological fact.
   The specific count (N=5) is model-level, determined at
   instantiation/meshing time.

4. **Time** — **Resolved (Sep 12).**  Time and space are **frame
   variables**, not indices.  They define the coordinate context of
   the model, consistent with the existing `frame` variable class.
   Specific time points or spatial positions are determined at
   instantiation/meshing time, not in the ontology.

## Open questions (remaining)

5. **Entity types** — **Resolved (Sep 12).**  Entity types are a
   combination of temporal and spatial abstraction, as defined in
   CWA 17960:2022 (the ModGra standard).  The ontology editor authors
   the entity type taxonomy; the Behaviour Linker assigns a specific
   type to a base entity.

   **Temporal — "triple domain" within a time scale:**
   - **Constant** — steady-state, algebraic
   - **Dynamic** — differential equations (ODE or PDE, depending on
     spatial)
   - **Event dynamic** — discrete events

   These three are strictly separated — behaviours in the gaps between
   them don't apply.  In a multi-scale model, at least two triple
   domains are stacked.  They interact at the "ends": the lower scale's
   **constant** becomes the larger scale's **event dynamic**.  Example:
   thermodynamics (constant at macro scale) is the result of
   microscopic computation (event dynamic at micro scale).  Triple
   domains do not overlap.

   **Physical capacities (nodes) — 5 types (CWA 17960 §4.1):**

   | Type | Temporal | Spatial | Size | Description |
   |------|----------|---------|------|-------------|
   | 4.1.1 | constant | uniform | infinite | Environment, sources/sinks, boundary conditions |
   | 4.1.2 | dynamic | uniform | finite | Lumped (ODE) |
   | 4.1.3 | dynamic | not uniform | finite | Distributed (PDE) |
   | 4.1.4 | event-dynamic | uniform | infinitesimal | Point — zero capacity, volume-like, can have reactions |
   | 4.1.5 | event-dynamic | not uniform | finite | Transport system — fast/infinite conductivity assumption |

   **Information capacities (nodes) — 3 types (CWA 17960 §4.2):**

   | Type | Temporal | Description |
   |------|----------|-------------|
   | 4.2.1 | constant | Provides constants |
   | 4.2.2 | dynamic | Dynamic information (e.g. integrating controller) |
   | 4.2.3 | event-dynamic | Instantaneous I/O transformation |

   **Spatial regimes (CWA 17960 §3.2):**
   - **Uniform** (lumped) — relevant characteristics not a function of
     spatial position → ODE
   - **Distributed** — relevant characteristics are a function of
     spatial position → PDE (1-3 spatial dimensions)
   - Size: infinite large, finite, or infinitesimal small

   **Special cases:**
   - **Point system** (4.1.4) — zero-size capacity, no spatial extent,
     seen as a volume.  Can host reactions (e.g. catalyst site, reaction
     point).
   - **Phase interface / intraface** — zero-size, no reactions, where
     continuity conditions are applied (effort equality, flow
     conservation).  This is an arc/boundary element, not a node element.

   **Important change from CWA 17960 to ProMo14:**
   In CWA 17960, the transport system was defined as the connecting arc.
   In ProMo14, this has changed:
   - The **transport system** is an **event-dynamic distributed node**
     (entity type 4.1.5), NOT an arc.  The transport *behaviour* lives
     in this node.
   - The **arc** is only the **intraface** — it carries continuity
     conditions (effort equality, flow conservation) and nothing else.
     The arc just says "these two ports are connected."
   - The CWA 17960 interface/intraface discussion was based on old ProMo
     and needs reinterpretation in the new architecture.

   **Key CWA 17960 definitions:**
   - **Token** — abstract item characterizing behaviour.  Physical:
     conserved quantities (internal energy, momentum, charge, mass) +
     balanced quantities with production (entropy, component mass in
     moles, granules).  Information: elementary pieces of information.
   - **Topology** — directed graph; nodes are token capacities; edges
     are arcs transporting tokens bidirectionally (direction is
     reference).
   - **Interface** — transfer of state information (physical → control,
     macro → molecular).
   - **Intraface** — transfer of state information between phases within
     a composite.
   - **Composite/surrogate** — conglomerate of elementary entities;
     surrogate is a model of a model (may not satisfy conservation
     principles).

   **Meshing** — distributed entities can be mapped into networks of
   lumped systems after model composition, before code generation.

   **Reference:** CWA 17960:2022, "ModGra — a Graphical representation
   of physical process models", CEN Workshop Agreement, December 2022.

6. **Variable class vocabularies per domain type** — **Resolved (Sep 12).**
   Variable classes are inherited down the domain tree and can be
   augmented (added to or specialised) in subdomains.  This is
   additive inheritance — a subdomain can add new classes or more
   specific sub-classes, but does not remove parent classes.

   The two main branches naturally get different base vocabularies:
   - **physical**: `state`, `effort`, `transport`, `frame`,
     `constant`, `parameter`, ... (extended by `thermo`, `mechanical`,
     etc.)
   - **information**: `state`, `input`, `output`, `constant`,
     `parameter`, ... (extended by `control`, `computation`, etc.)

   No separate fixed mapping per domain type is needed — the
   inheritance mechanism handles it.

7. **Event dynamics** — **Resolved (Sep 12).**  Event dynamics fits
   within the existing ontology taxonomy — no special ontological
   concepts needed.

   - **Event observer** = information capacity, event-dynamic (§4.2.3),
     instantaneous I/O transformation.  Its trigger condition (boundary
     crossing) is a *behaviour* defined through equations, not an
     ontology type.
   - **Sampler** = same entity type, different equations (fixed time
     interval trigger).
   - **Zero-order hold** = same entity type, different equations
     (piecewise constant output).
   - **Automaton** = an information processing representation of the
     physical plant.  It is a model, not a new entity type.
   - Event-dynamic *physical* capacities (4.1.4 point, 4.1.5 transport
     system) are already in the physical branch.
   - The bridging elements (observer, hold) are already in the
     information branch.
   - The connection between them is covered by connection rule type 3
     (signal connections).
   - The non-uniqueness of automaton transitions is a mathematical
     property of the equations, not an ontological distinction.  The
     equation editor handles it; the ontology just needs to know it is
     an event-dynamic information processing element.

   **Analogy: sampled vs. event-discretised systems:**

   | | Sampled (time-triggered) | Event (boundary-triggered) |
   |---|---|---|
   | Discretiser | Sampler (fixed time interval) | Event observer (triggers when state crosses a boundary) |
   | Return path | Zero-order hold (piecewise constant) | Zero-order hold (piecewise constant) |
   | Result | Discrete-time signal | Event-discretised signal |
   | Plant model | Continuous + discrete hybrid | Automaton (non-unique transitions) |

   - Continuous/analogue control is not excluded — standard time
     integration.
   - Sampled systems: sampler produces discrete signals, zero-order
     hold for manipulated variable back to continuous plant.  Standard
     for digital control.
   - Event observer: analogous to sampler, but triggers on boundary
     crossing (not fixed time interval).  Zero-order hold for return
     signal.
   - Event-discretised plant: can build an automaton representation,
     but transitions are **not unique** — state-space discretisation
     loses information.  The mathematics exists and could be built into
     the info processing system.
   - Both sampler and event observer are **information processing
     elements** (information branch, entity type §4.2.3 event-dynamic).
   - The connection between observer and continuous plant is an
     information arc (observation: physical → information; return:
     information → physical via zero-order hold).

   **Remaining work is equation-level** (equation editor and behaviour
   linker), not ontology-level: defining observer, hold, and automaton
   behaviours.

8. **Classification axis definition** — **Resolved (Sep 12).**
   Classification axes are per-domain with inheritance (same as
   variable classes).  The user defines axes at the level where they
   are meaningful; subdomains inherit them.

   **Variable class becomes the "role" axis.**  The current
   `variable_class` field dissolves into one axis ("role") among
   several.  Each axis is a hierarchical list of terms.  The user tags
   each variable with one term per axis.

   **Tagging is the primary mechanism**, with optional user-defined
   validation rules (e.g. "in domain `thermo`, if origin=derived then
   extensivity must be intensive").  These are user-authored
   constraints, not built-in physics — consistent with the flexibility
   principle.

   **Reducing clicking — inferred defaults:**
   The system proposes axis values based on context, and the user
   confirms or adjusts:
   - **Domain defaults** — variables created in domain `thermo` get
     domain-specific default axis values.
   - **Equation class inference** — if a variable is the LHS of a
     `d/dt` equation, "role" defaults to `state`.  If produced by a
     `thermodynamic.equation_of_state` equation, "origin" defaults to
     `derived`.
   - **Token binding inference** — if bound to `energy` token,
     "extensivity" defaults to `extensive` (conserved quantities are
     extensive).
   - **Bulk tagging** — select multiple variables, assign an axis
     value to all at once.

   Most variables need zero or one click; only unusual cases need
   manual tagging.

9. **Connection rules** — **Resolved (Sep 12).**  Three connection
   rule types:

   1. **Same domain, shared tokens** — physical arc (bidirectional,
      continuity).  Valid iff both nodes share at least one token.
   2. **Different physical domains, shared tokens** — physical arc
      (bidirectional, continuity).  E.g. liquid-gas interface where
      mass and energy are conserved across the boundary.
   3. **Signal connections** — information arc (unidirectional):
      - Physical → information: observation (instrument reads a
        physical quantity).
      - Information → physical: manipulated variable (control output
        to a valve/actuator or coefficient in transport equation).
      - Within information domain: control signal to control signal.
      - Within a physical domain: token signal (if a physical domain
        also carries a signal token).

   **Continuity is token-specific.**  An arc connecting two nodes
   carries continuity only for the tokens they share.  If two phases
   share `mass` and `energy` but not `momentum`, the arc enforces
   continuity on mass flow, energy flow, and their respective effort
   variables, but not on momentum.

   **Valve modelling — two abstraction levels:**
   - **Valve as physical entity** — modelled with its own mechanics
     (dynamic, lumped or distributed).  It is a physical node with its
     own state equations.  The control signal manipulates a parameter
     (e.g. valve position) via an information arc.
   - **Valve as coefficient** — not modelled as a separate entity.  The
     control signal directly modifies a coefficient in the transport
     equation (e.g. flow resistance).  Event-dynamic, no physical
     node.

   The ontology should not prescribe which abstraction — it allows
   the modeller to choose the entity type (physical node vs. parameter
   abstraction).  This is consistent with the flexibility principle
   (§10).  Mechanical device modelling (valves, pumps, actuators) at
   different abstraction levels has not been analysed in detail — to
   be revisited.

   **Domain tree structure:**

   ```
   root
   ├── physical
   │   ├── thermo
   │   │   ├── liquid
   │   │   ├── gas
   │   │   └── ...
   │   ├── mechanical
   │   ├── electrical
   │   └── ...
   └── information
       ├── control
       │   ├── feedback
       │   ├── logic
       │   └── ...
       ├── computation
       └── ...
   ```

   Two main branches: **physical** (tokens = conserved/balanced
   quantities) and **information** (tokens = elementary information
   pieces).  Control is a subdomain of information, not a peer of
   physical.  This maps to the CWA 17960 distinction: physical
   capacities (§4.1) vs information capacities (§4.2).

---

## Session 2026-09-13: Scales, graphical language, and glasses

### 13. Scales as a first-class concept

Time scale and length scale are not variable classification axes
(§8).  Axes classify variables (role, extensivity, origin).  Scales
classify **base entities** — they define the temporal and spatial
context in which an entity type operates.

The temporal triple domain (constant / dynamic / event-dynamic) lives
**within a time scale** (§5).  Multi-scale models stack triple domains:
the lower scale's constant becomes the larger scale's event-dynamic.
Without explicit scale definitions, entity types cannot be properly
grounded.

**Decision:** Scales become a first-class concept in the ontology
editor, sitting between classification axes and entity types in the
staged workflow.

A scale is a **dimension** (time scale, length scale, or
user-defined) with a hierarchical tree of values (like classification
axes).  Entity types become **compositions of scale values** rather
than hardcoded CWA 17960 fields.  CWA 17960's temporal×spatial becomes
a seed/default, not a schema.

**Staged workflow (revised):**
1. Tokens — no dependencies
2. Domains — depend on tokens
3. Classification axes + terms — per domain, for variable classification
4. Scale dimensions + values — time scale, length scale, user-defined
5. Entity types — compositions of scale values
6. Indices — reference tokens + domains
7. Connection rules — reference domains + tokens (come last)

### 14. Graphical language — ontology as a visual vocabulary

CWA 17960's ModGra was an early version of what evolved into ProMo.
Its development started in 1986.  The idea of graphically representing
ontology entities (and a bit further down towards entity declaration)
was very useful for working with models without writing equations.

**Extending the principle:** every ontology entity gets a graphical
representation — not just nodes and arcs, but tokens, domains, scales,
entity types, connection rules.  Each has a visual symbol.

**Paper/pencil modelling:** the symbols carry enough semantic meaning
that a sketch is already a partial model specification.  This is
design thinking, not just documentation.  It was called "playing" —
very useful for explaining processes to people, documenting processes
and experiments.  A versatile tool.

**Tight software integration:** the same symbols appear in the
Modeller, so there is no translation gap between paper and screen.
What you draw by hand is what you'd draw in the tool.

**Generic document domain:** the graphical language becomes a
documentation standard, possibly its own information domain in the
ontology.  To be discussed more later.

The ontology editor is not just defining a data model — it is defining
a **visual language**.  When you define an entity type, you also
define how it looks.  When you define a connection rule, you define
how things can be drawn together.  The graphical representation is
part of the ontology, not an afterthought applied by the Modeller.

### 15. Glasses — one model, many views

Base entities have **one canonical graphical representation** (the
ontology-level symbol for paper/pencil work).  However, once building
models in ProMo, users want to put on different **glasses** to see the
model in a graphical representation familiar to their working domain:

- Chemical process engineer: P&ID symbols (distillation columns,
  tanks, valves)
- Medical researcher: anatomical organ graphics
- Brain modeller: neural/vascular tissue representations
- Control engineer: block diagrams
- All looking at the **same** underlying entities and connections

**Glasses are domain-specific skins** applied at the Behaviour Linker
or Modeller level.  They are themselves ontology artefacts — a
"chemical engineering glasses" set maps entity types to P&ID symbols;
a "medical glasses" set maps them to anatomical graphics.  They are
reusable, shareable, and user-defined.

This is distinct from ADR-003's multiple views (pan/zoom of the same
representation).  Glasses are a different dimension: same model,
different visual vocabulary entirely.

The framework is very generic and can accommodate various modelling
domains.  Example: a friend models flow and diffusion processes in
human brains — the same underlying graph-based modelling paradigm,
completely different visual vocabulary.

### 16. Implications for the ontology editor

The ontology editor becomes a **language design tool**:
- Defines the vocabulary (tokens, domains, scales, entity types,
  rules)
- Defines the visual representation of each vocabulary element
- Defines the "glasses" mappings (domain-specific visual skins)
- Everything downstream (equation editor, behaviour linker, modeller,
  code generation) consumes this language

The flexibility principle (§10) becomes even more important: if the
ontology defines a visual language, it must be general enough to
support domains we haven't thought of yet.  Hardcoding CWA 17960's
five physical entity types would be like hardcoding a single
alphabet.

### 17. Downstream coupling — to be verified

Need to check how tightly the Behaviour Linker and code generation are
coupled to the current CWA 17960 entity type schema:
- If the Behaviour Linker is already ontology-driven, generalizing is
  clean
- If it has hardcoded assumptions (e.g. "dynamic/uniform/finite →
  ODE"), that logic needs to become configurable
- Code generation's special handling for entity types may need to
  become rule-based rather than hardcoded

### 18. CWA 17960 in perspective

CWA 17960 should be seen as an early version of what evolved into
ProMo.  Its development started in 1986.  The graphical representation
idea was very useful for working with models without writing
equations.  ProMo14 generalizes and extends this approach.

### 19. Three-level graphics model

Graphics are not defined in one place.  There are three levels, each
owned by a different module in the pipeline:

**Level 1 — Abstract symbol (Ontology Editor)**
- A sketchable glyph for paper/pencil work.  "A capacity is a box."
  "A transport is an arrow."
- Part of the visual **language definition**.  Minimal, generic,
  domain-agnostic.
- Needed before any software is opened — for sketching, explaining,
  documenting.
- Lives in the ontology because it is part of the vocabulary, not the
  behaviour.

**Level 2 — Concrete base graphic (Behaviour Linker)**
- The software-rendered graphic for a specific entity type.
  "A lumped capacity is a box with rounded corners, labelled with its
  variable class."
- Assigned together with equations — the Behaviour Linker bridges the
  abstract ontology and the concrete model.
- This is what the Modeller renders for base entities by default.
- Authored in the spawnable Graphic Object Editor (ADR-004), serving
  the Behaviour Linker.

**Level 3 — Composite / tailored graphic (Modeller)**
- Custom graphics for composed entities.  "This specific arrangement
  of capacities and transports is displayed as a distillation column
  icon."
- Model-level tailoring.  A composite is a sub-model; its graphic
  replaces the cloud of base entity symbols with a single domain-
  specific symbol.
- Authored in the spawnable Graphic Object Editor, serving the
  Modeller.

**Dependency chain:** entity type (ontology) → abstract symbol
(ontology) → concrete base graphic (Behaviour Linker) → composite
graphic (Modeller).  A graphic is only defined once the entity is
defined.

### 20. Glasses — separate artefact, separate authoring

Glasses are **domain-specific visual skins** that override concrete
graphics (levels 2 and 3) with domain-specific alternatives.  They
are:

- **Not ontology** — no new entities, just visual mappings.
- **Not behaviour** — no equations.
- **Not model-level** — not about a specific model instance.
- A **cross-cutting visual concern**: a mapping table from entity
  types to visual representations, for a specific domain perspective.

Glasses are stored separately, in their own RDF named graph.  Their
definition is a completely different task from ontology authoring,
behaviour linking, or model building.  A glasses set is authored by a
domain expert who knows "what a distillation column looks like in
chemical engineering" or "what a blood vessel looks like in medicine."

The Modeller is the primary **consumer** of glasses — it is where
users put them on.  But the Modeller does not own glasses authoring;
it only applies glasses and lets users switch between them.

### 21. Revised pipeline with graphics allocation

```
Ontology Editor
  └─ entity types + abstract symbols (sketchable glyphs, level 1)

Behaviour Linker
  └─ equations + concrete base graphics (per entity type, level 2)

Glasses (separate artefact, separate authoring, separate graph)
  └─ entity type → domain-specific visual mapping (overrides levels 2–3)

Modeller
  └─ consumes base graphics (level 2)
  └─ applies glasses (switch visual vocabulary)
  └─ authors composite / tailored graphics for sub-models (level 3)
```

The spawnable Graphic Object Editor (ADR-004) serves both the
Behaviour Linker (level 2) and the Modeller (level 3).

### 22. Documentation discipline

These decisions feed into a longer-run publishable document, possibly
a book documenting the ProMo modelling approach.  It is essential
that:

- Design decisions are documented carefully and in sequence.
- Existing documentation is reviewed for consistency so that future
  work does not derail.
- The design discussion document remains the single source of truth
  for ontology design decisions, with downstream docs (overview,
  design, data model) updated to reflect converged decisions.

### 23. Graphic Object Editor — separate software module

The Graphic Object Editor (ADR-004) is a **shared software module**,
not a pipeline stage.  It is spawned by:

- **Behaviour Linker** — to author level-2 concrete base graphics for
  entity types.
- **Modeller** — to author level-3 composite/tailored graphics for
  sub-models.

It is a separate piece of code in the monorepo, with its own
architecture, data model, and persistence format.  Its internal
design has not yet been discussed in detail.  Open questions:

- What is its internal data model for graphical definitions?
- How does it persist graphics (RDF?  SVG?  JSON?)
- How does it handle the different spawning contexts (level 2 vs
  level 3)?
- Does it need to know about glasses, or are glasses applied
  downstream of it?

To be addressed when the Behaviour Linker or Modeller needs it.

### 24. Documentation review (2026-09-13)

Reviewed and updated the following docs for consistency with the
converged design decisions:

- `docs/ontology-editor-overview.md` — removed variables/equations
  from scope; added classification axes, scales, entity types,
  connection rules, abstract symbols; updated module interactions;
  added three-level graphics model and glasses as separate artefact.
- `docs/ontology-editor-design.md` — complete rewrite: replaced
  variable-centric three-pane layout with staged workflow (7 stages);
  added sections on abstract symbols, three-level graphics, glasses;
  removed equation editor modal and user function registration.
- `docs/suite-overview.md` — updated stage 1 description; updated
  stage 3 to mention level-2 graphics; updated data flow diagram;
  added glasses as separate artefact; clarified EquationContext
  contract.
- `docs/ontology-data-model.md` — added scope note that the doc
  covers the var/expr schema (shared with equation editor) but not
  yet the newer ontology concepts (scales, axes, entity types,
  rules, abstract symbols).

### 25. Triple domain as scale values (Option B) — 2026-09-13

**Decision:** The temporal triple domain (constant / dynamic /
event-dynamic) is not a separate field on entity types.  It lives
**within** the time scale hierarchy as child values of each scale
level.

**Structure:**

Time scale dimension — each level has three triple-domain children:
```
molecular
  ├── constant
  ├── dynamic
  └── event-dynamic
nano
  ├── constant
  ├── dynamic
  └── event-dynamic
milli
  ├── constant
  ├── dynamic
  └── event-dynamic
macro
  ├── constant
  ├── dynamic
  └── event-dynamic
```

Length scale dimension — each level has spatial sub-values:
```
infinitesimal
  ├── point (zero-size)
  └── finite (small)
microscopic
  ├── uniform
  └── distributed
macroscopic
  ├── uniform
  └── distributed
infinite
  └── uniform
```

**Entity types** are pure compositions of fine-grained scale values.
Example: "lumped capacity" = `macro/dynamic` (time) +
`macroscopic/uniform` (length).  The legacy `temporal_type` /
`spatial_type` / `spatial_size` fields are kept for backward compat
but the canonical definition is the scale value composition.

**Multi-scale stacking:** The lower scale's constant becomes the
larger scale's event-dynamic.  This is encoded in the hierarchy:
`molecular/constant` is a child of `molecular`; at `nano` scale,
`molecular/constant` appears as instantaneous (= event-dynamic).

**Multi-scale models:** A model simply contains entities at different
scale levels, connected by arcs.  The ontology does not need to do
anything special — connection rules (stage 7) determine which entity
types can connect.  The multi-scale stacking is a semantic
interpretation handled by the Behaviour Linker and code generation,
not a structural constraint in the ontology.

**Behaviour Linker role:** Assigns a specific scale level to a base
entity.  The entity type defines which scale values are valid; the
Behaviour Linker picks the concrete level.

**Scale values are seeds, not fixed.** The user can rename, restructure,
add, or delete scale levels and their children.  The seed uses
molecular / nano / milli / macro for time and infinitesimal /
microscopic / macroscopic / infinite for length, but these are
editable defaults.
