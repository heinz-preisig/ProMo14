# Behaviour Linker — Design Discussion

Started 2026-09-13.

## 1. Purpose (rough first view)

The Behaviour Linker (BL) bridges the ontology and the equation knowledge graph.
Its job:

1. **Read the ontology** — entity type definitions (including scale values,
   domains, tokens, connection rules), plus whatever additional information
   the design will require.
2. **Read the var/expr knowledge graph** — the bipartite graph of variables
   and equations produced by the Equation Editor.
3. **Generate a subgraph** of the var/expr bipartite graph, via **user
   selection under tight control** — i.e. the user decides which equations
   apply to which entity types, and the BL validates/enforces consistency.

The output is an assignment: which equations describe the I/O behaviour of
each entity type, together with graphics assignments.

## 2. What the BL consumes

### 2.1 From the ontology (`ontology.trig`)

- **Entity types** — `promo:EntityType` with `promo:hasScaleValue` links
  (canonical definition), legacy `temporalType`/`spatialType`/`spatialSize`
  fields, `promo:branch` (physical/information).
- **Scale dimensions + values** — `promo:ScaleDimension`, `promo:ScaleValue`
  with hierarchical `promo:parent` links. Entity types are compositions of
  fine-grained scale values.
- **Domains** — `promo:Domain` tree with `promo:hasToken` bindings.
- **Tokens** — `promo:Token` hierarchy.
- **Connection rules** — `promo:ConnectionRule` (physical-same,
  physical-cross, signal).
- **Classification axes + terms** — `promo:ClassificationAxis`,
  `promo:AxisTerm` hierarchies. Variables carry `promo:axisValue` tags.
- **Equation classes** — `promo:EquationClass` hierarchy (generic,
  instantiate, balance, empirical, user_function, ...).

### 2.2 From the equation editor (var/expr named graph)

The var/expr graph is a **bipartite graph**:

- **Variables** (`promo:Variable`) carry:
  - `promo:label`, `promo:internalID`, `promo:network` (domain)
  - `promo:axisValue` → axis term IRIs (classification tags)
  - `promo:carriesToken` → token IRIs
  - `promo:unitVector` (8-element SI exponent vector)
  - `promo:indexStructure` → index IRIs
  - `promo:variableClass` (legacy string, being replaced by classifications)
  - `promo:hasEquation` → equation IRIs (the bipartite edges)

- **Equations** (`promo:Equation`) carry:
  - `promo:lhs` → the variable IRI being defined
  - `promo:rhs` → expression token stream (string)
  - `promo:incidenceList` → list of variable IRIs appearing in the RHS
    (JSON array literal — this is the other side of the bipartite edge)
  - `promo:equationClass` → IRI of `EquationClass` node
  - `promo:network` — expression definition network

So the bipartite structure is:

```
Variable ──hasEquation──▶ Equation
Equation ──lhs──────────▶ Variable (defined variable)
Equation ──incidenceList─▶ [Variable, Variable, ...] (RHS variables)
```

## 3. What the BL produces

(To be refined. First approximation:)

- An **assignment artefact**: for each entity type, a selected set of
  equations (a subgraph of the var/expr bipartite graph) that describes
  the I/O behaviour of that entity type.
- **Graphics assignments**: which concrete base graphic (Level 2 in the
  three-level graphics model) is assigned to each entity type.
- The assignment is itself an RDF named graph (separate from ontology
  and var/expr graphs).

## 4. Core design questions

### Q1: What is the unit of selection?

Options:
- **Per entity type**: user selects which equations apply to each entity
  type. Scale values determine which equations are *eligible*.
- **Per variable class**: user selects equations per variable role
  (state, effort, transport, ...) within an entity type.
- **Per equation class**: user assigns equation classes (balance,
  empirical, ...) to entity types, and the BL resolves which concrete
  equations match.

### Q2: What does "tight control" mean?

The old ProMo lesson: don't put application behaviour in ontology
definitions. The BL should enforce:
- **Structural consistency**: selected equations must have compatible
  variables (units, index structures, tokens, domain).
- **Completeness**: the selected equation set must fully describe the
  entity type's I/O (no missing state equations, no dangling references).
- **Scale consistency**: equations must be compatible with the entity
  type's scale values (e.g. a distributed entity needs PDE-type equations,
  not ODE-type).

But the BL should **not** hardcode "dynamic/uniform/finite → ODE".
The mapping from scale values to equation types should be configurable,
not embedded in BL logic.

### Q3: Where does the mapping logic live?

- **In the BL itself** (as configurable rules)?
- **In a separate assignment artefact** (RDF named graph, user-editable)?
- **In the ontology** (as additional predicates on entity types)?

The old ProMo temptation was putting behaviour in the ontology. The
correct approach is likely: the mapping lives in the **assignment
artefact**, which is a separate RDF graph. The BL is the editor for
this artefact, not the logic itself.

### Q4: What is the BL's relationship to the Modeller?

The Modeller instantiates entity types as model nodes. The Modeller
should **not** know about equations — it builds only on entity types,
connection rules, and graphics. Equation information stays in the BL's
assignment artefact and is consumed downstream by code generation, not
by the Modeller.

The Modeller does not query the var/expr graph directly.

> **Note (2026-09-13):** Keeping equations out of the Modeller may
> become sticky when we talk about connections — arcs may need to know
> something about the equations that define continuity conditions.
> To be discussed later.

### Q5: What additional ontology pieces might the BL need?

Possibly:
- **Port/interface definitions** — which variables are inputs, outputs,
  or bidirectional for a given entity type. Currently the ontology has
  `EntityInterfaceDefinition` in `packages/semantic/src/contracts.ts`
  but it's not populated from the RDF graph yet.
- **Variable role bindings** — which variable roles (state, effort,
  transport) apply to which entity types. Currently implicit in
  classification axis tags on variables.
- **Equation applicability constraints** — metadata on equations
  indicating which scale values or entity types they are eligible for.
  Currently equations have `equationClass` but no scale-value constraints.

## 5. Old ProMo lessons (to avoid)

1. **Don't put application behaviour in ontology definitions.** The
   ontology defines what entities exist, not what they do. The BL is the
   mapping layer.
2. **The BL was rewritten ~10 times.** Main cause: scope creep and
   mixing concerns. Keep the BL focused: it selects equations for
   entity types. It does not generate code, it does not validate
   physics, it does not assign parameters.
3. **Configurable, not hardcoded.** Any mapping from entity type
   properties to equation types must be user-editable, not baked into
   BL logic.

## 6. "State" — required concept or user-defined? (2026-09-13)

### The tension

System theory and thermodynamics are built on the concept of state: a
node has state variables, and state equations describe how state evolves.
Without "state," you can't write balance equations, can't check
completeness, can't generate ODEs/PDEs.

But the flexibility principle says: don't impose fixed concepts. Variable
classes are user-defined axis terms. If we require "state," we're baking
physics into the ontology — the old ProMo trap.

### Where does the requirement live?

Two options:

1. **"State" required in the ontology** — the ontology enforces that
   every physical entity type must have state variables. This is the
   trap: the ontology now contains physics knowledge. If someone models
   a domain where "state" isn't the right concept (algebraic constraints,
   event-driven systems), the ontology blocks them.

2. **"State" required in the BL** — the BL needs *some* concept of "the
   variables that describe this entity's condition" to select equations
   and check completeness. But it gets this concept from the user's own
   classification axes, not from a hardcoded "state" concept. The BL
   requires that *some* axis marks which variables are the "defining"
   variables, but it doesn't care what you call them.

Option 2 seems right: the BL requires a **structural role** — "which
variables describe this entity's condition" — but gets it from the
user's classification, not from a hardcoded "state" concept.

### Deeper question: does the BL need "state" at all?

If the BL's job is purely "select equations for entity types," then it
may not need to know about state — it just selects equations. The concept
of "state" would then live in:

- **The equation editor** — where the user writes balance equations that
  define state variables (the LHS variable of a balance equation is
  implicitly a state variable).
- **Code generation** — which needs to know which variables to integrate
  (state variables) vs. which are algebraic (effort, transport).

The BL might only need to know: "this equation is a balance equation for
this entity type." Whether the LHS variable is called "state" is a
classification concern, not a BL concern.

### Resolution (2026-09-13)

The BL does **not** need to know about "state" explicitly — it can be
**implied**.

"State" is a system-theory concept, more generic than just thermodynamics
but ultimately derived from physics. It is not a hardcoded ontology
requirement. Instead:

- The user selects a **state-defining equation** as the first equation
  added to an entity type's behaviour description. The LHS variable of
  that equation is implicitly the state variable.
- This selection is the **control mechanism**: by choosing a
  state-defining equation, the user anchors the entity's behaviour.
- From that anchor, the BL selects the **lower-triangular subgraph** of
  the var/expr bipartite graph — i.e. all equations that are reachable
  from the state-defining equation's incidence list, transitively,
  forming a closed set with no undefined variables (except inputs/ports
  and parameters).

This means:
- "State" is not a label on a variable — it is an emergent property of
  which equation the user selects first.
- The BL does not validate "do you have a state?" — it validates "is
  the selected subgraph closed?" (no dangling variable references).
- The concept of "state" lives in the user's modelling knowledge, not in
  the ontology or the BL logic.

This avoids the trap: the ontology doesn't require "state" as a concept,
and the BL doesn't hardcode it. But the user's selection of a
state-defining equation provides the anchor from which the rest of the
behaviour description is built.

### The intrinsic trap (2026-09-13)

There is an intrinsic trap here. One is tempted to declare a variable
type "state" in the ontology (as a classification axis term) in an
attempt to make things fit the application domain — i.e. to tell the
system "this is a state variable" at the ontology level.

But the BL can then **implicitly define another variable as the actual
state** for a particular entity type, through the selection of a
state-defining equation. The LHS of that equation becomes the state
variable for that entity, regardless of what the ontology classification
says.

So there are two notions of "state":

1. **Ontology-level "state"** — a classification axis term tagging a
   variable as a state-type variable. This is a *template* concept: "in
   this domain, variables of class 'state' are the ones that describe
   system condition." It's a hint, a default, a convenience.

2. **BL-level "state"** — the LHS variable of the equation the user
   selects as the state-defining equation for a specific entity type.
   This is the *actual* state for that entity. It may or may not match
   the ontology-level tag.

The trap is conflating the two. If the ontology says "variable V is a
state variable" and the BL treats that as binding, then the ontology is
dictating behaviour — the old ProMo mistake. If the BL ignores the
ontology tag and lets the user pick any equation's LHS as the state,
then the ontology tag is just a hint.

The resolution: the ontology classification is a **hint** (default
suggestion), not a constraint. The BL's state-defining equation
selection is the **binding** act. The user can override the hint.

This also means: the same variable can be state for one entity type and
non-state for another. "State" is not a property of a variable; it is a
property of the variable's *role in an entity type's behaviour
description*.

### Transport — same pattern (2026-09-13)

The same pattern applies to **transport**. Transport variables are the
binding elements between nodes — they describe what flows through arcs.

- **Ontology-level "transport"** — a classification axis term tagging a
  variable as a transport-type variable. A hint: "in this domain,
  variables of class 'transport' are the ones that carry flow between
  nodes." Useful for defaults and UI suggestions.

- **BL-level "transport"** — the LHS of the equation the user selects as
  the transport-defining equation for a specific entity type. This is
  the *actual* transport variable for that entity. It may or may not
  match the ontology tag.

The same trap applies: if the ontology says "variable Q is a transport
variable" and the BL treats that as binding, the ontology is dictating
behaviour. The ontology tag is a hint; the BL selection is the binding.

### General pattern: ontology tags are hints, BL selections are bindings

This generalises to all variable roles — state, transport, effort,
frame, parameter, etc.:

- The ontology defines **what roles exist** (via classification axes and
  terms) and **which variables carry which role tags** (via
  `promo:axisValue`). These are template-level hints.
- The BL **binds** specific variables to specific entity types through
  equation selection. The role a variable plays in an entity's behaviour
  is determined by which equation is selected, not by the ontology tag.
- The user can override any hint. The same variable can play different
  roles in different entity types.

This keeps the ontology as a **vocabulary/framework** (what roles are
possible) and the BL as the **assignment** (what role each variable
actually plays for each entity type).

### Consequence: choose variable classes wisely (2026-09-13)

A lesson that follows from the hint/binding distinction: the ontology
designer is advised to choose variable classes **wisely** — where
"wisely" means consistent with the world that is being modelled.

If the ontology defines a "state" role on the classification axis, the
BL can use it as a hint to suggest state-defining equations. If the
classification is poorly chosen (e.g. "state" is missing, or roles don't
match the modelling domain), the hints are useless and the user must do
everything manually in the BL.

So the ontology's classification axes are not arbitrary — they should
reflect the modelling domain's structure. But they are still hints, not
constraints. The BL can function without them; it just works better when
they are well-chosen.

This is consistent with the flexibility principle: the ontology *can*
define any roles it wants, and the BL *works* with whatever is defined.
But good ontology design makes the BL's job easier.

## 7. Open questions (to be resolved)

1. **Unit of selection** — per entity type, per variable class, or per
   equation class? (Q1)
2. **Assignment artefact structure** — what does the RDF named graph
   look like? What predicates?
3. **Interface/port definitions** — does the BL need these, and should
   they come from the ontology or from the equation editor?
4. **Equation eligibility metadata** — should equations carry scale-value
   constraints, or should the BL infer eligibility from variable
   classifications?
5. **Validation scope** — what does the BL validate, and what is
   deferred to code generation / instantiation?
6. **Graphics assignment** — is this a BL responsibility or a separate
   step? (The three-level graphics model says Level 2 concrete base
   graphics are assigned in the BL, but the Graphic Object Editor is a
   separate module.)
7. **Mathematical role classification** — does the BL need to know about
   dependent/independent/input/parameter roles, or is that determined by
   the equation subgraph structure? (See §8.)
8. **PDAE → ODAE meshing** — where does meshing live? (See §8.)

## 8. The mathematics domain (2026-09-13)

There is one more larger concept domain to be included: the
**mathematics**.

### What the mathematics concerns

Once a model is assembled in the Modeller, it is a large
multi-dimensional **PDAE** (partial differential-algebraic equation) or
**ODAE** (ordinary differential-algebraic equation) system, to be solved
by integrating over time and space.

The mathematics domain introduces classifications that the BL (or
downstream code generation) needs:

- **Dependent variable** — a variable whose value is determined by the
  equation system (the unknowns being solved for).
- **Independent variable** — time, space (frame variables). These are
  the integration domains.
- **Input** — a variable whose value comes from outside the entity
  (from a connected entity or from the environment). The entity's
  equations treat it as given.
- **To be instantiated** — a parameter: a variable whose value is fixed
  at instantiation time, not determined by the equation system.

### Where does this classification live?

Following the hint/binding pattern from §6–7:

- **Ontology-level**: the classification axes can include a "mathematical
  role" axis with terms like dependent, independent, input, parameter.
  These are hints — they tell the BL and code generation what to expect.
- **BL-level**: the actual mathematical role of a variable for a specific
  entity type is determined by its position in the selected equation
  subgraph:
  - The LHS of a state-defining equation → dependent variable (integrated)
  - A variable in the incidence list with no defining equation in the
    subgraph → input (comes from outside)
  - A variable flagged for instantiation → parameter
- **Code generation**: resolves the final mathematical structure — which
  variables are integrated (state), which are algebraic (effort,
  transport), which are inputs, which are parameters.

### Resolution: BL mechanics (2026-09-13)

The BL does **not** need to distinguish between PDAE and ODAE — that is
a numerical issue, not a BL concern.

The dependent/independent distinction is handled by the BL's core
mechanic, which was already implemented in a past version of the BL:

> Once one defines a base equation, all that is on the RHS is input to
> the equation and must either be defined by another equation or
> instantiated.

This means the BL's algorithm is:

1. User selects a **base (state-defining) equation** for an entity type.
2. Every variable on the RHS of that equation is an **input** to it.
3. Each input must be **resolved**: either
   - another equation in the var/expr graph defines it (the user selects
     that equation too, and it becomes part of the subgraph), or
   - it is **instantiated** (it's a parameter — value set at
     instantiation time), or
   - it comes from **outside** the entity (a connected entity provides
     it — this is a port/input).
4. Repeat recursively: each newly selected equation has its own RHS
   variables, which must be resolved the same way.
5. The subgraph is **closed** when every RHS variable in every selected
   equation is either defined within the subgraph, instantiated, or
   declared as an external input.

This is the **lower-triangular subgraph** construction from §6: starting
from the base equation, the BL builds downward through the incidence
list, and the user controls which equations are selected to resolve
each input.

### The loop via state equations (2026-09-13)

Note that this approach forms a **loop** via the state equations. The
state-defining equation is the starting point, but the state variable
it defines also appears on the RHS of other equations (e.g. a property
equation that depends on state). Those equations' outputs may feed back
into the state equation's RHS (e.g. a transport flux depends on a
property, which depends on state, and the flux appears in the state
balance).

**Only cycles via the state equation are allowed — nothing else.**
This is actually the root of defining "state": the state equation is
the one equation in the subgraph whose LHS variable feeds back into
its own RHS (transitively). All other equations must be acyclic —
their LHS variables do not appear (transitively) on their own RHS.

So the subgraph structure is:

```
state equation:  dU/dt = f(inputs, transport, properties, ...)
transport eq:    transport = g(effort, properties, ...)
property eq:     property = h(state, ...)
```

The state equation defines U. The property equation depends on U.
The transport equation depends on the property. The state equation
depends on the transport. This is a cycle — but **only through the
state equation**. The transport equation does not cycle back to
transport. The property equation does not cycle back to property.

This loop is **resolved by integration**: the state equation is
integrated over time given initial conditions. At each time step, the
state is known (from the integrator), so the property and transport
equations are algebraic (they can be evaluated given the current state),
and the state equation's RHS can be computed for the next step.

So the BL's subgraph is **closed** in the sense that every variable is
either:
- **Defined by an equation** in the subgraph (state, transport,
  property, effort, ...), or
- **Instantiated** (parameter), or
- **External** (input from connected entity or environment).

But the subgraph contains a loop through the state variable, which is
broken by the integrator. The BL does not need to solve the loop — it
just needs to ensure the subgraph is closed (no undefined variables).
The numerical solver handles the loop at runtime.

### Two equivalent views of "state" (2026-09-13)

There are two equivalent ways to identify the state variable:

1. **Structural (graph-theoretic)**: the state equation is the one whose
   LHS variable transitively feeds back into its own RHS. The cycle
   through the state equation is what makes it the state.

2. **Analytical (derivative)**: whichever variable appears as a time
   derivative (dU/dt) is a state variable. This is equivalent to saying
   the variable describes the **capacity effect** — the accumulation
   term in a balance equation.

These are two views of the same thing:
- The derivative dU/dt is what creates the cycle: the equation defines
  how U changes, and U (transitively) affects the RHS of its own
  equation through properties and transports.
- The capacity effect is the physical interpretation: a capacity
  (volume, mass, energy storage) accumulates, and the rate of
  accumulation is the time derivative of the state variable.

So "state" can be identified either by graph structure (where is the
cycle?) or by analytical form (where is the time derivative?). Both
are emergent from the selected equation subgraph — neither requires
an ontology tag.

### Transport system: no state, no capacity (2026-09-13)

An important consequence of the structural/analytical definition of
state: the **transport system** (event-dynamic distributed node, entity
type 4.1.5 in CWA 17960) has **no state** and consequently describes **no
capacity effect**.

This is something people are mostly not aware of. The transport system
is modelled as an event-dynamic distributed system. Its equations are
**algebraic** — they describe instantaneous transport behaviour (flow
rates as functions of effort differences, transport coefficients, etc.),
not accumulation. There is no time derivative, no cycle through a state
variable, no capacity.

In the BL's subgraph terms:
- The transport system's equation subgraph is **acyclic** — no equation's
  LHS transitively depends on itself.
- There is **no state-defining equation** — no base equation with a time
  derivative.
- All variables are either defined by algebraic equations within the
  subgraph, instantiated (parameters like transport coefficients), or
  external (effort values from connected capacity nodes).

This is why the transport system is a **node**, not an arc: it has its
own behaviour (transport equations), but it doesn't accumulate. The
arcs just carry continuity conditions (effort equality, flow
conservation). The transport *behaviour* lives in the node; the arc is
pure topology.

This also illustrates why the structural definition of "state" is
powerful: it naturally handles the case where an entity type has no
state. The BL doesn't need a flag that says "this entity type has/doesn't
have state" — it just builds the subgraph, and if there's no cycle,
there's no state. The absence of state is as informative as its presence.

### Transport connects capacities (2026-09-13)

The transport system has no state of its own — but it **connects
capacities**. This is its role in the model network:

- Capacity nodes have state (accumulation, time derivatives).
- Transport system nodes have no state (algebraic, instantaneous).
- Arcs carry continuity conditions (effort equality, flow conservation).
- The transport system sits between capacities, computing the flow
  between them as a function of the effort difference and transport
  coefficients.

So the transport system's inputs are the effort variables from the
connected capacity nodes (external inputs via arcs), and its outputs
are the transport flows that appear on the RHS of the capacity nodes'
state equations.

In BL subgraph terms:
- The transport system's subgraph is acyclic and closed: all inputs
  (efforts) come from outside (connected capacities), all outputs
  (flows) go outside (back to capacity state equations).
- The capacity nodes' subgraphs contain the cycle (state), and the
  transport flow appears on the RHS of the state equation as an input
  from outside (from the transport system node).

This is where the **network** structure matters: the BL builds
subgraphs per entity type, but the entity types are connected. A
transport system's output is a capacity's input, and vice versa. The
BL's per-entity-type subgraphs are individually closed, but they
reference each other through external inputs/outputs. The full model
(assembled in the Modeller) closes the network by connecting these
external inputs to the corresponding outputs.

### PDAE → ODAE meshing — numerical, not BL

PDAE vs ODAE is a **numerical issue**, not a BL concern. The BL does
not need to know whether it is building a PDAE or ODAE system.

However, we did imply that PDAEs may be **meshed** into a network of
ODAEs — i.e. spatial discretisation converts a distributed entity's PDE
equations into a network of lumped ODE equations. This is a
transformation step that lives downstream:

- The ontology defines entity types with scale values (e.g.
  "distributed" = macro/dynamic + macroscopic/distributed).
- The BL selects PDE-type equations for distributed entity types.
- Meshing (code generation or a pre-processing step) converts the PDE
  into a network of ODEs — the spatial indices become network topology.

This means the mathematics domain also needs to understand:
- **Index structure** — which indices are spatial (to be meshed) vs.
  which are topological (network structure).
- **Meshing rules** — how spatial indices are discretised into network
  nodes. This is likely a code generation / instantiation concern, not
  a BL concern.

### Open questions

- ~~Does the BL need to know about the PDAE/ODAE distinction?~~
  **Resolved**: No. PDAE vs ODAE is a numerical issue.
- Should the ontology define a "mathematical role" classification axis,
  or is this determined entirely by the equation subgraph structure?
  (The BL mechanics imply the role from subgraph position — but ontology
  hints could help the UI suggest defaults.)
- Where does meshing live — code generation, instantiation, or a
  separate step?
