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
   equation class? (Q1) — **Resolved**, see §9.
2. **Assignment artefact structure** — what does the RDF named graph
   look like? What predicates? — **Draft proposal**, see §13.
3. **Interface/port definitions** — does the BL need these, and should
   they come from the ontology or the equation editor? — **Resolved**,
   see §10.
4. **Equation eligibility metadata** — should equations carry scale-value
   constraints, or should the BL infer eligibility from variable
   classifications? — **Resolved (tentative)**, see §11.
5. **Validation scope** — what does the BL validate, and what is
   deferred to code generation / instantiation? — **Resolved**, see §12.
6. **Graphics assignment** — is this a BL responsibility or a separate
   step? (The three-level graphics model says Level 2 concrete base
   graphics are assigned in the BL, but the Graphic Object Editor is a
   separate module.)
7. **Mathematical role classification** — does the BL need to know about
   dependent/independent/input/parameter roles, or is that determined by
   the equation subgraph structure? (See §8.) — **Resolved**: implied by
   subgraph position; ontology hints optional.
8. **PDAE → ODAE meshing** — where does meshing live? (See §8.) —
   **Resolved**: downstream of BL (code generation / instantiation).

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
   - it is **marked to be instantiated** (see below), or
   - it comes from **outside** the entity (a connected entity provides
     it — this is a port/input).
4. Repeat recursively: each newly selected equation has its own RHS
   variables, which must be resolved the same way.
5. The subgraph is **closed** when every RHS variable in every selected
   equation is either defined within the subgraph, marked to be
   instantiated, or declared as an external input.

### The `Instantiate` operator (2026-09-13)

A variable is not "instantiated" — it is **marked to be instantiated**.
There is an `Instantiate` operator in the ProMo language definition.
Its purpose is to keep units and index structures clean: the variable
retains its full semantic identity (units, index structures, token
bindings, classifications) but is flagged as a parameter whose value
will be set at instantiation time, not computed by the equation system.

This distinction matters: the variable is still a first-class entity in
the var/expr graph with all its metadata. The `Instantiate` operator
just marks it as "value comes from outside the equation system, at
instantiation time."

### Two ways to mark a variable to-be-instantiated (2026-09-13)

There are two places where a variable can be marked to-be-instantiated:

1. **In the equation editor** — via the `Instantiate` operator directly
   in the equation expression. The equation author writes something
   like `Q = Instantiate(heat_transfer_coefficient)`. This is baked into
   the equation definition itself.

2. **In the BL** — when resolving an unresolved RHS variable during
   subgraph construction, the user marks it as to-be-instantiated
   instead of selecting a defining equation for it.

The question is: should the BL be able to mark **any** unresolved
variable as to-be-instantiated?

**Open question**: Can all variables be marked to-be-instantiated in
the BL, or only some? This needs further thinking. There may be
variables that should never be parameters (e.g. state variables, or
variables whose value is structurally determined by the equation
system). Allowing the BL to mark anything as to-be-instantiated could
lead to degenerate subgraphs where the equation system is trivially
satisfied by instantiating everything.

This needs discussion.

### Cycle check is indirect (2026-09-13)

The cycle check is **not** an explicit graph-theoretic cycle detection.
It is implicit in the recursive construction:

- One starts with a base equation and recursively fills in new equations
  to define not-yet-defined variables.
- The **endpoints** of this recursion are:
  - **to-be-instantiated** (parameter — marked with `Instantiate`),
  - **state** (the LHS of the base equation — the cycle closes here),
  - **a flow in a balance equation** (external input from a connected
    entity — port).
- If the recursion encounters a variable that is already being defined
  by an equation in the subgraph (other than the state variable), that's
  an error — an unwanted cycle. The user must resolve it by marking the
  variable as to-be-instantiated or declaring it external.

So the cycle through the state variable is the **natural endpoint** of
the recursion — the recursion terminates because the state variable is
already defined (by the base equation). No explicit cycle detection is
needed; the recursive construction naturally identifies the state as
the one variable that closes the loop.

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

**Refinement (2026-09-15):** "no state" means no *autonomous dynamic*
state, and it is the **time-scale value** that decides.  Modelled as a
*dynamic distributed* entity, the transport system is a PDAE: it has
its own integrated state (spatial profiles of T, c, v evolved by its
balance equations).  Modelled with the *event-dynamic* assumption, the
internal state still exists but is **boundary-determined** — the
profiles are whatever the adjacent capacities currently impose
(quasi-steady assumption).  The subgraph is then acyclic *given the
port inputs*, not because nothing inside could be a state.  Same
equations, same ports — the modelling choice lives in the scale value,
not in the code.

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

## 9. Unit of selection — per entity type (2026-09-13)

### Resolution

The unit of selection is **per entity type**. The BL builds a complete
behaviour description for each entity type — a closed equation subgraph
that only depends on what is connected to it (external inputs) and what
is instantiated (parameters).

For a **capacity** (physical entity with state):
- The state equation closes over the state variable (the cycle).
- External inputs are token flows (from connected transport systems)
  and instantiated variables (parameters).
- All other equations (properties, efforts, etc.) are internal to the
  entity's subgraph — they are resolved within it.

For **information processing** (e.g. control):
- The same applies for dynamic equations. A controller has a state
  (dynamic equation), and its inputs come from connected entities
  (observations, setpoints).

### Information processing in the BL (2026-09-13)

How does information processing map to the BL design?

#### Same mechanics, different semantics

The BL mechanics are identical for information and physical entities:
select a base equation, resolve RHS inputs, close the subgraph. The
differences are in the semantics of connections and state:

**Physical domain:**
- Arcs are bidirectional (continuity conditions: effort equality, flow
  conservation).
- Transport system nodes connect capacities — they compute flows.
- State = physical capacity effect (accumulation of mass, energy, ...).
- External inputs = token flows from transport systems.

**Information domain:**
- Arcs are unidirectional (output of one function = input of next).
- No transport system equivalent — the arc IS the connection. It just
  passes the signal. No separate node needed to compute the connection.
- State = algorithmic memory (e.g. integral of error in a PID controller,
  filter state). Structurally identical to physical state: a time
  derivative creates the cycle.
- External inputs = signals from upstream entities (observations,
  setpoints, manipulated variables).

#### Entity types in information processing

From the ontology design (CWA 17960 §4.2), information capacities have
3 types: constant, dynamic, event-dynamic (instantaneous I/O).

In BL terms:
- **Dynamic information entity** (e.g. PID controller, filter): has a
  state equation (dynamic equation with time derivative). The cycle
  goes through the state variable. Same structure as a physical capacity.
- **Algebraic information entity** (e.g. gain block, summing junction,
  lookup table): no state, no cycle. All equations are algebraic. Same
  structure as a transport system — but it's a node, not an arc.
- **Constant information entity** (e.g. fixed setpoint): no equations,
  just a parameter. Instantiated.

#### What connects to what?

Cross-domain connections (from ontology design discussion):
- Physical → Information: observation (sensor reading)
- Information → Physical: manipulated variable (valve position, heater
  power)
- Within Information: signal chain (controller output → actuator
  command)

In the BL, these cross-domain connections are all **external inputs**:
- A controller's subgraph has observation variables as external inputs
  (from a physical capacity's output).
- A physical capacity's subgraph has a manipulated variable as an
  external input (from a controller's output).

The BL doesn't need to know it's a cross-domain connection — it just
sees an external input that comes from a connected entity. The
connection rules in the ontology determine which connections are valid.

#### Open question: is there an information-domain "transport system"?

In the physical domain, the transport system is a separate node that
connects capacities. In the information domain, the arc just passes
the signal — no separate node needed.

But what about more complex information routing? E.g. a multiplexer,
a splitter, a signal selector? Are these:
- Separate entity types (nodes in the Modeller)?
- Or just arcs with special properties?

This needs further discussion.

### What is a node? (2026-09-13)

This raises a key question: is an algebraic equation that is connected
to the state equation's holding entity also a node?

From the ontology design discussion (2026-09-11/12):
> Property functions (thermo relations, geometric relations) are
> sub-routines called within a node, NOT network nodes. Old ProMo
> tried to put them in a separate domain — was not clean.

So the answer is: **no**, an algebraic equation connected to the state
equation is NOT a separate node. It is part of the same entity's
behaviour description. The BL includes it in the entity's equation
subgraph.

The distinction is:
- **Network nodes** (entities in the Modeller) — connected by arcs,
  exchange variables through ports. Each has its own behaviour
  description (BL subgraph).
- **Internal equations** (within a node's subgraph) — resolved within
  the entity. Property functions, effort relations, constitutive
  equations. They are not nodes; they are part of the node's behaviour.

The BL's subgraph for an entity type includes ALL equations needed to
close the description — state, properties, efforts, transports (if
internal), constitutive relations. Only variables that come from
outside (connected entities) or are instantiated (parameters) are
external to the subgraph.

### Open question: what about transport systems?

The transport system IS a network node (entity type 4.1.5) — it has its
own behaviour description (algebraic transport equations). It is NOT an
internal equation of a capacity node. The transport system connects
capacities; it is a peer node in the network, not a subroutine.

So the rule is:
- If the equation describes the entity's own behaviour (properties,
  constitutive relations, efforts) → internal to the entity's subgraph.
- If the equation describes interaction between entities (transport
  between capacities) → separate entity type, separate node, separate
  subgraph.

The distinction is in the ontology's entity type definitions, not in
the BL logic. The BL just builds subgraphs per entity type.

## 10. Interface/port definitions (2026-09-13)

### Current state in the codebase

The semantic contracts (`packages/semantic/src/contracts.ts`) already
define:

```typescript
type PortDirection = 'input' | 'output' | 'bidirectional'

interface InterfacePortDefinition {
  iri: Iri
  label: string
  direction: PortDirection
  tokenTypeIris: Iri[]
  attributes: SemanticAttribute[]
}

interface EntityInterfaceDefinition {
  iri: Iri
  ports: InterfacePortDefinition[]
}
```

`VariableRecord` has `port_variable: bool`. But `getInterface()` in the
placeholder catalogue returns `undefined` — not populated from RDF yet.

This concept likely originates from CWA 17960 / old ProMo.

### Do we need a special definition for cross-domain information?

No. We do not have a special definition for information exchanged between
domains. The connection rules already encode which connections are
valid (type 3: signal connections). The key distinction is direction:

- **Physical ports**: bidirectional (effort equality + flow conservation
  — both quantities are exchanged through the connection).
- **Information ports**: unidirectional (output of one entity = input of
  next). Direction is `input` or `output`, never `bidirectional`.
- **Cross-domain connections**: unidirectional information arcs.
  Physical→information (observation), information→physical (manipulated
  variable).

### Where do port definitions come from?

Following the hint/binding pattern:

- **Ontology**: connection rules define which tokens can be exchanged
  between entity types, and the arc type (physical bidirectional vs.
  information unidirectional). This determines the port's direction and
  token types — a **hint**.
- **BL**: the subgraph closure identifies which variables are external
  (not defined within the subgraph, not instantiated). These external
  variables are the entity's **ports**. The BL **binds** which specific
  variables are the actual inputs/outputs for each entity type.
- **Direction**: determined by the arc type (physical = bidirectional,
  information = unidirectional). For information entities, the direction
  (input vs. output) is determined by whether the variable appears on
  the RHS (input) or is the LHS of an equation whose result goes outside
  (output).

So ports **emerge** from the BL's subgraph closure, just as state
emerges from the cycle. The BL doesn't need a separate port definition
step — it identifies external variables during closure, and these
become the entity's interface.

### Open question

- The current `InterfacePortDefinition` has `tokenTypeIris` — should
  this be populated from the variable's token tags, or from the
  connection rules? (Likely both: the variable carries token tags, and
  the connection rule validates that tokens match.)

## 11. Equation eligibility metadata (2026-09-13)

### The question

Should equations carry metadata saying "I'm valid for entity type X" or
"I'm valid for scale value Y" (e.g. "this is a PDE balance equation for
distributed entities")? Or should the BL infer eligibility from the
variables' classifications?

### Following the hint/binding pattern

This is the same pattern as state, transport, and ports:

- **Equation eligibility metadata = hint**: the equation author tags an
  equation with scale-value constraints or entity-type applicability.
  This helps the BL filter/sort which equations to show as selectable for
  a given entity type. But it does not bind — the user can override.
- **User selection = binding**: the user selects which equations apply
  to which entity types. The BL's subgraph closure is the actual
  assignment.

Without eligibility metadata, the user sees all equations and must
choose wisely. With eligibility metadata, the BL can filter/sort the
list, making the user's job easier.

### Where could eligibility metadata live?

Options:
1. **On the equation itself** — `promo:eligibleForScaleValue` or
   `promo:eligibleForEntityType` predicates on the `Equation` node.
2. **On the equation class** — the `EquationClass` hierarchy could
   carry scale-value constraints (e.g. "balance" class is eligible for
   all entity types, "PDE balance" subclass is eligible for distributed
   only).
3. **Inferred from variables** — the BL checks whether the variables in
   the equation have classifications compatible with the entity type's
   scale values. No explicit metadata needed.

Option 3 is the most consistent with the flexibility principle (no
extra metadata to maintain), but it requires the BL to understand the
relationship between variable classifications and entity type scale
values — which may be complex.

Option 2 is a middle ground: equation classes are already hierarchical,
and adding eligibility constraints to the hierarchy is a natural
extension. The equation editor already has `equation_class` as a field.

### Resolution (tentative)

Start without explicit eligibility metadata (option 3). The BL shows all
equations; the user selects. If the UI becomes unwieldy, add equation
class-level eligibility constraints (option 2) as hints.

This is consistent with the incremental approach: don't add metadata
until the need is proven. The BL works without it — it just works
better with it.

## 12. Validation scope (2026-09-13)

### What the BL validates

From the discussion so far, the BL performs these checks during subgraph
construction:

1. **Closure check** — every RHS variable in every selected equation is
   either:
   - defined by another equation in the subgraph,
   - marked to-be-instantiated, or
   - declared as an external input (port).
   If any RHS variable is unresolved, the subgraph is not closed.

2. **Unwanted cycle detection (indirect)** — the recursive construction
   naturally identifies the state variable as the endpoint where the
   cycle closes. If the recursion encounters a variable already defined
   by another equation in the subgraph (other than the state variable),
   that's an unwanted cycle — an error the user must resolve.

3. **Endpoint validity** — the three valid endpoints of the recursion
   are: to-be-instantiated, state, or a flow in a balance equation
   (external input/port). Any other endpoint is an error.

### What the BL does NOT validate

The following are deferred to code generation, instantiation, or other
downstream steps:

- **Numerical solvability** — DAE index, PDAE vs ODAE, stiffness,
  well-posedness. These are numerical concerns.
- **Meshing** — spatial discretisation of PDEs into ODE networks. This
  is a code generation / pre-processing step.
- **Parameter values** — actual values of to-be-instantiated variables.
  Set at instantiation time.
- **Network-level closure** — connecting entity subgraphs in the
  Modeller. The BL builds per-entity-type subgraphs; the full model is
  assembled downstream.
- **Unit consistency across entities** — the equation editor checks
  units per-equation. Cross-entity unit consistency is a code
  generation or model-level validation concern.
- **Physical validity** — does the selected equation set make physical
  sense? The BL doesn't judge physics; the user does.

### Summary

| BL validates | Deferred |
|---|---|
| Subgraph closure | Numerical solvability |
| Unwanted cycles (indirect) | Meshing |
| Endpoint validity | Parameter values |
| | Network-level closure |
| | Cross-entity unit consistency |
| | Physical validity |

The BL's validation is **structural** — it checks the subgraph is
well-formed. It does not validate **semantics** (physics) or
**numerics** (solvability). Those are downstream concerns.

## 13. Assignment artefact structure (2026-09-13)

### What is the assignment artefact?

The BL's output is an RDF named graph — the **assignment artefact** —
that records the result of the user's equation selection for each
entity type. It is the binding: which equations describe which entity
type's behaviour, which variable is the state, which variables are
to-be-instantiated, and which are external inputs (ports).

### Existing PROMO vocabulary

The codebase (`backend/core/graph_store.py`) already defines:

- `promo:EntityType` — entity type
- `promo:Equation` — equation (with `promo:lhs`, `promo:rhs`,
  `promo:incidenceList`)
- `promo:hasEquation` — links a variable to its equation(s)
- `promo:hasScaleValue` — links entity type to scale values
- `promo:EquationClass` — equation class hierarchy
- `promo:equationClass` — links equation to its class

### Proposed predicates for the assignment artefact

The assignment artefact is an RDF named graph. Everything that can be
linked via RDF should be linked — equation IRIs, variable IRIs, entity
type IRIs all reference the existing graphs. No copying or reification.

The key insight: **the list of equations must be ordered** — in the
sequence they are discovered and added during the recursive
construction. This order directly defines the **computation sequence**
for code generation.

The computation sequence is:

1. **State equation** — the base equation (integrated over time)
2. **Secondary state** — property equations (thermodynamic relations,
   effort, geometry, ...) that depend on state and on each other
3. **Transport** — transport equations (flow rates, fluxes)
4. **Reactions** — reaction equations (if applicable)

This order emerges naturally from the recursive construction: the user
selects the base equation, then resolves its RHS inputs by selecting
equations in order. Each equation's LHS becomes available for
subsequent equations.

### RDF structure

```
promo:Assignment              — the assignment (one per entity type)
  promo:forEntityType         — links to the entity type IRI
  promo:hasBaseEquation       — the state-defining equation IRI (first in sequence)
  promo:hasEquationSequence   — an rdf:List of equation IRIs, in computation order
  promo:hasStateVariable      — the state variable IRI (if entity has state)
  promo:hasPortVariable       — an external input variable IRI (port)
  promo:hasInstantiatedVariable — a to-be-instantiated variable IRI
```

Using `rdf:List` (ordered collection) for the equation sequence
preserves the discovery order. Each equation IRI references the
equation in the var/expr graph — single source of truth.

Variable role predicates can be flat triples:

```
entityType IRI  promo:hasState      variable IRI
entityType IRI  promo:hasPort       variable IRI
entityType IRI  promo:hasParameter  variable IRI
```

### Why order matters

The computation sequence is critical for code generation:

- The integrator needs the state equation first.
- Secondary state equations (properties) are evaluated after state is
  known — they are algebraic functions of state.
- Transport equations are evaluated after properties are known
  (transport depends on effort, which depends on properties).
- Reactions are evaluated after transport (reaction rates depend on
  concentrations, which depend on state and transport).

This is the **lower-triangular evaluation order**: each equation's
inputs are either the state (from the integrator), outputs of earlier
equations in the sequence, to-be-instantiated parameters, or external
inputs (ports). The recursive construction naturally produces this
order — no topological sort needed at code generation time.

### Resolved sub-questions

- **Reference, not copy**: equation IRIs reference the var/expr graph.
- **Order matters**: use `rdf:List` to preserve computation sequence.
- **Single graph**: one assignment named graph for all entity types
  (simpler to query, and entity types are independent).

### Remaining open question — resolved (2026-09-18)

- How are port variables linked to connection rules? The port variable
  needs to match a token type when connected in the Modeller.

  **Resolution:** the vocabulary already exists — it just isn't wired
  yet.  Variables declare `promo:carriesToken` (the `tokens` field on
  `VariableRecord`) — which token the variable rides on.  A resolved
  connection rule exposes `matched_tokens` — the tokens licensed to flow
  on that arc.  **Port satisfaction** is the check the Modeller does not
  yet perform: a BL port variable is satisfied by an arc iff its token is
  in (or comparable to) the arc's `matched_tokens`.

  Semantics per carrier:

  - **token-flow arc** (`physical-same`) — ports are the flow + effort
    pair per licensed conserved token (mass flow + pressure, heat flow +
    temperature, …).
  - **reference arc** (`signal`, `access`, `sensor`, `actuation`) —
    ports are the accessed variables; the signal *subtokens*
    discriminate direction: `observation` for sensor (read-only),
    `manipulation` for actuation (write), plain `signal` for
    access/signal.

  Missing piece: variables must actually declare their token (the field
  exists but is mostly empty), and the Modeller needs the port-token
  check on connect.  To be pinned down in ADR-008 alongside the
  assignment artefact.

## 14. Token semantics for exchange variables (2026-09-18)

### The token lifecycle

Tokens live in the **domain** — they are the conserved/exchangeable
quantities.  Variables are their *manifestations* in the equation
system.  The same token appears in three roles:

- **Accumulate** → *state variable* — amount of token held in the
  entity (`n`, `U`, `m`).  The balance equation's LHS: `d(token)/dt`.
- **Move** → *flow variable* — token transport across the boundary
  (`F`, `Q`).  The RHS fluxes.
- **Drive** → *effort variable* — the token's potential (`p`, `T`,
  `μ`).  What pushes the flow.

The pattern is **uniform across branches**: on the information branch,
signal "accumulates" as information state and "moves" as transmission.
Same abstraction, different domain — argues for uniform token handling
rather than splitting by carrier.

Consequence: the assignment's variable roles (state / port / parameter)
*are* the token's manifestation modes — accumulation, transport, none.

### `carriesToken` is definitional, not an annotation

Choosing a flow variable implicitly chooses its token — the link is
part of what the variable *is*, not optional metadata:

- **Exchange variables** (state/flow/effort that cross boundaries) —
  token link is intrinsic and required.
- **Internal variables** (geometry, parameters like `k`) — no token;
  they never ride an arc.  If one is later exposed via an `access`
  arc, it carries `signal` — accessed *as information*.

### `port_variable` vs the BL port role

Two different concepts, both needed:

- **`port_variable` (flag on `VariableRecord`)** — *structural*: a
  boundary node in the entity's bipartite (variable↔equation) graph —
  where another entity's equation system can attach.  Direction-
  agnostic capability ("*can* be exchanged").
- **BL port role (`promo:hasPortVariable`)** — *directional*: consumed
  as external input in this entity's assignment ("*is* exchanged, and
  in which direction").

The same physical quantity appears on both sides of an arc: exposed
output (`port_variable`) on the source entity, BL port (input) on the
target entity.  The arc joins them.

### Token suggestion in the equation editor

`carriesToken` should be *suggested*, not silently defaulted:

- **Units match a conserved-token signature** (`kg` → mass, `mol` →
  amount, `J` → energy) → suggest that token.  Units are a consistency
  check, not a reliable key — store the link explicitly.
- **Exchange-marked but no unit match** (signals usually have no
  units) → offer the **signal family as a picklist**:
  - `signal` (recommended default) — direction-agnostic; comparable to
    both `observation` (sensor) and `manipulation` (actuation) arcs,
    since `tokens_comparable` is ancestor-or-self.
  - `observation` — tighter: read-only, sensor arcs only.
  - `manipulation` — tighter: write-only, actuation arcs only.
  The subtoken choice is a deliberate narrowing, not a guess — the
  observation/manipulation discrimination lives on the arc/rule side,
  so a variable carrying plain `signal` stays direction-agnostic.
- **Otherwise** → no token (internal variable).

### Port satisfaction (recap from §13)

A BL port variable is satisfied by an arc iff its token is in (or
comparable to) the arc's `matched_tokens`.  With `carriesToken`
intrinsic, this check is definitional rather than annotation-
dependent.  Remaining work for ADR-008: the Modeller-side check on
connect, and whether `carriesToken` becomes required for
`port_variable` variables.

## 15. Reference coordinates for flow systems (2026-09-20)

### The problem

Transfer laws give flow direction *relative to a reference
coordinate*.  The reference coordinate comes from the connection —
in old ProMo the directed arc drawing provided it, and the node–arc
incidence matrix of the directed graph was the reference coordinate
for the whole model.

In the new modeller this no longer works directly:

- Physical arcs are **bidirectional** connections (continuity
  condition: effort equality + flow conservation).  `ModelArc.source`/
  `target` records drawing order — pure layout, no semantics.
- Transport systems are **nodes**, not arcs: a flow path is
  `capacity —arc— transport —arc— capacity`.  There is no single arc
  whose drawing direction could serve as the reference.

### Decision: per-contact reference direction

Every **contact** between a flow-system entity and a capacity carries
a reference direction — essentially the old system, relocated:

- Each physical (token-flow) arc gets a **semantic orientation**
  (`referenceFrom`/`referenceTo` endpoints) independent of the drawn
  `source`/`target`.  The old directed-arc gesture assigned both
  contacts' directions at once; the new model assigns per contact.
- Per-contact assignment is what generalises to **multi-port flow
  systems** — a thermal system connected to several capacities, a
  mass-diffusion system: n contacts, n reference directions.
- One sign per contact suffices: direction "T → C" means positive
  flow leaves the transport and enters the capacity; the capacity
  end reads the complement automatically.
- The flow-system entity **owns** the orientation: assigning the
  reference coordinate is part of inserting the entity into the
  model — the modern equivalent of drawing the directed arc.

### Properties

- **Any assignment is valid.**  Reference directions are pure
  convention; a negative computed flow means physical flow runs
  opposite to the reference.  The only hard requirement is
  *existence*: every contact of a flow system must have one.
- **Transport balance**: a non-accumulating transport's own
  conservation is `Σ_i s_i·f_i = 0` over its contacts, signs from
  the stored orientations.
- **Global incidence is derived**: per-contact signs + topology →
  the old-ProMo `F[N,A]` at instantiation.  Equations reference `F`
  symbolically, so flipping an entity's orientation flips signs at
  codegen — no equation edits.  (Notation: `F` = incidence matrix,
  `I` is reserved for identity.)
- **Scope**: only token-flow/continuity arcs need a reference
  coordinate.  Signal/access/sensor/actuation arcs have inherent
  direction (output → input); discrete/event systems have no
  continuous conservation.  The problem is confined to the physical
  domain's continuity condition.

### Terminology caution

"Incidence" currently names two different things:

- `checker.py` / `promo:incidenceList` — the set of **variable IRIs
  in an RHS** (bipartite variable↔equation dependency).
- The topological **node–arc incidence matrix** `F[N,A]` discussed
  here — derived from model topology at instantiation.

Keep them distinct in discussion; a rename of the former may be
worthwhile when the latter is implemented.

### Edge cases

- **Capacity↔capacity arcs** — if connection rules ever allow a
  direct physical arc with no transport between, that arc needs its
  own reference direction (no entity owns the contact).
- **Transport↔transport arcs** — both ends are flow systems; each
  end's sign is independent, and a consistency check should verify
  the two ends' reference directions compose sensibly.
- **Composites / open arcs** — the sign convention across a
  composite boundary must be written down; `OpenArcDoc.isSource`
  already encodes the boundary side.

### Modeller UX implications

- Orientation is part of the **insertion gesture** for flow-system
  entities.
- Default for the common 2-port case: auto-assign the through-path
  orientation when the second connection is made; explicit choice
  only for n-port or non-standard orientations.
- A **"reverse reference direction"** command flips the semantic
  orientation without touching layout.
- A visible **arrow convention** on the entity/contacts shows the
  reference direction — distinct from arc rendering.

### Where it lands

- **Model artefact**: per-arc semantic orientation stored alongside
  `ModelArc` (e.g. `promo:referenceFrom`/`promo:referenceTo`).
- **BL / instantiation**: derives the signed incidence matrix `F`
  from topology + orientations; binds it to the symbolic `F` in
  conservation equations.
- **Equation editor**: unchanged — equations stay orientation-free.
