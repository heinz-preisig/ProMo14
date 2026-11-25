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
  - `promo:indexStructure` → index IRIs — a **fixed sequence of
    unique indices**: declaration order is the canonical axis order
    (`F[node, arc]` means rows=nodes, cols=arcs).  The checker
    enforces uniqueness and preserves order through the expression
    tree (ordered union for products, operand order minus the
    reduced index for reductions); element-wise ops require the same
    sequence, not just the same set.  Codegen emits axes in this
    order — no label lookup needed at runtime.
    *(Superseded 2026-11-13 — design-principles §8: `+`/`-` conform
    by index set, result order = left operand, `_align` permutes at
    emit; declaration order stays canonical.)*
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
   instantiated, or declared as an external input (port).

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

**Partially resolved (2026-09-22)**: variables of a bound-value class
(`constant`/`parameter`) or carrying a pre-bound `promo:value` are
*implicit* instantiation endpoints — they terminate the search without
a marking, and any explicit resolution (defining equation, instantiated
marking, port) overrides the hint.  Whether marking an arbitrary
*state-class* variable should be allowed remains open — the degenerate
"instantiate everything" subgraph is still possible today.

**Discussed (2026-09-29)**: marking is per variable, not per occurrence —
the unresolved-input mark already instantiates "the variable itself"
(the old ProMo distinction between instantiating a variable vs its
arguments collapses here).  Any variable is in principle a value
endpoint: measurement and prescription are meaningful for states too,
so value-endpoint is a *role* (binding), while `constant`/`parameter`
classes remain hints.  The case not expressible is a variable that is
*both* defined and instantiated (`defined_and_instantiated` conflict):
its coherent reading is equation inversion — the retained equation
determines one of its inputs instead — which is real assignment-problem
machinery, deferred until a concrete case needs it.  Degenerate
all-instantiated subgraphs are guarded by the closure check rather
than by class restrictions.  The unreferenced-mark warning applies to
ports only: an instantiated-but-unreferenced variable is a legitimate
interface declaration (a bound value provided outward — e.g. an
environment fixing a boundary variable), while an unreferenced port
promises an input nothing consumes.

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
- ~~Should the ontology define a "mathematical role" classification axis,
  or is this determined entirely by the equation subgraph structure?~~
  **Resolved (2026-09-24)**: structural roles are *not* axis terms.
  `port` is the `promo:portVariable` flag (bipartite-graph position —
  fundamental for the graph build); `derived` is implied by having a
  defining equation.  The physical `determination` axis keeps only the
  declarative fixity terms {constant, variable}; `parameter` moved to
  the `function` axis — a parameter is a characteristic value in a
  function (part of the function definition, often embodying a specific
  assumption), not a determination mode.  The earlier `variability`
  axis was dissolved ('variable' = not given; it overlapped and could
  contradict determination).
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

**Resolved (2026-10-29):** the static `EntityInterfaceDefinition` /
`getInterface()` contract in `packages/semantic` was **removed** —
it was never populated, had no callers, and sits on the wrong
artefact layer: an entity's interface is not ontology catalogue
data, it is **assignment-scoped** (which assignment the model pins
decides which ports exist).  The real interface surfaces are:

- **BL ports** — `port_variable` demands bound by the assignment,
  surfaced per connection at `GET /api/modeller/port-satisfaction`
  (§14).
- **§22 open-arc terminals** — a referenced composite's declared
  interface (arc type + token + §15 direction).

`VariableRecord` has `port_variable: bool`.

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

- ~~`InterfacePortDefinition.tokenTypeIris` population~~ — moot: the
  contract was removed (see resolution above).  The live equivalent is
  `carriesToken` on the variable + `matched_tokens` from the
  connection rule (§13/§14).

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
  on that arc.  **Port satisfaction** is the check the Modeller now
  performs at connect time (advisory — see §14 implementation note):
  a BL port variable is satisfied by an arc iff its token is in (or
  comparable to) the arc's `matched_tokens`.

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
  agnostic capability ("*can* be exchanged").  Refined in §19 (R3):
  exportability is *implied* for non-state defined vars carrying a
  token — the flag is an override, needed to export the state itself
  and to disambiguate several same-token candidates.
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
dependent.

**Implemented (2026-10-29)**: `GET /api/modeller/port-satisfaction?
source=&target=&arc_type=` adjudicates a proposed connection —
each side's `hasPortVariable` demands against the peer's exportable
variables (shared `readable_vars` helper in `builder.py`), licensed
through `resolve-connection`'s `matched_tokens` for the pair
(optionally narrowed to one carrier).  Statuses: `satisfied` /
`ambiguous` / `unbound` (with `state_hidden` hint) / `unlicensed`.
The check is **advisory** — the Modeller shows which port demands a
hovered connection would feed without gating the gesture
(`backend/instantiate/satisfy.py`, connect-gesture panel in the
Modeller sidebar).  Still open: whether `carriesToken` becomes
required for `port_variable` variables.

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

> **Implemented 2026-09-22** (modeller + F-builder):
>
> - `ModelArc.referenceFrom`/`referenceTo` (absent = draw order),
>   persisted as `promo:referenceFrom`/`promo:referenceTo` — token-flow
>   arcs only; signal/reference arcs keep their inherent direction.
> - Insertion default in `defaultOrientation()` (ModelGraph.ts):
>   through-path — a second arc on a transport complements the
>   existing one's direction; otherwise draw order.  The is-transport
>   check walks `promo:parent` via `BaseEntityDefinition.parentIri`
>   (new; `EntityTypeRecord.parent` added to the ontology API).
> - Reverse command: right-click on a token-flow arc, or `r` on the
>   selected arc → `reverseArcOrientation` (layout untouched).
> - Arrowhead follows the reference direction (`referenceReversed`
>   on `VisibleArc` → `arrowReversed` on the scene object).
> - Open arcs carry `refToExternal` (boundary-relative, survives
>   leaf→composite→leaf); restored on `reconnectOpenArc`.
> - `GET /api/instantiate/arc-indices` reports the effective
>   `reference_from`/`reference_to` per arc — the F-builder input.
>
> **Port donor selection (2026-10-29):** chained/carried port reads
> follow the reference direction — the donor lies at the
> `reference_from` (upstream) end of the contact arc.  A variable is
> *carried* iff it is **token-indexed** (`index.source == "token"`,
> e.g. species concentration); only carried vars are direction-gated:
>
> - same-variable candidates on a DOWNSTREAM peer are excluded in
>   `candidates_at` (a carried quantity is not read from the node the
>   flow leaves for);
> - an unbound carried port on an UPSTREAM node binds through its own
>   other resolved contacts (transit) or its own readable instance of
>   the same variable (`_self_supply`, unflagged state still hidden);
> - efforts/flows and non-carried vars keep direction-blind contact
>   semantics (an effort is equal at the contact).
> - `GET /api/instantiate/incidence` emits the signed `F[N,A]`
>   matrices (sparse COO, +1 at `reference_to`, −1 at
>   `reference_from`): base over all token-flow arcs + one per
>   declared arc sub-index, shared node row space.

## 16. Arc sub-indices by token and mechanism (2026-09-20)

### The problem

The algebra needs symbolic partitions of the arc index: a balance
sums fluxes over the arcs carrying its token (`F_mass`, `F_energy`),
and constitutive grouping needs the mechanism partition
(`F_diff`, `F_conv`, …).  Hardcoding "diffusion"/"convection" into
the index schema would fix the ontology to physics — the mechanism
had to be abstracted.

### Decision: `subIndexOf` + `selector`

An `Index` may carry two optional predicates:

- `promo:subIndexOf` — the base index this is a subset of (`arc`).
- `promo:selector` — the entity type that defines membership: an arc
  belongs to the sub-index iff the transport node it touches has that
  entity type (or a subtype — transitive resolution is an
  instantiation-time concern, not yet implemented).

The checker treats a sub-index as a plain distinct index; only
instantiation resolves the element set.  Nothing in the mechanism is
physics-specific — any classification term can be a selector.

### Entity tree: mechanisms grouped by token

Mechanisms are per-token, not a symmetric cross product — mass
transports by diffusion and convection, energy by heat (conduction),
radiation and work (mechanical/volume):

```
transport_system
├── mass_transport          → A_mass   (token partition)
│   ├── diffusion_transport → A_diff
│   └── convection_transport→ A_conv
└── energy_transport        → A_energy (token partition)
    ├── heat_transport      → A_heat
    ├── radiation_transport → A_rad
    └── work_transport      → A_work
```

The token-level grouping types carry no scale bindings; the mechanism
leaves bind the continuum pair (`macro_event_dynamic` +
`microscopic_distributed`).

### Consequences

- **The arc does not declare its token.**  Arc types encode only the
  carrier category (`token-flow`|`reference`); the specific token is
  implicit in the transport node's entity type.  A `promo:token` on
  arcs is a separate, deferred decision.
- **Balances write per-mechanism terms** — the standard form:
  `d(mass)/dt = F_diff·J_diff + F_conv·m_conv`.  The token partition
  falls out of summing mechanism terms; no index-union machinery.
- **Coupled transport** (one phenomenon carrying mass and heat)
  becomes two parallel transport nodes.
- **Reclassification is safe**: equations never see entity types —
  changing a transport's type moves its arcs between sub-indices at
  instantiation; equations still check clean.

### Deferred

- ~~Instantiation resolver: arc → incident transport → entity type →
  sub-index membership, including transitive subtype resolution
  (`A_mass` over the leaves of `mass_transport`).~~ **Done
  (2026-09-22):** `backend/instantiate/resolver.py` — pure resolver
  (`resolve`, `by_sub_index`) + `GET /api/instantiate/arc-indices`.
  Token-flow arcs only; transitive via `promo:parent`.  A
  transport↔transport arc unions both ends' sub-indices.
- The F-builder that turns membership + orientations (§15) into the
  numeric matrices.  Blocked on §15: per-contact reference directions
  are not captured in the modeller yet.
- Signal arcs: no mechanism partition — they touch no transport node,
  so the selector has nothing to resolve against, and direction is
  already discriminated by rule + subtoken.  If information-domain
  balances ever sum transmissions into information state, add
  `A_signal` as a *token* partition selecting by rule/subtoken, not
  mechanism (2026-09-21 discussion).
- `idx_arc` is seeded `network="physical"` — whether signal arcs
  (information topology) fall in its element set is unsettled; settle
  before any signal sub-index question (2026-09-21).

## 17. Scale regimes and the seed contract (2026-09-20)

### Regime: particulate | continuum

Macroscopic-and-below scales differ fundamentally from molecular —
continuum assumption vs discrete particles.  The distinction is a
*scale* distinction, so it lives in the scale-value trees as a
grouping level, not as a parallel classification that could
contradict the scale binding:

```
scale_length                          scale_time
├── particulate                       ├── particulate
│   └── molecular → {point, finite}   │   └── molecular → {…}
└── continuum                        └── continuum
    ├── infinitesimal → {point,fin.}      ├── nano → {…}
    ├── microscopic → {unif.,distr.}      ├── milli → {…}
    ├── macroscopic → {unif.,distr.}      └── macro → {…}
    └── infinite → {uniform}
```

Entity types keep binding leaf values; **regime is derived** by
walking `promo:parent` ancestry — single source of truth.  All seeded
entity types are continuum; the molecular time binding the transport
types briefly carried was removed (it predates the regime layer and
would have misclassified them as particulate).

Downstream value: behaviour applicability.  The §16 transport tree
is implicitly continuum-only; particulate wants different equation
forms (population balances, MD-style).  The BL can constrain
behaviours by regime without enumerating scales.

### The seed contract

Seeds come in two tiers:

- **Initial-state seeds** — everything `seed_default_ontology`
  writes into an empty graph (domains, tokens, base entity types,
  base indices, rules, scale dimensions, axes, equation classes).
  One-time initial state: modify or delete freely, never resurrected.
- **Floor seeds** — what the idempotent migrations ensure on every
  load (constants, transport mechanism types, arc sub-indices, scale
  regime structure).  Deleting one resurrects it on next backend
  start; modifications persist.  Each migration is guarded by its
  anchor — deleting `idx_arc` or `scale_length` retires that whole
  floor section.

**Scope**: the floor applies only to the core ontology graph
(`ONTOLOGY_GRAPH_IRI`).  Other artefact graphs load untouched — no
seeding, no migrations.  So the suite stays open: the newcomer's
core is self-repairing, while the advanced user's own line (hub →
New empty, Fork, or a `.trig` dropped into `data/`) is completely
free.  The choice is *which artefact line you work in*, not what the
seed contains.

### Deferred

- **Tombstones** — record deleted floor IRIs so migrations skip
  them.  Only when in-place deletion from core becomes a real need;
  fork covers the realistic case.
- **Floor marker** — a `promo:seeded`-style flag so the ontology
  editor can badge floor items instead of letting users discover
  resurrection by surprise.
- **`seedFrom`** on `New` — copy a chosen graph as starting point
  (fork without lineage) if non-empty non-fork starts are wanted.

## 18. Variable mutability policy (2026-09-21)

### Question

Which parts of a variable definition stay editable once the variable
is in use?  Answer: usage-conditioned — cosmetic fields always free,
structural fields locked while referenced.

### Field classes

- **Free always** — `doc`, `label`, `latex` and other codegen aliases,
  audit fields.  Stored expressions reference variables by
  `global_ID`/`internal_id` (rhs is a token stream in global_ID form;
  `lhs` is the variable IRI), so surface names are display/input only.
  Caveat: `rhs_latex` is a cached rendering — a rename needs cache
  regeneration, not a lock.
- **Identity (effectively immutable)** — `iri`, `internal_id` /
  `global_ID`; for indices, `internal_code`.  These are the reference
  keys inside stored expressions.
- **Locked while used** — `units`, `index_structures`, `tokens`,
  `port_variable`, and reference-key identities.  Two focused corrections
  remain available in the existing-variable editor:
  - `classifications` / derived `variable_class` (the variable's role) stay
    editable because changing them does not alter reference resolution;
  - `network` stays editable only when every reference is the variable's
    own defining `lhs`; its stored equations move to the new network with it.
    A foreign equation reference locks the network because qualified or
    scope-dependent names could otherwise change meaning.
  These edits preserve the variable IRI.  Units and index structures remain
  locked because changing either invalidates already-checked equations.
- **Data, editable** — `value` (changes results, not structure;
  seeded constants stay permanent by convention).

### Usage

An equation *uses* a variable iff the variable's IRI is the equation's
`promo:lhs`, appears in its cached `promo:incidenceList`, or one of its
reference tokens (IRI, `internal_id`, `global_ID`, `internal_code`)
occurs as a whole token in `promo:rhs`.  The variable's own defining
equation counts — changing `x`'s units breaks `x := f(y)` too.  The
scan is dataset-wide: `usesOntology` pins make references
cross-artefact.

### Enforcement (`backend/equation/service.py`)

- `POST`/`PUT /variables/{iri}` — field-level diff; a disallowed structural
  change + non-empty usage → **409** with `locked_fields` + `references`.
  (POST guards too: the editor updates via POST, and re-POST replaces rather than merging multi-valued triples.)
  Role/classification changes are allowed under usage; network changes are
  allowed only without foreign references.  (POST guards too: the editor
  updates via POST, and re-POST replaces rather than merging multi-valued
  triples.)
- `DELETE /variables/{iri}` — 409 while *foreign* equations reference
  it; own equations are deleted with the variable.  Delete also
  removes the variable's equation nodes — previously they were
  orphaned, leaving phantom rhs references.
- `GET /variables/{iri}/references` — `{used, references[]}` for
  proactive UI locking; `api.ts` surfaces the 409 `detail` message.
- Editor side: `VariableDetailDialog` (the variable detail modal) edits
  name/LaTeX/doc and role classifications while used; it permits a domain
  correction when references are only the variable's own defining equations,
  but locks domain under foreign references.  Units and index structures stay
  greyed out while used.  Legacy records with no classifications show an
  explicit warning and editable blank role selectors rather than guessing
  roles from the lossy legacy class.  Its “Add equation…” button opens
  `DependentVariableEditor` in editing mode — the same check/parse/
  generate/preview UI as for new variables, attaching the equation to the
  existing record.  The repository table edits name and doc inline
  (click cell → Enter/blur commits, Esc cancels).  `saveVariable` carries
  `equations`, `classifications`, `imported` and audit fields through the
  replace-semantics POST — previously a re-save silently dropped them.

### Deferred

- **Arc/port usage** — BL port bindings (`hasPortVariable`) and model
  arcs should count as usage once those writers exist.
- **`rhs_latex` cache invalidation** on rename.

## 19. Model instantiation (2026-09-22)

### What instantiation produces

The instantiation step binds a **model artefact** (topology:
`ModelNode`/`ModelArc`) to **behaviour assignments** (§13, per entity
type) and yields the assembled equation set — the input codegen
needs.  Implemented as a computed report, not a persisted artefact
(same pattern as the §16 resolver and §15 F-builder):

```
GET /api/instantiate/model?graph=<model>&vars=<var/expr graph>
```

`graph` is required (the model being instantiated); `vars` selects the
var/expr artefact supplying variables, equations and the assignment
graph (`{vars}/assignments`, or the default assignment graph when
`vars` is absent — dataset-wide variable scope).

`backend/instantiate/builder.py` is the pure engine; `service.py`
adapts store graphs into its plain inputs.

### Index element sets

Symbolic indices bind to concrete element sets:

- node index `N` → all model nodes;
- base arc index `A` → all token-flow arcs;
- each arc sub-index `A_k` → its §16 member arcs;
- per entity type `T` → the node subset `N_T` (nodes typed `T`).

Non-topological indices (species `S`, reaction `Q`, …) have no model
element set — they stay symbolic (`null` in the binding) until their
own element source exists (composition, reaction list).

### Variable bindings

Every variable an assignment references gets a **role** (state /
defined / port / parameter / input) and a **binding**:

- `incidence` — a `constant`-class variable indexed `[node, arc]`
  binds to the numeric `F` matrix for its arc index (`[N,A]` → base,
  `[N,A_k]` → `F_k`).  This is the symbolic-F convention from §15:
  equations reference `F` by index structure, instantiation supplies
  the numbers.  The `constant` class is the guard: graphs map into
  incidence matrices, so the `[N,arc]` shape is reserved for them —
  a data variable with that shape binds `local`, never silently `F`.
- `constant` — pre-bound `promo:value` (universal constants); one
  global instance.
- `parameter` — marked `hasInstantiatedVariable` or a bound-value
  class (`INSTANTIATE_CLASSES`); per-entity-type slot, value filled
  later.
- `port` — external input, resolved per contact (below).
- `local` — state/defined vars; each symbolic index maps to its
  element set (node index → `N_T`; arc index → members ∩ arcs
  incident on `N_T`).

Instances are named `<internal_id>@<entity-type frag>` — one
instantiated variable per (var, entity type), indexed by its bound
element sets.  Two entity types using the same var IRI get distinct
instances; the same type on several nodes shares one indexed
instance.

### Port resolution

A port variable carrying token τ binds through an incident arc to the
peer node's **exported defined** variable.  The candidate rule (R3 —
flag as override, not gate):

```
raw        = peer's defined vars (sequence lhs ∪ state)
             with a comparable token (shared promo:parent ancestry,
             so signal matches observation/manipulation)
raw       -= the state variable, unless it is flagged port_variable
candidates = the flagged members of raw, if any — else raw
```

`tokenKind` pre-filters carriers: conserved → token-flow arcs,
reference → reference arcs.

- **Arc-indexed ports** bind **per contact**: one `PortBinding` per
  incident carrier-matching arc.  A 2-contact transport's `p_in[A]`
  yields two bindings — `p@c1` via `a1`, `p@c2` via `a2`.
- **Scalar ports** aggregate all contacts: exactly one candidate →
  bound; several → ambiguous (a scalar can't have two sources).
- **Element**: arc-indexed peer vars bind at the arc element (the
  capacity's flow port → `J@a`); node-indexed at the peer node (the
  transport's effort port → `p@c`).

Why R3: what crosses a boundary is the token's *move/drive/observe*
manifestation (§14) — a defined var carrying a token — never the
accumulation.  So exportability is implied for non-state defined
vars; `port_variable` remains for (a) marking the *state* itself
exportable and (b) disambiguating several same-token candidates.
Consequences: the flag can add/prefer but never exclude a non-state
defined var; flags are per-var-IRI, so they disambiguate within one
peer's candidate set, never across contacts.  When the only
comparable var is the unflagged state, `unbound` carries a hint
("set port_variable or add a measurement variable").

### Problems

Reported, never silently dropped: `untyped-node`, `no-assignment`,
`assignment-open`, `unbound-port`, `ambiguous-port`,
`unmarked-input` (an external input that is neither port nor
instantiated — incidence/constant bindings exempt), plus
`missing-equation`/`missing-variable` for dangling references.

### Scheduling (`scheduler.py`)

The builder assembles *what* computes; the scheduler derives *when*
— the evaluation plan codegen consumes.  DAG nodes are
`(entity_type, equation)` pairs — the vectorized equation blocks.
An edge `A → B` means B consumes a variable A defines:

- **intra-type** — B's input is the lhs of another equation in the
  same entity type (the assignment's lower-triangular structure);
- **cross-type** — B's input is a *bound* port variable; the edge
  goes to the equation defining the peer variable in the peer's
  entity type.

**States are sources**: a state variable's value comes from the
integrator, not from its balance equation (which yields the
*derivative*) — consuming a state creates no edge.  This is what
breaks the differential cycle and leaves only *algebraic* loops.
Corollary worth stating: `base_equation` *is* the balance — a
stateless entity (transport) has none, so no state variable, and its
lhs vars stay ordinary defined vars in the schedule.  Constants,
parameters, incidence matrices, unbound ports and unmarked inputs
create no edges.

Output: `levels` — blocks grouped by dependency depth on the
condensation DAG (same level = independent, parallelisable; SCC
members share one level since they evaluate as a unit); `loops` —
SCCs of size > 1, the algebraic loops needing `fsolve`/tearing,
reported as `algebraic-loop` problems.  The canonical chain:
secondary states → flows → balances (`prop → flow → bal`).

### Codegen targets (2026-09-22)

Three emitters over one target-agnostic `CodePlan`
(report + schedule → structured plan: state layout, gather maps,
matrix literals, ordered blocks, loop groups):

- **Julia** — *primary numerical target*: `Tullio` for named-index
  Einstein ops (matches `Checked.indices` directly), `SparseArrays`
  for `F`, `OrdinaryDiffEq`/`NonlinearSolve` for integration and
  algebraic loops; ModelingToolkit later for index
  reduction/tearing.  `Unitful` could carry the checker's SI units
  into compile-time checking.
- **NumPy** — *readable baseline*: `np.einsum` subscripts lowered
  from the ordered index list, fancy-indexing gathers, dense/sparse
  `F @ J`.  No tensor runtime needed (no MultiDimVar port).
- **Matlab** — *legacy audience*: the vendored `MultiDimVar`
  Einstein-notation library (`runtime/matlab/@MultiDimVar`).

### Deferred

- **Persistence** — the report is computed per request; an
  instantiation artefact graph (frozen equation set for codegen) is
  the next step once the shape is validated.
- **Fix marking** (ADR-008 three-layer model) — per-occurrence
  overrides belong to the model artefact.
- **Node sub-indices** — `N_T` is derived per entity type; a declared
  node-sub-index mechanism (symmetric to §16) is not needed yet.
- **Port direction check** — binding is token+export based; whether
  the arc's rule direction licenses the flow (sensor reads vs
  actuation writes) is the modeller-side check (pending item 4).
- **R3 validation** — the flag-as-override rule is a hypothesis about
  modelling ergonomics; unit tests verify mechanics only.  Validate
  against real cases in the modeller (same-token exports, sensor
  reading state, unflagged efforts) before settling — R1 (strict
  gate) remains the fallback.
- **`[N,A]`-indexed data variables** — resolved by the constant-class
  guard above: only `constant`-class vars of that shape bind to `F`;
  a data variable binds `local` with per-index element sets.

## 20. Species allocation and distribution (2026-09-22)

### The problem

Non-topological indices (species `S`, reaction `Q`) have no model
element set (§19) — species presence is a *computed* property, not a
topological one.  Which species occupy each node and arc depends on
what is injected, what the transports pass, and what the reactions
produce.  This section defines the species artefact and the
distribution computation that yields the `S` element sets.

### Species-agnostic modelling

The modeller never names a concrete species.  Entities reference
species *by role* — "the species present here" — and the concrete set
arrives from a separate **species artefact** at instantiation.  The
same model topology + behaviour instantiates against different
allocations (a different feedstock) with no remodelling.  This mirrors
how the model references the ontology via `usesOntology`: the species
artefact is another swappable input.

### The species artefact

A new artefact type — the external **species/reaction app**, porting
the old-ProMo species-assignment app — owns the *vocabulary*:

- the **species set** — the global `S` elements;
- **allocations** — named species sets a reservoir can inject;
- **reactions** — stoichiometric rules `{reactants} → {products}`
  (open — see below).

The modeller owns the *placement and permissions* — it never names a
species, only references the artefact's vocabulary.

### Modeller capabilities

Three gestures, each gated by a **capability** on the entity type (a
predicate the modeller checks — not a `ConnectionRule`, which governs
arcs):

- **Inject species** — a node whose type carries the *species-source*
  capability (constant environment systems / reservoirs) may be
  assigned an *allocation* from the species artefact.  The injection
  point is topological (the modeller owns where sources sit); the
  injected content is allocated externally.
- **Set diffusivity** — a mass/species transport system may enable or
  block each species (**per arc**).  A semipermeable wall is a
  transport with some species blocked.  Restricted to mass/species
  transport — energy and signal arcs carry no species.
- **Host a reaction** — a node whose type carries the *reaction-host*
  capability may host reactions from the artefact.  "Any other node"
  in the requirement = any node with this capability.

The species distribution then defines what species is where, on every
node and arc.

### The distribution computation

A monotone fixpoint propagation over the model graph — the
graph-based algorithm from old ProMo:

- **Source** — a reservoir injects its allocated set.
- **Transport** — an arc carries `species(source) ∩ permeable(arc)`.
  A **semipermeable wall** is a transport whose permeable set is a
  strict subset — it blocks the complement.  Permeability is set
  **per arc**, and may be restricted to mass/species transport
  systems (energy and signal arcs don't carry species).
- **Reaction** — at a node, if `reactants(r) ⊆ species(node)` then
  `products(r)` are added.  Conditional: a reaction fires only when
  its reactants are present, so reactions cascade as species
  propagate in.
- **Fixpoint** — `species(n) = injected(n) ∪ transported_in(n) ∪
  produced(n)`; `species(a) = species(source a) ∩ permeable(a)`.
  Species only accumulate, so the iteration terminates.

The computation is shared: the modeller runs it live for
"species present" feedback; the instantiation builder runs it to bind
`S`.

### Binding `S`

The distribution yields a *per-node* set, but agglomeration wants a
rectangular `[N_T, S]` per entity type.  Reconcile by **union +
presence mask**: the type's `S_T` is the union over its nodes, and a
computed `present[N_T, S_T]` mask marks what is actually in each —
the "always all + a map" pattern, where *all* is the type union, not
the global species list.  The mask is a constant the emitters already
handle.  (Per-distinct-set sub-indices are the compact alternative,
but they break the per-type tensor when a type spans two sets.)

### Model-level aliasing (ruled 2026-09-23)

Components are **abstract** (`A`, `B`, `C` …) — the artefact is a
named reaction scheme, reusable across models.  What a species *means*
is model-dependent, so the alias is a per-model binding stored in the
**model graph**:

```turtle
<componentIRI>  promo:speciesAlias  "H2O" .
```

The split rule: the artefact owns *what exists and what can happen*
(components, allocations, reactions); the model owns *where it happens
and what things mean here* (placements, permeability, aliases).
Reactions stay in the artefact — they are scheme structure, not
model state.  Aliases are edited in the modeller (the app that owns
the model graph), never in the species app.

### Deferred / open

- **Stoichiometry** — ruled (2026-09-23, final): ν is a
  parameter-class variable indexed `[Q,S]` in the var/expr artefact,
  used symbolically in the algebra and valued at instantiation
  (persisted with the instantiated model artefact).  The scheme needs
  no coefficient slots — the non-zero pattern is derivable from
  `reactants(q) ∪ products(q)` with the −/+ convention; only
  magnitudes are supplied.  Open: the value channel — `promo:value`
  is scalar, a `[Q,S]` parameter needs a `(reaction, species)`-keyed
  table on the instantiated artefact.
- ~~Whether `Q` (reaction index) binds by the same mechanism.~~
  **Yes (2026-09-23):** `build_model`'s `reaction_index` binds a
  `Q`-indexed variable to the union of active reactions over the
  type's nodes — the `indexClass "conversion"` index is the
  discriminator (reactions carry no token).
- Whether the mask is required for correctness or only for
  compactness — absent species may already evaluate to zero.
- Alias target is a literal; an IRI-valued alias (substance catalogue
  or ontology subtoken → `component_mass` balances) is the migration
  path.

### Implemented (2026-09-22)

- **Species artefact** — `promo:Species` graph holding
  `promo:Component` (species), `promo:Allocation` (named injectable
  set, `member`→Component) and `promo:Reaction`
  (`reactant`/`product`→Component).  GET/PUT `/api/species/species`;
  catalogue type `species`; standalone `/species` SPA edits it.
- **Capabilities** — `promo:capability` → `promo:Capability` resources
  on entity types, inherited through `promo:parent` ancestry:
  `species_source` (environment), `reaction_host`
  (lumped/distributed/point), `species_transport` (mass_transport →
  diffusion/convection inherit).  Exposed on `/entity-types`.
- **Modeller gestures** — capability-gated pickers in the Properties
  panel: a `species_source` node picks its allocation
  (`promo:speciesAllocation`), a `reaction_host` toggles reactions
  (`promo:hostsReaction`), a `species_transport` arc gets per-species
  permeability (`promo:permeable`; absent = all pass).  The model
  names its species artefact via `?species=`.
- **Distribution → `S`** — `/api/instantiate/model` and `/code` take
  `?species=`: the service reads the placements + artefact, runs the
  fixpoint (`instantiate/distribute.py`), and `build_model` binds the
  species index to the union over each variable's topological extent.
- **Model-level aliases (2026-09-23)** — `promo:speciesAlias` map in
  the model document (`GET`/`PUT /api/modeller/model`); modeller
  toolbar **Species aliases** dialog
  (`apps/modeller/src/SpeciesAliasDialog.tsx`); pickers resolve
  `alias ?? label ?? frag`.
- **Model→species pin (2026-09-23)** — `promo:usesSpecies` on the
  model graph IRI: stamped at creation (`uses_species` on
  `/api/catalogue/new`), copied on fork, replaceable on drafts via
  `PUT /api/catalogue/pins`, surfaced in the hub (chips + Species…
  button).  The modeller resolves the scheme from the pin —
  `?species=` is now an override that re-stamps the pin on save —
  and `/api/instantiate/model` + `/code` fall back to it.

```

## 21. Admissibility — moves preserve the closed-subgraph invariant (2026-10-27)

### Terminology (pinned)

- **variable** — the symbol being defined.
- **expression** — the right-hand side, a formula over variables.
- **equation** — the pair `variable := expression`; the unit of
  selection in the BL.  A variable may own several equations
  (alternative expressions).

### The invariant

An assignment is an ordered list of definitions
`v₁ := e₁, v₂ := e₂, …, vₙ := eₙ` where each expression `eᵢ` may only
reference variables defined at positions `< i` or endpoints.  The
lower-triangular sequence **is** the data structure — not a check
applied on top.  This is the same principle the equation editor
already enforces at authoring time (an expression can only be written
once its constituent variables exist); the BL applies the positional
version: "defined" = bound to an expression at an earlier slot (or an
endpoint), not merely declared.

Consequence: declaration-before-use does **not** prevent
equation-level cycles in the store (`a := f(b)`, `b := g(a)` are both
authorable).  The triangular sequence breaks them by construction —
whichever order is picked, one equation consumes a not-yet-defined
variable, so a closed assignment simply cannot contain the pair.  The
only cycle that survives is the integrator loop through the state
variable.

### Endpoints (all four must be matched)

- **state** — the base equation's LHS; owns the integrator loop.
- **instantiated** — variable bound to a value (constant/parameter
  class or `promo:value` pre-binding; explicit marking).
- **port** — external input, satisfied across a model arc.
- **output** — external *sink*: a variable computed for
  observation/measurement/recording that nothing else consumes.
  Declared outputs are **roots of the reachability check** alongside
  the base cone — an equation feeding an output's cone is legitimately
  in the subgraph.

### Moves, not edits

The user never edits the sequence into a broken state.  Every
operation is a *move* whose result must restore the invariant —
each move is a re-closure:

- **Choose base equation** — opens the integrator loop; its
  expression's variables become the frontier to resolve.
- **Pick `v := e′` for an unresolved `v`** — the candidate list is
  restricted to expressions that keep the subgraph completable; the
  act of picking *is* the closure step.
- **Exchange an expression for `v`** — drop `v := e`, take `v := e′`;
  `e`'s now-exclusive provider subtree is pruned; `e′`'s variables
  must already be defined before `v`'s position or their definers are
  pulled in and the sequence repositioned so `v` sits after them.
- **Delete `v := e`** — everything only needed by `e`'s cone is
  pruned; whatever `v` fed reopens as unresolved and resolution
  continues until endpoints are matched again.
- **Unmark an output** — re-runs pruning: if its cone is not needed
  elsewhere, it is dead.

"Unreachable" is therefore not a report category — it is a transient
that the move completes or prunes.  An equation can only be
unreachable if it feeds neither the base cone nor a declared output,
and that state never persists past a move.

### What changes in the current engine

- `closure.py` today *evaluates* a selection: unreachable is a
  warning, `resolveWith` appends without replacing, `removeEq` filters
  without cascading.  Under §21 the engine **computes the minimal
  sequence change that restores the invariant** for each move.
- `lhs_class` folds into candidate filtering — the expressions offered
  for `v` are those that keep the subgraph completable, not a hard
  gate.

### Open

- Exact prune semantics on delete (full cascade vs. reopen
  dependents) — the moves above assume cascade; confirm in UX.
- Whether output endpoints persist as `promo:hasOutputVariable` on the
  assignment artefact (symmetric with `hasInstantiatedVariable` /
  `hasPortVariable`).

## 22. Referenced composites — model reuse (2026-10-28)

### Premise

All models share one data model (same `promo:Model` /
`promo:ModelNode` / `promo:ModelArc` / `promo:Composite` machinery),
which makes any model usable as a building block.  A reused model
appears in the host modeller as a composite whose content is a
**reference** to another model artefact — not inline children.

### Refer, don't copy

A referenced composite carries `refersTo` → model artefact IRI plus
an **override map**; children stay empty.  Copying at save time is
rejected: copies fork evolution silently, lose provenance, and
duplicate the artefact-level Fork gesture that already exists.
Live reference gives propagating fixes — instantiations are computed
anyway, so every host picks up submodel changes on next build.
Reproducibility is a pin concern (freeze the referenced artefact at a
version), orthogonal to the mechanism.

References nest recursively — a referenced model may itself contain
referenced composites.  Resolution walks the reference DAG; a
transitive self-reference is a `reference-cycle` problem.
Referrer discipline: the catalogue reports "N models reference this"
before delete/interface-breaking edits.

### Interface — declared in the referenced artefact

The referenced model's **open arcs are its interface**, captured at
save time: each boundary terminal carries arc type + carrier token +
direction (§15 sign convention across the boundary).  On insert, the
terminals surface as the composite's connectable endpoints; the
modeller's `resolve-connection` answers admissibility of host node ↔
terminal connections from the same rule machinery — the artefact
declares, the ontology adjudicates.

### Per-occurrence instantiation

The unit of instantiation is the **use site**, not the artefact:

- Each composite occurrence instantiates independently — two uses of
  the same submodel yield two instances with disjoint emitted names.
- Instance paths extend the `<internal_id>@<entity-type frag>` scheme
  hierarchically: `exchanger_1/pipe_3@lumped`.
- **Effective context** = submodel's own pins (ontology, library,
  species, saved value/fix defaults) + per-occurrence **override
  map** on the composite (absent key → submodel default).
- Overrides must still *cover* the referenced artefact: a substitute
  species scheme must provide compatible components for the
  submodel's placements; a substitute var/expr graph must define the
  referenced assignments' symbols.
- **Boundary check**: species crossing a port must exist on both
  sides — same class of check as token comparability.
- The host's `promo:Instantiation` carries one sub-plan per
  occurrence keyed by occurrence path (`generatedFrom` → host).
  A standalone submodel instantiation is the degenerate case
  (occurrence path = root).
- Codegen stays call-style (approach 2): each level instantiates
  against its own index element sets; only port values cross the
  boundary.

### Modification of an embedded submodel

The reference is **not an editing channel**.  Three operations, no
structural overlay:

- **Parameterize** — per-occurrence overrides only.
- **Edit the artefact** — open the referenced model itself; changes
  propagate to all referrers (catalogue warns).
- **Fork + re-point** — hub Fork produces a private variant; re-point
  `refersTo` to the fork.  The per-occurrence delta is an artefact
  identity change, never a hidden diff.

Plus one escape hatch:

- **Dissolve** — one-way conversion replacing the referenced
  composite with an *inline* composite containing a copy of the
  referenced content (nodes, arcs, knots, open-arc terminals).
  Existing external arcs remap onto the copied terminals so the
  host topology is preserved; active overrides fold in as explicit
  content (the copy gets its own `usesSpecies` pin etc.).
  `dissolvedFrom` records source artefact + version.  From then on
  it is ordinary host content — the link is severed.

A host-stored patch/overlay on top of a reference is **rejected**:
silently breaks on submodel evolution, duplicates topology ownership,
needs merge machinery that Fork already provides.

### Gestures implied

1. **Save-as-composite** — lasso/subtree selection → new model
   artefact; boundary-crossing arcs become its open arcs (extraction
   decision per save; outside peers are dropped).
2. **Library pick** — catalogue lists model artefacts with
   label/pins/interface summary (open-arc count, token, direction).
3. **Insert** — places a referenced composite; the saved model's open
   arcs materialise as terminals.
4. **Connect** — host arc ↔ terminal via `resolve-connection`.
5. **Override** — per-composite override map editor (species, values,
   pins).
6. **Dissolve** — flatten reference to inline content.

### Open — resolved 2026-10-29

- **Predicate — both.**  `promo:refersTo` on the `promo:Composite`
  resource is the authoritative per-occurrence mechanism (sits next
  to `openArcs`/override map).  `promo:usesModel` on the host graph
  IRI is a *derived index* — rewritten on each save, same shape as
  `usesSpecies` — so referrer-count and dependency queries stay
  cheap without scanning every composite.
- **Save-as-composite — move.**  Extraction replaces the selection
  with a referenced composite in place ("refactor into submodel");
  boundary arcs remap to terminals.  Copy is rejected — it
  duplicates content that then drifts, and Fork already covers the
  copy use case.  Gesture name: *Extract to submodel*; dissolve is
  the undo path.
- **Frozen references — deferred.**  Right granularity is
  per-composite (`refersTo` + version qualifier — two uses may pin
  different versions), but the pin shape depends on hub artefact
  versioning, which does not exist yet (Fork only makes new IRIs).
  To be designed with the versioning model — probably
  commit/tag-style IRIs rather than mutable artefact IRIs.

### Status — implemented 2026-10-29

- **Persistence**: `refersTo`/`overrides`/`dissolvedFrom` on
  `promo:Composite`; derived `promo:usesModel` rebuilt on PUT.
- **Extract/dissolve**: `POST /api/modeller/extract-submodel` (move
  semantics, boundary arcs → open arcs both sides) and
  `POST /api/modeller/dissolve` (flatten + provenance).
- **Resolution**: `GET /api/modeller/references` (DAG + cycles);
  catalogue `usesModel`/`referencedBy` + delete guard.
- **Modeller UI**: submodel palette (insert → declared interface as
  terminal stubs), terminal connect adjudicated via
  resolve-connection using the declared `externalEntityType`,
  override editor, extract/dissolve actions.
- **Instantiation**: `_collect` expands references into per-
  occurrence instance paths (`comp/inner`), boundary arcs re-point
  at occurrence instances; `_occurrence_contexts` merges each
  occurrence's effective context (submodel pins re-pointed by
  overrides) into vars/assignments/species/value-cells; problems:
  `reference-cycle`, `uncovered-override`, `species-port-mismatch`.
- **Nested sub-plans — resolved 2026-10-31**: `POST
  /api/instantiate/instantiations` writes one `promo:Instantiation`
  per occurrence inside the host artefact — `hasSubPlan` link,
  `occurrencePath`, `instantiates` → referred artefact, `overrides`
  JSON, effective-pin provenance
  (`usesLibrary`/`usesAssignment`/`usesSpecies`/`usesValues`, the
  override-resolved context `_occurrence_contexts` computed against)
  and a `promo:plan` JSON sliced by `sub_plan_slice` (direct
  ownership only — nested occurrences own their content;
  boundary-crossing loops stay with the host).  Call-style codegen
  (approach 2) was already in the emitters.

### Codegen architecture — resolved 2026-10-29

The global-equation vs block-sequential debate dissolves into
levels: **merge cones for analysis, parallelise for execution**.

- **Analysis is global.**  Reference expansion (§22) makes all
  occurrence cones one equation set with shared IRIs — a port is
  *one* variable one side defines and the other consumes, not a
  cut-variable pair needing a connection equation (the Modelica
  cut-equation machinery is unnecessary — IRIs already bind across
  the boundary).  The scheduler sees true global dependencies and
  finds every coupling loop, including boundary-crossing ones.
- **Parallelism comes from the schedule, not the artefact
  boundary.**  Blocks at the same scheduler level are independent
  by construction — host and occurrences at one level evaluate
  concurrently with no per-artefact awareness.  Inside an SCC the
  cone structure pays differently: the Jacobian is block-sparse
  *by cone*, interior variables eliminate locally (Schur
  complement), and only boundary variables enter the outer
  iteration — conservation's linearity confines nonlinearity to
  the cone interiors.
- **Call-style is emission formatting.**  The artefact boundary
  matters for the generated *source* (per-artefact functions for
  readability/reuse), not for scheduling — it never constrains
  the dependency analysis.  Emitters: blocks within a level emit
  as independent tasks (`Threads.@spawn` / `parfor`-style);
  SCC blocks emit a `SolveRoot` over the cone-blocked Jacobian.

Terminology: **interior cone** (entity's closed assignment
subgraph — the codegen unit), **boundary coupling** (the shared
port variables), **conservation network** (the sparse `F[N,A]`
outer system), **coupling loop** (algebraic loop crossing a
composite boundary).

## 23. The token model — who declares what (2026-10-29)

Port satisfaction (§13/§14) and donor directionality (§15) both
depend on knowing **which conserved or reference quantity a variable
is**.  This section records the complete token model, because the
declaration sits in a different place than in old ProMo.

### The three levels

Tokens appear at three layers of the artefact stack, each answering
a different question:

| Layer | Declaration | Answers |
|-------|------------|---------|
| **Ontology — connection rules** | `promo:sharedToken` on rules; `resolve-connection` returns `matched_tokens` | What *may* flow between these two domains? |
| **Ontology — entity types** | implicit in the mechanism taxonomy (§16: `mass_transport` transports mass, `heat_transport` transports energy) | Which token does this transport *mechanism* move? |
| **Var/expr — variables** | `promo:carriesToken` (`VariableRecord.tokens`) | Which token does *this variable* quantify? |

Arcs carry **no token declaration** — arc type is only the carrier
category (`token-flow` vs `reference`).  The token flowing on an arc
is not chosen at connect time; it falls out of the entity types and
the rules that licensed the connection.

### Why the variable declares it

In old ProMo the token was introduced **via the connection** — the
arc was simultaneously topology, carrier, and token declaration.
That overloaded the arc (multi-token contacts needed composite
tokens or multiple arcs) and entangled it with direction, which is
part of why §15 had to relocate orientation to per-contact
`referenceFrom`/`referenceTo`.

The new split puts each fact where it intrinsically lives:

- A concentration **is** a mass quantity — `promo:c carriesToken
  token_mass` completes the variable's own declaration; it is not
  extra annotation, it is the variable's physical type.
- The rule's `matched_tokens` say what *may* flow; `carriesToken`
  says what the variable *is*.  Port satisfaction is the
  comparability of the two (§14).
- The arc stays minimal — bidirectional carrier only; direction and
  token are both relocated to their owners.

### The contract this creates

- **`carriesToken` is what makes a port licensable.**  A
  `port_variable` with no token is demand-shaped but semantically
  untyped — `port-satisfaction` reports it `unlicensed` regardless
  of the arc.  (Surfaced live on `promo:c`, 2026-10-29.)
- **Consistency is checkable, not enforced.**  A variable's token
  can disagree with the licensed tokens — the connect-time check
  reports it rather than blocking.  The check exists precisely
  because the declarations are now separate.
- **Comparability is ancestry** (§14): `observation` ports accept
  arcs licensed for `signal`, mass subtokens match `mass`.

### Tagging convention (settled 2026-10-29)

The thermodynamic fundamental relation `U(S, V, n, …)` is the
organising principle: the extensive arguments name the token
networks — `S` → entropy, `V` → **mass** (the space token is tied
to the mass network; volume and pressure form its work pair), each
`n_i` → **component_mass**, `U`/`T` → energy, mechanical frame
quantities (`r_x`, `r_y`, `r_z`, `Axy`) → momentum.  Secondary
variables ride the token of their network (`rho`, `fm_conv`,
`k_conv` → mass; `Mm`, `dndt`, `fn_conv` → component_mass).  Vars
that are not token quantities — direction flags, times — carry no
tag at all.  The first sweep applied this to the seeded library:
26 vars tagged (`4fb2628`).

### The cost

- **Annotation burden** — port variables want `carriesToken` or the
  modeller cannot adjudicate them.  Old ProMo never asked for the
  tag because it never asked the variable to type itself.
- **Open policy** — whether `carriesToken` becomes *required* for
  `port_variable` at authoring time (equation editor validation)
  rather than discovered `unlicensed` at connect time.  Leaning
  toward required: a port that cannot name its token is not a
  usable demand.
- **Guard interaction** — `tokens` is a §18 structural field;
  adding `carriesToken` to an in-use variable is API-blocked (the
  field is locked once equations reference the variable).  Whether
  *adding* a token where none existed should be exempt is a
  guard-policy question — today it requires a data-level edit.

### Terminology note

"Token" unifies what physics calls conserved quantities (mass,
energy, momentum, charge, component-mass) with reference quantities
(signal and its `observation`/`manipulation` subtokens).  Both
travel through the same licensing machinery; the distinction lives
in the token taxonomy's `promo:kind` (conserved vs reference), not
in separate mechanisms.

## 24. Variable classification — quantity-kinds, claims, and the physics vocabulary (2026-10-31)

Two parallel systems classify variables today: the flat
`promo:variableClass` (original vocabulary `state, effort,
transport, frame, network, constant, parameter`) and the axis-based
`promo:axisValue` (`determination`, `extensity`, `function`,
`role`).  The `deriveType` bridge proved they are not two systems —
the flat class is a *projection* of the axis state — while the UI
let both write the same field, so two vocabularies fought over one
string (a picked `transport` was silently overwritten by the
bridge's `state`).  This section records the resolution: the
terminology must serve physics and system theory, and modelling
assumptions must be crystal clear — first-class, relaxable data —
because engineering shorthand ("a transport element just
transports") hides the capacity that is not incorporated, the cause
of real modelling problems.

### The canonical loop — nature vs position

The basic diagram: an integrator takes a **state derivative** and
generates a **state**; thermodynamics and geometry transform the
state into **secondary states** (mostly intensive, some of which
are effort variables); the secondary states compute **transport**
and **reactions**; these come together into the state derivative.
**Control** takes measurements from state and mostly secondary
states and manipulates the flows.

The axes record a variable's *nature* — what it physically is.
Its *position* in this loop (integrator output, derivative input,
law output) is structural — it falls out of the equations and the
topology, and is never a class.

### One stored truth

- **`promo:axisValue` is the only write target.**  `variableClass`,
  its dropdown, and `deriveType` go; the flat class survives only
  as a *derived display* (`kind: flow · intensive ·
  variable`), never stored.
- **Legacy consumers all reduce to one test.**  The Instantiate
  gate (`INSTANTIATE_CLASSES`), auto-instantiation, and the
  behaviour `lhs_class` filter all mean "bound-value": `determination =
  constant OR function = parameter`.
- **Vocabulary fidelity is cheap** — axis terms are data; where the
  old class and the function axis diverged the term follows the
  variable's nature, not the legacy word (`flow`, not `transport` —
  `transport` stays where it belongs: the phenomenon on the entity
  side).

### Function axis = quantity-kinds (one world)

The six terms are mutually exclusive answers to "what kind of
physical quantity is this variable":

| Term | Nature |
|------|--------|
| `state` | coordinate of a state representation (see below) |
| `effort` | intensive driving potential |
| `flow` | throughput rate — conjugate to effort |
| `reaction` | transformation rate |
| `frame` | reference coordinate (time, space) |
| `parameter` | constitutive characteristic, often embodying an assumption |

`transport` and `reaction` also name *phenomena* — that is the
other world, the entity side (§16 mechanism taxonomy).  A
transport variable is the *flow produced by* a transport process,
not the process itself; same words, different axes.

### Entity side — reality vs claims

Reality is distributed; everything else is a claim:

- `+ lumped` — spatial simplification → storage capacity
- `+ event-dynamic` — temporal simplification (very fast) →
  **transport system** := distributed element + event-dynamic
  claim, i.e. a *dissipation* element: it transports iff an effort
  difference exists
- `source` — boundary (environment); `junction` — arc balance;
  `transduction` — reaction host

`transport` is therefore introduced when *designing the basic
entities* — a named composition, not a primitive kind.  The regime
assumption is relaxable data (cf. §17 scale regimes and the
event-dynamic bindings): drop the fast claim and the same element
re-models as an accumulating distributed system — the neglected
holdup was there all along.

### State — resolved

State is the core of a dynamic representation: infinitely many
representations exist, but a **minimal dimension** does not change.
In physics, the conserved quantities form this minimal state space.

- **`fundamental-state`** — conserved quantity; candidate member of
  the minimal set.
- **`secondary-state`** — image of the states via thermo/geometry;
  not a coordinate at all.
- **bare `state`** — a legal non-conserved coordinate of a
  representation (e.g. integrating `T` instead of `U`: same
  dimension, transformed basis).
- **State reduction is a claim**, already mechanized: "constant
  volume" pins `V` → `determination: constant` at the occurrence —
  the existing pin/override machinery *is* the state-reduction
  machinery.  The minimal set is a derived readout on the
  instantiated system: `{fundamental-states} − {pinned}`.

### Unclassified — resolved

The physical domain has no unclassified nature: every variable is
*something*, so a missing `function` means **incomplete authoring** —
a completeness marker (`needs classification`), and gates reject
with "what is X?" rather than silently assuming `state` (the old
reader default that hid `fV`'s real classification).  On the
*information* branch the axis is simply inapplicable: a signal
carries `role: input/output`, not a physical nature — inapplicable,
not unanswered.

### The unifying pattern

The same machinery recurs at three levels: **reality vs claims
about it** — distributed vs lumped (spatial), accumulating vs
event-dynamic (temporal), conserved vs pinned (state reduction).
Assumptions are inputs, not identities.

### Open threads

- **`effort`** — own function term, or `secondary-state` +
  `intensive` + a driving-force *role*?
- **Regime mechanics** — a `promo:regime`-style claim triple vs the
  current event-dynamic entity-type bindings.
- **Control side** — measured-vs-manipulated: does `role:
  input/output` suffice, or does function want signal terms?
- **Axis display names** — e.g. `determination` as "fixed or
  varying" in the user's words.

Implementation (variableClass removal, seed renames, gate rewrites,
minimal-state readout) follows after this section is reviewed.

---

## 25. Incidence factors are seeded scheme objects (2026-11-01)

### The problem

`promo:F_conv` existed twice: a port-variable-era description in the
ontology artefact (`portVariable true`, single index `A_conv`,
`internalID V_4`) and the current `[A_conv, N]` constant/parameter
record in the library artefact (`V_25`). One IRI, two divergent
descriptions — under the union read (`RdfContext` resolves variables
over artefact + `usesOntology` pins) scalar predicates pick
arbitrarily. The question "all network-dependent equations should use
the same objects" exposed the missing rule for *where a shared
variable lives*.

### Decision

- **Home: the ontology graph.** Resolution scope is artefact ∪ pinned
  ontologies — a variable is visible only upstream in the pin chain.
  `F_*` are needed by the ontology's own equations and by every
  library using the ontology; the ontology graph is the only home
  that reaches all of them.
- **Derived, not authored.** Every field of an `F_*` record is a pure
  function of its arc sub-index: name `F_<mech>` from the
  `idx_arc_*` IRI, indices `[A_k, N]`, determination `constant` +
  function `parameter`, dimensionless units, LaTeX `F`, doc — and the
  token follows the mechanism tree: sub-index `selector` → entity
  type → `promo:parent` walk to the `mass_transport` /
  `energy_transport` group → `token_mass` / `token_energy`. Zero user
  content → a floor migration `_seed_incidence_factors`, run from
  `load()` like `_seed_arc_sub_indices` (§17 seed contract). A new
  mechanism sub-index materialises its factor at next load; deletion
  resurrects, so the reserved records cannot drift or be forked.
- **Cleanup.** The authored copies are removed: the ontology V_4
  description is superseded by the seed; the library V_25 and the
  API-made `F_heat` become redundant (same IRI resolves to the one
  ontology record). The legacy ontology equation
  `sign(F_conv * p_mech)` uses the single-index form and is rewritten
  to the `[A_k, N]` contraction.
- **Guard.** A save-time check on the equation-editor write path
  rejects a variable whose IRI is already defined in another in-scope
  graph with a different shape — the structural fix for the
  V_4/V_25-class split brain. (Deferred with the seed; listed as an
  open thread in concepts §8.)
- **Reserved shape is unchanged.** Instantiation's `incidence`
  binding (§19) keys on constant-class + `[node, arc]` shape; nothing
  downstream needs to know which records are seeds.
- **Editor.** "New incidence factor…" is redundant once factors are
  seeded — retired with the migration; its mechanism→record
  derivation logic moves into the seed function.

### Consequences

- Network-dependent equations across all artefacts reference one
  `promo:F_*` object — literally the same subject, not a copy.
- The dialog's hand mapping (`TOKEN_GUESS`) is replaced by the
  ontology-structural derivation — no guessing when new mechanisms
  appear.
- Concept documented for users in concepts-and-architecture §3.5
  (structure handles) + terminology entry; authoring guide notes the
  factors are referenced, not authored.
- Same pattern earmarked for stoichiometric matrices when reaction
  instantiation lands.

## 26. Instance IRIs are absolute and live under their artefact's namespace (2026-11-01)

Problem, found while finishing §25: three historical mints produce
*relative* URIs — `<promo:F_conv>` (variables), `<promo:Model/Node_1>`
(model records), `<promo:ArcType/token-flow>` (synthesised arc types).
The strings look like prefixed names but are whole base-less,
scheme-less URIs: in the TriG files `promo:F_conv` (prefixed name,
expands to `https://w3id.org/promo#F_conv`) and `<promo:F_conv>`
(relative URI) are *two different subjects*.  That is exactly what
split the seeded incidence factor from the authored record — the seed
spelled the IRI one way, every reference the other.

Rule: **an instance IRI is absolute and lives under the namespace of
the artefact that owns it.**  The artefact owns what exists; the IRI
says so.

- **Variables**: `promo:X` → `{home-graph}#<label>` — the equation-IRI
  precedent (§`_migrate_equation_iris`) applied one level up.
  Home = the graph holding the variable's equation subjects, else the
  graph with the richer record.  Duplicate records (`Axy`, `p_mech`,
  `p_term` — same internalID, written into both `ontology` and
  `library` by earlier write paths) are merged into the home graph;
  the `promo:V` ontology stub (empty `V_8`) merges into the real
  library record (`V_23`).  Expressions are untouched: they resolve
  `network!label`, never IRIs.
- **`global_ID`** = the canonical IRI.  It *is* the global
  identifier — a `promo:X` spelling was the same defect one layer
  down.  `rdf_context` falls back to the full IRI, not the fragment.
- **Model records**: `promo:Model/Node_n` → `{model}Node_n`,
  `promo:Arc/Arc_n` → `{model}Arc_n` — the flat `model/Composite_0` /
  `model/Model` convention the persistence layer already uses.
- **Arc types**: `promo:ArcType/<carrier>` → `promo#ArcType/<carrier>`.
  A synthesised, shared, vocabulary-side resource — the honest
  expansion of the prefixed name the mint intended.
- **Rewritten everywhere**: subject triples, object references
  (`lhs`, `hasEquation`, `hasInstantiated/Port/StateVariable`,
  `instanceOf`, `source`/`target`/`referenceFrom`/`referenceTo`,
  canonical `rdf:first` argument lists), and `promo:` tokens inside
  JSON literals (`incidenceList`, `aliases.global_ID`, `children`,
  `knots`).  Tokens with no subject anywhere (e.g. the long-dangling
  `promo:c`) expand to `promo#` — a dangling absolute IRI beats a
  dangling relative one.
- **Frozen version graphs are not rewritten** — a published snapshot
  keeps the spellings it was published with.
- **Mints move to the canonical form**: frontend
  `promo:${lhs}` → `{graph}#${lhs}`, `ModelGraph` prefixes,
  `ARC_TYPE_PREFIX`, and the §25 seeds write `{graph}#` directly.
- **Guard**: the variable/equation write path rejects relative IRIs —
  the deferred §25 same-IRI-redefinition guard lands here: nothing
  without a URI scheme gets stored again.

Migration `_migrate_variable_iris` runs at `load()` like its equation
counterpart — idempotent, both machines converge on next load.

### Shape table (normative, 2026-11-01)

Single definition sites: `backend/core/iri.py` (server) and
`packages/semantic/src/iris.ts` (clients).  Two join conventions —
`#` names a vocabulary member, `/` names a subordinate resource:

| Shape | Constructor | Used for |
|---|---|---|
| `{base}#{frag}` | `vocab_iri` | Vocabulary members of an artefact: variables (`variable_iri`, frag = internal ID `V_n` — rename-stable), equations (`equation_iri`, frag = internal ID `E_n`), domains, entity types, indices, tokens, assignment resources (`{assignments}#assignment_<etype>`) |
| `{base}/{seg}` | `child_iri` | Subordinate resources: `{graph}/Model`, `{graph}/Composite_<treeId>` (deterministic, ADR-007), `{graph}/Node_n` (`model_node_iri`/`modelNodeIri`), `{graph}/Arc_n` (`model_arc_iri`/`modelArcIri`), `{eq}/expression`, `{base}/assignments` artefact, species members `{graph}/{Kind}_{stamp}` |

**Artefact graph IRIs are slash-free names** (`…/ontology`,
`…/library`, `…/model`, `…/library/assignments`, `…/ontology/1.0`).
`_normalize_graph_iris` rewrites trailing-slash identifiers at
`load()` — graph triples move to the canonical context, pin /
`versionOf` / `refersTo` references follow (also inside frozen graphs,
which keep their own published names), and `{old}#x` vocabulary
members rehome to `{new}#x`.  `child_iri` makes `/`-joined member
IRIs identical under both spellings, so model/species record IRIs are
untouched.  `canonical_graph_iri` normalises `?graph=` input so old
session URLs keep resolving.

Synthesised (read-only, never a stored subject):

| Shape | Constructor | Used for |
|---|---|---|
| `promo#ArcType/<carrier>` | `arc_type_iri` | Arc-type vocabulary — server-synthesised on `ConnectionRuleRecord.arc_type_iri`; clients consume, never construct |
| `{ontology}#F_<mech>` | `f_factor_iri` | Seeded incidence factors (§25) |
| `promo#{local}` | `vocab_ns_iri` | Expansion of a bare `promo:` token with no owning subject (migration fallback) |

Helpers: `local_name` (last fragment after `#` or `/`), `is_absolute`
(the write-boundary guard), `occurrence_prefix` (§22 instance paths
`{composite}/`).

**Who mints**: the server owns every IRI it writes — variables are
POSTed with `iri: ''` and come back `{graph}#{internal_id}`
(store-minted `V_n`; labels are data, never keys — a rename touches
no reference).  Seed-floor records follow the same rule with
deterministic IDs: `const_zero` / `F_{mech}` are the internal IDs,
so `{graph}#{iid}` reproduces their readable IRIs.  Clients mint
only whole-document topology IDs (model Node/Arc, species members)
that the server stores verbatim under `PUT` document semantics.

**Resolved seams** (2026-11-01): the two earlier inconsistencies —
mixed artefact-IRI spellings (`…/library/` vs `…/ontology`) and the
bare-concat `{graph}Node_n` convention that produced
`test-modelNode_3` on slash-free graphs — both collapse under the
slash-free-graph + `/`-child convention above.  `_migrate_variable_iris`
rehomes non-variable subjects via `child_iri` for the same reason.

## 27. Ontology composition — artefacts compose via pins, nothing merges (2026-11-01)

Prompted by §26's cleanup: with every member IRI namespaced to its
owning artefact, combining vocabularies can never collide on
identifiers — the open question is only *resolution semantics*.

### Premise

An ontology is just an artefact (`promo:Ontology` marker).  The store
already knows how to keep several side by side — `…/ontology`,
`…/library`, `…/model`, each its own line in `data/`.  "Combining
ontologies" therefore splits into three distinct modes:

- **Extension** — artefact B builds on artefact A's vocabulary.  This
  is the `usesOntology`/`usesLibrary` pin, and it already works.
- **Alignment** — two independently-authored vocabularies describing
  overlapping domains (community ontology vs core).
- **Physical merge** — one graph absorbs another's content.

### Decision

**Artefacts compose via pins; nothing merges.**  Concretely:

- `resolution_scope(graph)` is the artefact's vocabulary context: the
  graph itself plus the *transitive* `usesOntology`/`usesLibrary`
  closure, breadth-first, cycle-safe.  A model pinning a library sees
  the library's ontology set without re-declaring it — pin chains
  stay shallow (a new artefact stamps only its *direct* pins; the
  closure does the rest).
- `usesAssignment`/`usesSpecies`/`usesModel` are **resource pins**,
  consumed by their own services (behaviour vend, species panel,
  §22 referenced composites) — they deliberately do *not* enter the
  vocabulary scope: an assignment graph holds no entity types, a
  species graph no equation vocabulary.
- Pins may name **frozen version IRIs** (`…/ontology/1.0`) — that is
  the reproducible-dependency form; a draft pin tracks the moving
  line.
- **Extension never copies**: a user ontology pins the core, it does
  not inherit the seed floor.  The floor self-repairs only in
  `ONTOLOGY_GRAPH_IRI` (§floor scope) — composition over inheritance.
- **Alignment is a mapping artefact** (deferred): a graph of
  `promo:equivalentTo` claims between `ontA#x` and `ontB#y`, consumed
  by the rule resolver's `promo:parent` walk and the checker's type
  equivalence as a synonym expansion.  Build when a second ontology
  actually exists — the machinery is a day of work for zero users
  today.
- **Physical merge is not a strategy.**  The `promo:`→absolute
  rehome machinery (`_migrate_variable_iris`) is the precedent for
  what a merge *would* look like — subject consolidation with
  provenance loss — kept as a healing tool, not a path.  When a
  community ontology matures into the standard library the route is
  mapping artefact + a rehome migration, not graph surgery.

### Consequences

- Identity is stable across artefacts by §26: `{graph}#{internal_id}`
  variables and `{graph}/x` members mean a cross-artefact reference
  (`lhs`, `instanceOf`, assignment roles) survives edits on either
  side.  Rename affects nothing outside the record.
- Label ambiguity is a *display* problem, not a data problem: two
  ontologies may both define `conv`; resolution is exact-IRI, and the
  picker must qualify by home (`conv (my-lib)` vs `conv (core)`).
- `usesOntology` pins from a dependency flow *through*: model →
  library → ontology gives the model both vocabularies.  Tested in
  `test_graph_store.py` (`resolution_scope` suite).

### Open threads

- `promo:equivalentTo` predicate + resolver expansion (alignment,
  above).
- Label qualification in pickers once a second ontology exists.
- Hub UI: pin editors already offer every artefact's draft + frozen
  versions — nothing to add.

## 28. Event-dynamic entities, transport-law ownership, and rule granularity (2026-11-02)

Reviewing the simple-system chain (environment → convection transport
→ lumped) surfaced where `state` comes from and who may own a
transport equation.

### Decision

- **Event-dynamic = stateless assignment shape.**  `state` was
  hardcoded to `lhs(base_equation)` — a transport's base LHS is its
  flow output, not an accumulation.  `base_equation = null` suppresses
  the derivation entirely: `closed=True`, `state=None`, sequence +
  outputs intact.  The environment's no-base shape generalises.
- **Regime switching = artefact swap, not parametric zero.**  An
  event-dynamic transport is physically a C→0 capacity, but setting
  accumulation to zero turns the state algebraic — a value decision
  with a structural (DAE) consequence.  Instead: same entity type,
  two assignment *shapes* (stateless vs state-bearing); the switch
  happens at model time by re-assignment.  No algebraic-state
  machinery needed yet.
- **Entity types already carry `temporal_type`** (`event-dynamic` on
  every transport leaf) — the no-accumulation signal exists on the
  ontology side; wiring it into closure (expect stateless on
  event-dynamic types) is open.
- **Transport equations live on transport entities.**  A lumped
  capacity owns balances over ports, nothing else — a flow with no
  second end is source/sink or conversion, a different mechanism and
  a different entity.  When the BL offers another entity's equation
  (entity-agnostic candidates), the fix is visibility — *"E_4 is
  claimed by convection_transport"* — not prohibition: reuse stays
  possible when intentional, but seen.

### Gaps found

- **Connection rules are domain-pair + shared-token only.**  All
  physical entity types share `domain_physical`, so env→env is
  indistinguishable from lumped→transport — `rule_physical-same`
  licenses a token-flow between two environments.  "Token exchange
  requires a transport endpoint" is inexpressible in the current
  schema → needs entity-role-aware rules (ontology data), not a
  gesture hardcode.  Related UX bug: the sync resolver's cache-miss
  answer `allowed` + `connections:[]` paints the hover 'valid' before
  the authoritative (forbidden) answer lands.
- **The delete cone is single-artefact.**  Variable delete scans
  var/expr incidence refs; assignment endpoint refs
  (`hasInstantiatedVariable`, ports, state, outputs, sequence) are
  cross-artefact and invisible → a deleted `k_conv` left a dead IRI
  in the transport's instantiated list.  Proposed: a read-only
  cross-artefact integrity audit (endpoints/sequences → vars/eqs,
  model entityType refs, instantiation pins, stale caches incl.
  `promo:closed` vs live and stored `incidence_list` vs re-check)
  plus extending the delete cone to assignment references.
- **Graphic-designer extent contract.**  Any spatial constraint must
  read the object's own bounding box, never a shape constant — the
  coming node graphic designer MUST declare one.  Implemented:
  `SceneNode.halfExtent` + `graphicalHalfExtent`/`entityHalfExtent`
  (zone clamp migrated; hit-test and rim-attach to follow).

## 29. Port gathers across peers, index-broadcast semantics, value-cell UX (2026-11-02)

### Found and fixed (settled — machinery corrections)

- **Port gathers must split per peer.**  `plan.py` grouped a port
  var's contacts by `(etype, var)` and served all contacts from
  `pbs[0]`'s peer field.  A 2-contact transport whose contacts resolve
  to different peers (upstream env pressure, downstream lumped
  pressure) got `[env[0], env[-1]]` — the `-1` was `pos.get`'s
  not-found sentinel but Python reads it as a valid index →
  `[p_up, p_up]` → `F@p = 0` → zero flow, silently.  Contacts now
  batch into runs sharing a peer; runs split at peer changes and emits
  concatenate sibling pieces in contact order (`gather_multi` in all
  three dialects).  The shared var-keyed cell table (`V_34` values at
  `Node_1`/`Node_3`) is what makes the element-keyed gather work.
- **Numeric-shape normalisation** (recorded for the pattern):
  `np.ravel` at every vector-concat site (cell tables keep bound index
  shape, e.g. `[[v]]`); `np.atleast_1d` on runtime pars (port-gather
  fancy indexing can't read 0-d); `np.asarray(x).item()` wherever a
  scalar is required — NumPy 2.x rejects `float()` on ndim≥1 arrays.

### Open questions

- **Index-broadcast semantics (DECISION NEEDED).**  `fmc` is declared
  `A_conv[2]×N[1]` but its defining law `k·A·(F@p)` produces a
  per-node value — `F@p` contracts the contact index away.  Should a
  RHS whose index space is a subset of the LHS's broadcast implicitly
  over the missing index (here: same flow on both arcs — the right
  serial-transport physics)?  If yes, emits wrap assignments in
  `broadcast_to` against the declared dims; if no, the expression
  language needs an explicit index-expansion operator and `E_4` needs
  rewriting.  This is the same "implicit index union" question that
  the einsum dialects paper over with Hadamard-expand rules — worth
  settling once, for all targets.  Blocks `derivative()`/`outputs()`
  (and therefore simulation) — t=0 already works because `fmc` is a
  solved unknown there.
- **Value cells are keyed by VARIABLE + element, not occurrence.**
  Correct by design (the element coordinate IS the per-occurrence
  addressing), but the Values card lists one row per occurrence all
  editing the same table — looks like three independent tables, and
  `save cells` (replace semantics) from one row rewrites the shared
  table for all.  Display should say "shared table" or merge the rows;
  port-bound vars shouldn't be listed at all (they resolve across
  arcs, never from cells — the `values > 0` sticky clause keeps them
  visible once any cells exist).  Fill keys also accept arbitrary
  strings → entries that match no coordinate are stored as dead keys
  (the `Node_1`/`Node_3` fill entries landed exactly where they were
  needed only by accident of the shared table).
- **Gather `-1` sentinel.**  `pos.get(element, -1)` emits a valid
  negative index when a contact's element isn't in its peer's field —
  the silent-alias source of the zero-flow bug.  Missing contact
  elements should surface as plan problems, not indices.

---

## 30. Per-mechanism incidence matrices — `F_k`, not `F_token` (2026-11-03)

Resolves the "open design decision" in
`session-handoff-2026-11-03.md` (`F_mass` vs `F_conv` in test_01).

### Decision

**Equations reference the mechanism index `F_k`**
(`F_conv`, `F_diff`, `F_heat`, …), never the token-group union
`F_mass`/`F_energy`.  The union exists — the machinery derives it —
but it has no equation-facing role: conservation is always written as
a **sum of per-mechanism terms**
(`dmdt = F_conv·fmc + F_diff·fmd`, §16's "token partition falls out").

### Why this is right

- **The F matrices *are* the mechanism distinction.**  `F_diff`
  selects the diffusion arcs, `F_conv` the convective ones — the
  user's words: "we need to distinguish between diffusional mass
  transfer and convective mass transfer; that should be the meaning
  of defining different F matrices."
- **Mechanism lives on the entity type, nowhere else.**  An arc
  lands in `A_conv` iff it touches a node whose type is-a
  `convection_transport` (selector + `promo:parent` closure,
  resolver).  The arc itself declares nothing beyond `token-flow`;
  the system has **no driving-force knowledge** — nothing knows that
  pressure-driven means convection or chemical-potential-driven
  means diffusion.  The user declares it twice: by placing the
  transport node's entity type, and by writing the constitutive law
  on that type.  Fick's law on `convection_transport` passes every
  check — mechanism semantics is a user-held convention, like §15
  orientation (any assignment valid; existence is all that matters).
- **`F_mass ≡ F_conv` is model-contingent.**  Verified on test_01:
  both arcs touch the convection node → member of `A_conv` **and**
  `A_mass` → identical matrices.  The day a diffusion transport is
  added, `F_mass` picks up its arcs automatically while `F_conv`
  stays unchanged — exactly why the balance must name `F_conv`, so
  the equation survives model growth without edits.
- **Edge case noted:** an arc directly between two transports of
  different mechanisms touches both types → member of `A_conv`,
  `A_diff` *and* `A_mass` (one column in each).  Consistent with the
  rule — whether such arcs should exist at all is a
  connection-rule matter (§28 rule-schema gap).

### Consequences for test_01 (Option A)

- `V_56`/`V_57` keep `[idx_arc_convection, idx_node]`.
- `E_4` uses `F_conv` → its `[N, A_conv]` result becomes a clean
  permute onto the lhs (the fragile positional bind via `F_mass`
  disappears).
- `E_29` → `F_conv . fmc` (elementwise — `*` sees two shared index
  IRIs and is ambiguous), **and** `F_conv` enters `E_29`'s incidence
  list so the lumped binds it.
- Edits go through the equation editor, not the `.trig` files.

---

## 31. Boundaries, not arcs — the unified port semantics (2026-11-03)

Resolves the `V_34` `port-coverage` problem on test_01 — and
**retracts both** the "re-index `V_34`" and the earlier
"`own ∪ contacted` extent" framings from this session.  This is the
baseline concept, not a patch: it was the original plan.

### The concept (user)

- **Everything is a system (node).**  Capacities and transports are
  the same kind of thing, differing only in temporal regime: a
  capacity integrates (dynamic); a transport is *event-dynamic* — a
  capacity whose relaxation is infinitely fast, or ignored →
  stateless, no interior, no state variable, no balance equation.
  `temporal_type` already carries the signal (§28); this is where
  it becomes load-bearing.
- **An "arc" is not a thing — it is the drawing of a boundary
  coupling between two systems.**  The arc index enumerates
  *boundaries/connections*, not arc objects.
- **Coupling = shared variable, not a copied value plus an
  equation.**  The boundary slot *is* the peer's variable — that is
  what eliminates the cut equations.

  - *Physical*: bidirectional contact — effort and flow **equal at
    the contact** (the continuity conditions).
  - *Information*: directed signal — the output **is** the
    connected input; identity, not even equality.

  Same principle in both domains, different continuity rule.

### The bound-extent rule

> A port-connected variable on an **event-dynamic** entity binds
> its **contacted (boundary) elements** — the peers' elements at
> each contact.  On a **capacity** it binds own elements as today.

The transport's domain degenerates to its boundary — a transport is
always distributed, and "distributed" means the quantity varies
over the entity's domain; for a stateless transport the domain *is*
the boundary.  Each boundary slot is filled by the port gather —
the peer's nodal value at that contact.

### What this resolves in test_01

- `V_34` (`p_mech`, `[N]`, nodal) — declaration unchanged; on the
  convection transport it binds `{N1, N3}` (the contacted env and
  lumped elements) = 2 slots = 2 contacts → `port-coverage` gone.
- **No `p_N2`** — the transport has no internal pressure unknown.
  That "cut equation" never appears; the drop across the transport
  *is* the difference between its two boundary values.
- **The drop** is the signed sum over the transport's contacts:
  `F[N2, :] = [+1, −1]` *is* the sign vector over its boundaries —
  `e * F` contracting `A` yields `p_env − p_lumped`, broadcast to
  `fmc[A_conv]`.  Existing operators; `E_4` gets a rewrite in the
  contact space (not `F_conv * p` over a shared node field — that
  form assumed `p` spanning the neighbourhood including `N2`).
- The §29 "same flow on both arcs" broadcast question dissolves —
  it was this same seam seen from the other side.

### Simplification for codegen (user's point, confirmed)

- No mixed-provenance splicing — every boundary slot is
  peer-delivered; the emit stays a pure gather-concat.
- No implied equations, no extra unknowns — the transport's law
  *is* its conservation.
- Bound extent is per-entity-type already (`instance@etype`); the
  change is *which elements* the port binding enumerates, not a new
  data model.

### The one open seam

A boundary slot is addressed by its **contact** — an arc element —
while `V_34` declares `[N]`.  Either the machinery lets a
node-declared port var bind contacted arc-addressed elements
(bound extent keyed by contact), or the boundary view is an
`[A]`-declared port var bound to the same peer `p_mech` via
token-comparability (already supported).  Decide when implementing.

### Machinery change

- `builder.py` — bound extent of a port-connected var on an
  event-dynamic entity = contacted peer elements (not own nodes);
  needs entity-type ancestry (`parents` is already collected in
  `_collect`, not passed to `build()`).
- `plan.py` — `port-coverage` counts supplied vs bound as today;
  with the corrected extent the counts match.
- Emit — unchanged (pure gather-concat).

### Implemented (2026-11-03) — verified on test_01

- **Bound extent**: `_collect` now threads `temporalType` into
  `build()`; port-connected vars on `event-dynamic` entities bind
  contacted peer elements (`contacted_elements`, contact order =
  incident-arc order).  `port-coverage` gone; emit is pure
  gather-concat — `V_59 = concat(env_p, lumped_p)`.
- **Seam resolved — option B**: the boundary view is a separate
  arc-indexed variable, not a node-declared var rebound.  `*`
  contracts by declared index IRI only (checker never sees bound
  elements), so the driving-force operand must carry the arc
  index: `V_59 p_conv [A_conv]` (effort axis, token_momentum —
  token-comparable to `p_mech`).  On the transport it resolves
  per-contact to `{N1, N3}` values; on capacities `p_mech` stays
  `[N]`.
- **`E_4`**: `(kConvX . Ayz) . (p_conv * F_conv)` — contracts
  `A_conv` → `+p_N1 − p_N3` (the drop) per transport node.
- **Broadcast emit** (`emit_common.render_rhs` + per-dialect
  `broadcast`): when the rhs index set is a strict subset of the
  lhs's and shared extents match, the rhs spreads over the lhs's
  extra axes — `[N] → [A_conv,N]` gives the same flow on both
  contacts.  Python: `broadcast_to(reshape)`.
- **`E_29`**: `reduceSum(F_conv . fmc, A_conv)` — the balance is
  the *net* rate per node, not per-contact.  The `V_57=0` cells on
  the transport then read correctly as "net accumulation = 0"
  (stateless) instead of forcing each contact flow to zero — which
  was the actual `gtol` contradiction (`fmc=0` vs `fmc=kA·4`).
- Result: `problems: []`, `POST /initial` `ok:true` at t=0.
- Remaining: matlab/julia `broadcast` stubs raise — implement when
  those dialects are exercised; `E_11` still references `p_mech`
  (unused by test_01).

## 32. Is the arc-typed boundary var an artifact? — OPEN (2026-11-04)

User objection to the §31 option-B landing: `p_conv [A_conv]` is a
machine-forced duplicate of `p_mech` — same physical field, re-indexed
to satisfy the contraction rule.  "For the user completely illogical."

Why it currently must exist (all three load-bearing):

- `*` contracts by declared index IRI only — `p_mech[N]` cannot
  contract `F_conv`'s `A_conv` axis.
- The port needs a declared landing var — the gather must bind into
  something arc-typed.
- `F` is per-entity (`F_conv_ct` covers only the transport's own
  node), so the global-style `Fᵀ·p` (per-arc endpoint difference, no
  boundary var at all) cannot form — the peer pressures live in other
  entities' instances; the gather brings them in, and gathers land on
  bound (arc) elements.

### Options weighed

- **A — keep the artifact, fix the label.**  A boundary var is a real
  modeling slot (where film/contact/membrane physics would attach);
  it only reads redundant in the pure shared-trace case.  Cost: a
  second var per effort-at-boundary; systematic naming
  (`p_mech@A_conv`) would make it legible.  Zero machinery change.
- **B — port = `p_mech`, arc view resolved by binding.**  The port
  endpoint is the shared var itself; on event-dynamic entities its
  bound domain *is* the contact set, so `ct!p_mech` is arc-typed by
  context.  Cost: index structure becomes context-dependent —
  `p_mech` means `[N]` on capacities, `[A_conv]` on transports; the
  checker must see bound elements (the wall §31 kept).
- **C — explicit trace op `contact(x, A_conv)`.**  Declares its
  result index like `reduceSum`'s index args; the wall survives;
  equations self-contained.  Cost: an operator whose semantics spans
  declared/bound — and (user's objection) it *restates* a contact
  fact the drawn arc already declares.

### User's current feeling (not a ruling)

The fact of contact is given by the arc drawn in the modeller —
topology already carries it.  Requiring a separate operator (or,
implicitly, a second var) double-declares what the arrow says.  This
weights against C and toward B.

### Sharpening of B under that objection

B need not be "context magic": the bound domain is *declared* — in
the model artefact, by the drawn arcs.  The wall isn't crossed into
mystery; the index check would run in binding context rather than
standalone at authoring.  Refined form:

- Port endpoint = `(var, optional mechanism qualifier)` —
  `p_mech @ A_conv`.  The qualifier is *not* a restatement of contact
  (topology supplies the arcs); it selects *which mechanism family*
  the shared var couples through — needed when a transport touches
  multiple mechanisms (p drives convection, not diffusion — same
  `token_momentum`, different efforts; token can't disambiguate).
  Single-mechanism transports default to "all contacts": zero extra
  authoring.
- Bound index typing is a *port-var rule only*: a var used as a port
  on an event-dynamic entity types by its contacted arc subset —
  narrow, not a general context-typing of all vars.
- Equations keep writing `p_mech`; `E_4` becomes
  `(kConvX . Ayz) . (p_mech * F_conv)` — p is p, the arrow is the
  contact, the qualifier lives in the assignment not the expression.

### Shared multi-mechanism boundaries (user's sharpening)

- Usually convection and diffusion couple through *different*
  boundaries — no problem.  The load-bearing case: **one arc in two
  mechanism sub-indices** (arc touches a multi-mechanism transport,
  or a convection and a diffusion transport on the same boundary).
- At such an arc element the boundary hosts two independent
  couplings: `p_mech` (convection effort) *and* `μ` (diffusion
  effort) on the effort side; `fmc_conv` and `fmc_diff` on the flow
  side.  The capacity's balance correctly nets both —
  `Σ F_conv·fmc_conv + Σ F_diff·fmc_diff` = convective + diffusive
  influx at the same boundary.
- So the coupling engine must know **which var couples through which
  mechanism**.  That pairing is physics, not topology — the arc says
  *where* contact is, not *what* acts across it.  Candidate homes:
  - port-endpoint qualifier (B'); per-instance, repeats science in
    every assignment;
  - **mechanism→effort-kind rule in the vocabulary** — convection
    declares "driven by momentum effort", diffusion by "chemical
    potential" — pairing then automatic by quantity-kind, lives where
    physics lives (preferred);
  - the artifact var (A) smuggles it into the index declaration.
- Degenerate edge: transport↔transport arc with *mixed* mechanisms —
  both sub-indices, both endpoints stateless, no capacity to read
  peer values from.  Parked (§15 deferred case).
- Takeaway: the qualifier's job is var↔mechanism *pairing*, not arc
  selection.  Single-mechanism entities default cleanly; shared
  boundaries need the pairing, best sourced from vocabulary.

### Mechanism as vocabulary object (user direction, pending design)

User lean: declare mechanism rules in the vocabulary — the pairing
is science.  What a mechanism must declare reduces to the **coupling
signature**: what drives it + what it carries.  The law stays
user-authored.

- `promo:Mechanism` resource — first-class vocabulary, like seeded
  `F_<mech>`/arc types.  Entity types link `promo:hasMechanism`;
  sub-index membership already resolves via entity type.
- Two slots (not one): **`drives`** = effort quantity-kind
  (§24: effort axis + token); **`carries`** = flowing token.
- Key subtlety: **effort token ≠ carried token** — convection is
  driven by a *momentum* effort but carries *mass*.  Pairing can't
  be token-only matching.

  ```
  convection   drives: effort(momentum)     carries: mass
  diffusion    drives: effort(chem-pot)     carries: mass (per-species)
  conduction   drives: effort(temperature)  carries: energy
  radiation    drives: effort(temperature)  carries: energy
  ```

  Radiation/conduction share a signature — mechanisms answer *which
  vars couple*, not *how they relate* (the law is the user's).
- Open semantic questions: advected energy (one mechanism or
  bulk-convection + derived T·fmc coupling?); species-indexed
  diffusion efforts (`μ_s` carries S axis from scheme); transfer
  class attribute (boundary-transfer vs source — work_source differs).

### Coupled transport + entropy (user's continuation)

Three distinct phenomena, different landings:

- **Advected energy** — stays capacity-owned: the shared `fmc` IS
  the energy carrier; the capacity's energy balance applies the
  upstream enthalpy (`fmc·h_up`).  One coupling, energy derived
  downstream.  Open modelling point: *which* upstream (upwind rule).
- **Coupled transport** (Soret/Dufour/thermo-osmosis) — the law
  itself mixes domains → `drives` becomes a SET: the transport needs
  one effort view per kind at the same contact (`μ` AND `T`).
  `carries` also a set when one coupled law produces both mass and
  energy fluxes.  Onsager matrix stays user-authored; mechanism
  declares only the coupling interface.
- **Entropy** — production needs declared conjugate pairs:
  `σ = Σ J_k·X_k`.  A `conjugates` slot pairing drives↔carries is
  the signature's thermodynamic spine; enables a future entropy
  token (advected `s·fmc` + conductive `q/T` boundary fluxes +
  production inside transport AND capacity).

Refined signature sketch:

```
convection      drives:{momentum}     carries:{mass}
                conjugates:{(p, fmc)}
conduction      drives:{temperature}  carries:{energy}
                conjugates:{(T, q)}
soret-diffusion drives:{chem-pot, T}  carries:{mass}
                conjugates:{(μ, j)}
coupled m+e     drives:{chem-pot, T}  carries:{mass, energy}
                conjugates:{(μ, fm), (T, fe)}
```

### Film resistance & co. — user's ruling: explicit nodes, agreed

- A film/contact layer has its own physics → it is a *system*, drawn
  as a node (`capacity—arc—film—arc—capacity`), not hidden in a
  boundary var.  Implicit-in-var treatment would make the boundary a
  thing again — precisely what §31 removed.
- A film *is* a stateless transport (n contacts, own resistance law)
  — existing machinery handles it; e.g. a conduction film is just
  `drives:{temperature}, carries:{energy}` on a node.
- Consequence: **A's escape hatch evaporates** — arc-typed port vars
  are an internal instantiation form (bound elements), never
  user-authored.  B' is unqualified.

### Semipermeable walls (use case, validated)

- User case: a transport entity that *inhibits* species transfer —
  black/white selectivity.  No objection: a membrane IS a stateless
  transport; selectivity lives in its type/law, never in the arc.
- Two levels:
  - **Law-level (today)**: permeability `k_s [S]`, zero rows for
    retained species — fluxes evaluate zero, extent stays full-S.
  - **Signature-level (honest form)**: `carries` gets species scope
    (`carries:{mass(water, urea)}`) — retained species never enter
    the transport's species extent; impossible states unrepresentable.
    Membrane classes (MF/UF/RO) are literally named by retention →
    evidence for species-granular `carries`.
- Modeller: nothing needed — arcs are species-agnostic carriers;
  selectivity is entity-type content.  Membrane glyph = graphicals.
- Dependency: per-entity species admission in the scheme's
  distribution fixpoint — check when species content is authored.
- Also a natural multi-mechanism shared boundary: selective mass
  transport + heat conduction at the same contacts.

### Ruled & implemented (stage 1, 2026-11-04)

- **B' unqualified**: the shared var itself is the port — bound-typed
  by the contacted arcs in the binding context.  The arc-typed
  duplicate (p_conv/V_59) is gone from the vocabulary.
- Index-checking runs in *binding context*: the same var may check to
  different shapes under different assignments (p_mech `[N]` on a
  capacity, `[A_conv]` on the transport).  The bound elements *are*
  declared — in the model artefact — so the wall is moved to
  instantiation, where binding is authoritative anyway.
- Mechanics: `builder.contact_arc_domain` — a node-declared port var
  on an event-dynamic entity binds its incident token-flow arcs under
  the covering mechanism sub-index nearest the entity's own type
  (`A_conv` for convection, never the `A_mass` union).  No covering
  sub-index → `port-domain-unresolved`; several covering at equal
  selector distance → `port-domain-ambiguous` (the var↔mechanism
  pairing gap — stage 2 vocabulary).  `PlanBlock.var_bound` carries
  the bound index IRIs to the emit-time check, which re-checks the
  RHS in a scoped CompileSpace.
- Verified on test_01: `p_mech * F_conv` contracts over `A_conv`,
  gathers concatenate peer values in contact order, all three
  dialects emit; E_4/E_11 repointed, V_59 deleted.

### Ruled & implemented (stage 2 — vocabulary slice, 2026-11-11)

The `drives`/`carries` coupling signature landed in minimal form;
the pairing resolver stays deferred until the first multi-mechanism
model trips `port-domain-ambiguous` (the existing tripwire — no
silent wrong answer in the meantime).

- **`drives` declared** — `promo:drives` on mechanism leaf entity
  types: the token the driving *effort* carries (convection →
  `token_momentum`, diffusion → `token_component_mass`,
  heat/radiation → `token_energy`, work → `token_momentum` —
  user-confirmed 2026-11-11).  Set-valued for coupled
  transports; floor-seeded and migrates on `load()` (additive —
  user-declared extra drives preserved, seeded value resurrects).
  Match rule: a peer var couples as the effort iff it is
  `function:effort`-classified and carries the drive token.
- **`work_transport` = catch-all** — the bin for every energy
  transfer that is not mass-, heat- or radiation-coupled.  Its
  seeded drive is mechanical (force/stress → momentum token);
  surface/interfacial, elastic and gravitational work all resolve
  to momentum effort or body-force sources.  Electrical and
  magnetic work are normally folded into the (electro)chemical
  potential — the effort stays `component_mass`-tokened and couples
  on the *mass-transport* side, not through work at all.  The
  alternative view (an explicit electrical-work term) would need a
  `token_charge` vocabulary extension — `drives` being set-valued
  already leaves the slot open (`{momentum, charge}` on a subtype).
- **`carries` is free** — it is exactly the inherited `promo:token`
  on the grouping types.  Effort token ≠ carried token is now
  first-class: convection is momentum-driven but moves mass.
- **`mechanism_drives`** (`capabilities.py`) — *union* walk up
  `promo:parent`, unlike `mechanism_token`'s nearest-wins: a
  subtype may add a coupled drive beside the inherited one.
- **Write path** — `EntityTypeRecord.drives` + token-typed
  validation, so user-authored mechanism types declare their own
  signatures; `VOCAB_DOCS` self-doc on `promo:drives`;
  `SEED_FLOOR` → 2026-11-11.
- **§30 amendment (narrow)** — "no driving-force knowledge" narrows:
  the system now declares the *coupling interface* (which effort
  kind drives each mechanism) but still not the law — the signature
  answers *which vars couple*, never *how they relate*.
  Fick-on-convection remains legal; laws stay user semantics.
- **Still open**: pairing resolver (var→mechanism on ambiguous
  boundaries — effort vars match `drives`; flow vars may pin via
  the `F_k` their defining equation already names),
  effort-availability advisory at contacts (warn, not gate),
  `conjugates` (entropy — no consumer yet), `promo:Mechanism`
  resource layer (needed only when one etype hosts two mechanisms
  and drives↔carries must pair per-mechanism).

### Follow-up (2026-11-25): pairing derives, unions removed — RULED

The `fnc`/`fnd` `ambiguous-port` on the convection peer fired the
tripwire.  Reading the demand legs showed the pairing signal is
already authored — twice over: the flow var's `indexStructure`
carries its mechanism arc sub-index (`fnc`→`A_conv`, `fnd`→`A_diff`)
and the consuming balance names the same sub-index in its `F_k`
contraction (`E_anc`/`E_and`).  Token cannot discriminate — both
carry `component_mass`, correctly.  Ruled: **pairing derives, it is
never declared** — candidate's arc sub-index ↔ demand's contraction
index; an explicit pairing predicate would double-declare what the
index structure already says.

- **Union indices removed** (`A_mass`, `A_energy`, `F_mass`,
  `F_energy` — seed entries + stored resources).  Zero consumers:
  `E_29` contracts `A_conv` only, builder routed around the union,
  and a union-typed flow var is unpairable by definition.  User's
  remark: stay on basic physical tokens — for mass that is the
  species (`component_mass`), which a bulk-mass union didn't even
  group.  Mechanism-level sub-indices only, from here on.
- **Resolver split** (to implement): effort-role ports pair via
  `drives`; arc-typed flow ports pair via `indexStructure` sub-index
  ↔ demand contraction index; neither signal → stays ambiguous,
  loud.

## 33. Submodel reuse — two insertion modes and the phantom port (2026-11-08)

Continuation of the 11-06 copy-vs-reference discussion.  The user's
clarification — *reuse requires open connections* — dissolved the
either/or: the two modes serve different intents and **coexist**.

### Two insertion modes — ruled

- **Copy insert** — paste-and-integrate.  Stamped content becomes
  ordinary host content: flat graph, no occurrence semantics, no
  read-only island, re-resolved under host pins.  Mechanically it is
  *insert + dissolve*; `dissolvedFrom` is the provenance record and
  dies if the composite is later ungrouped — the honest semantics of
  "stop tracking this".  Copied open arcs persist as ordinary host
  open arcs — never auto-deleted; they may even become the *host's*
  own interface if it is later saved as a part.  The interface
  survives as wiring documentation, not a gate: **every leaf is a
  legal connection surface** — the copy's interface is emergent.
- **Referenced insert** — sealed contract use.  The declared ports
  are the *only* legal connection surface (strictness below).

Division of labour: **copy = private, editable reuse; reference =
curated, versioned, untouchable reuse** — maps onto principle 12's
in-doc vs own-graph tiers.  The Friday proposal's refresh machinery
(`copiedFrom` + refresh gesture) is demoted: `dissolvedFrom` already
provides the provenance anchor; refuse-to-clobber/merge stays
deferred until a real update workflow demands it.

### The interface — ports as complete contracts

A submodel's interface is its open arcs, each a **complete
contract**: what flows (token or information), which way (§15
reference direction for physical; in/out inherent for signals), arc
kind, and what peer it expects.  Token is never stored on the
terminal (arcs declare none — principle 3); it derives from the
inside entity's type.  `externalEntityType` demoted from gate to
auto-filled hint of intent; admissibility is the ontology rules run
between the two real entity types at connect time.

A reusable submodel is **complete**: it carries its own context —
tokens/species scheme, pins, possibly value defaults — so it means
something on its own, before any host places it.

### Phantom ports — how interfaces are authored

Two origins of a port:

- **Severed** — extraction cuts a live arc; the contract is
  inherited from the cut arc and the dropped peer's type.  Primary
  path, exists today.
- **Authored** — declared on purpose for standalone or imported
  models, and for the cuts extraction forgot.

*Ruled:* authored ports are declared via a **phantom peer**.  Pick
the inside leaf, name the imagined partner ("a capacity sits here");
the connection rules derive the contract — arc kind, token,
physical-vs-informational.  Nothing is hand-written, so nothing goes
stale.  The one underivable bit is the direction convention: a
default plus a flip gesture.

**The phantom does double duty**: it is also the default boundary
condition — "expects a capacity" instantiates a minimal capacity to
close the circuit when the part is tested alone.

### Strict boundary — ruled

Only declared ports are connectable on a referenced occurrence —
**including observational arcs**: reading an internal variable is
crossing the boundary like any other wire, so observable parts
declare signal ports.  Consequences, accepted:

- A missing port is a hard stop: the fix is an artefact edit (open
  the submodel → phantom-declare → host picks it up).  Someone
  else's artefact = fork + re-point, or ask the author.
- Undeclared leaves of a referenced composite are not connect
  targets; `resolve-connection` enforces.
- **Escape hatch: dissolve.**  It converts the occurrence to a copy;
  every internal becomes reachable at the price of severed
  provenance.  Strict is only livable because port-declaration is
  cheap and escape exists — remove either and it is intolerable.

### Standalone instantiation — ruled (provisional, evaluate on use)

A complete, interfaced submodel instantiates **standalone**: its
ports are exposed as boundary conditions, the phantom peers as the
default closures.  Parts are testable before placement.

*Status 2026-11-09:* the procedure is new — v1 picks the minimal
honest semantics and keeps track for evaluation:

- **Overlay, not content** — phantom peers materialize only in an
  instantiation-scoped view; the artefact itself never gains
  phantom entities or arcs.
- **Phantoms as boundary-condition providers** — the imagined
  peer's port variables become fill-in inputs on the instantiation,
  not a computing entity with its own equations.
- **Undeclared terminals** — open arcs without a named peer report
  as unclosed boundary, not errors.

*Evaluate on use:* whether input-provision suffices or the phantom
must compute; the DOF story at open boundaries; whether authored
terminals need declared default values beyond the peer's port
vars.

### What this settles from 11-06

- **Q1 (per-occurrence pin variation)** — lives in the referenced
  path; the override map remains its mechanism.  Copies don't need
  it — adaptation is just editing.
- **Q2 (automatic propagation)** — the referenced path keeps
  pin-gated propagation.  Copies don't propagate; that was the
  point.
- **Q3 (black-box boundary)** — answered: the referenced insert
  *is* the black-box case.  `refersTo` stays — not as the sole reuse
  story, but as the contract-bound tier.
- §22 stands reframed: *refer* is one of two modes.  The machinery
  (occurrence expansion, sub-plans, override coverage) stays live
  for exactly this tier.

### Depth — dissolve and ungroup are single-level (ruled)

Both operations remove only the **top** layer:

- **Dissolve** severs exactly one `refersTo` — the occurrence's own.
  Inner referenced composites inside the pasted content copy through
  with their `refersTo`/`overrides`/`dissolvedFrom` intact: they
  stay live references under the host (already the implemented
  behaviour — `service.py` dissolve copies them verbatim).
- **Ungroup** splices one composite's children into the parent's
  child list — inner composites stay composites (structurally
  single-level by construction).  It applies only to in-doc
  composites; referenced composites go through dissolve (the
  gesture is already gated so).

A paste-dissolve-ungroup sequence therefore yields a **mixed**
host: integrated top level + still-live inner references — which is
the desired semantics: links die only by explicit act, one per
occurrence.  Flattening deeper is always a repeated deliberate
gesture, never a cascade.

### Open

- **Port multiplicity** — a terminal gathering several host peers
  (cf. the shared boundary var, §29/§32) needs declared cardinality.
  Dual case, ruled: one leaf anchors *several* terminals of
  different kinds — a valve/pump = two token-flow ports (capacity
  peers) + one signal port (controller peer), each its own phantom.
  The phantom set can be suggested by the entity type's
  capabilities (actuation implies a signal port); `exposeTerminal`'s
  one-terminal-per-leaf cap must relax to per-(leaf, contract)
  — done 2026-11-09 (dedup key = leaf+phantom+kind+direction).
  Gathering-terminal cardinality stays open.
- **Enforcement surface** — verified structural (2026-11-09): a
  referenced composite's internals are never host-view connect
  targets — `computeGraphView` builds the host view from host maps
  only, and the ref's interior lives in a separate read-only view
  (`viewRefIri`) where `inRef` gates every mutating gesture.
  Terminals are the only exposed surface, and `reconnectOpenArc`
  requires the host end in `modelNodes`.  What remains is polish:
  terminal stubs should be the *only* visible connection
  affordance on a referenced box.
- **Phantom closures** — instantiating the imagined peer as a
  minimal default entity is new machinery at instantiation time.
- **Copies of interfaces** — answered in implementation
  (2026-11-09): stamped copies keep their open arcs *with* hints
  (`externalEntityType`/`phantomEntityType` ride the remap
  verbatim); the interface lands as wiring documentation.
- **One flatten gesture** — dissolve and ungroup *feel* the same to
  the user while differing underneath: present a single
  flatten-this-level action that dispatches by composite kind, with
  a confirm affordance only on the dissolve path (one-way, severs
  the link); ungroup stays instant and redoable.

## 34. Two senses of "port" — variable interface vs assignment endpoint (2026-11-09)

Surfaced while authoring the first control block (`y := p∘e`): the
user pushed back on a suggestion to flag `y` as port — "y is a
function of existing variables, so it is not a port variable".
That exposed a terminology collision the implementation had been
carrying silently.

### The two senses — clarified

- **Variable-level `promo:portVariable`** — connectable-interface
  marker: "this variable may be supplied to a peer across a contact
  arc".  The functional-block I/O sense: `u`, `y` of
  `ẋ = f(x,u); y = g(x,u)`.  Preference, not gate (§14 R3): the flag
  exports an otherwise-hidden state and disambiguates among
  comparable supply candidates; unflagged defined vars still bind.
  Port vars may own defining equations (`fmc` = `E_4`): port-ness is
  boundary reach, not determined-ness.
- **Assignment-level `promo:hasPortVariable`** — demand endpoint:
  where the lower-triangular var/expr search terminates ("one needs
  to start somewhere").  The graph-root sense (§21).

They compose: `y` is `out` on the controller's assignment (produced
root) and `port` on the plant's (demand); the variable flag licenses
it as a connectable surface.  "Is `y` a port?" — yes on the variable
record, no on the controller's assignment.

### The terminal question — resolved in discussion

User's question: a variable class "defined like ports, but
connectable later — requestable to be instantiated, like a setpoint
(either instantiated or driven by another control block)".

No new class — the three layers already decompose it:

- `portVariable` = *connectable* capability (variable declaration).
- Endpoint mark = *per-occurrence resolution* (assignment: `port`
  when wired, `instantiated` when pinned).
- §33 phantom closure = the unconnected case: an unwired terminal
  instantiates via the imagined peer's boundary condition.

Cascade control is the composed case: outer `out y` → inner
`port s`.  "Terminal that can be requested to be instantiated" IS
`portVariable` + endpoint-per-occurrence.

### What it actually exposed

- **Unconnected-resolution policy** — physical contact ports resolve
  open to an *environment boundary*; info terminals (setpoint,
  manual input) resolve to a *value pin*.  Both via phantom closure,
  different phantom types.  Where the *default* lives — variable
  hint vs occurrence fix marking — is open.
- **Optional terminals** — the endpoint taxonomy has no "may be
  wired": `port` implies *will be* wired.  If
  instantiate-if-unwired should be a declared property rather than
  emergent, it is a small attribute question on the endpoint mark —
  not a new variable class.  Adjacent to §33's port-multiplicity
  open item.
- **Defects found same day** — stale doc wording fixed
  (`ontology-data-model.md` now records both senses); the two
  creation dialogs merged into one variable editor (done same day):
  "Port (connectable)" is a checkbox, the port editor's manual
  units/indices pickers appear when no RHS is given (declared
  variables), and a single "New variable…" button opens it —
  `PortVariableEditor.tsx` deleted.  §18 still locks the flag while
  *referenced* — exempting it (same argument as the token-ADD
  exemption) is a policy question left open.  Possible predicate
  rename (`promo:connectable`) parked: cheap via migration, only if
  the fuzz keeps biting.

### Two connection semantics under one flag (user, same day)

- **Signal arcs — inherently directed terminals.**  In/out is baked
  into the arc kind (§15); the endpoint roles are already typed at
  the assignment level (`port` = demand, `out` = produced).  Every
  signal endpoint of a block is therefore a *potential* terminal —
  in flat models the emergent surface is the full I/O set.  The
  flag's remaining job: declare the curated interface (referenced
  tier), license state export to a sensor, disambiguate comparable
  supply candidates.
- **Physical token-flow arcs — shared coupling points.**  `p_mech`
  is not pushed down a directed wire; it is *one* variable bound at
  several contacts (bound-index by incident arcs, §32) — effort
  continuity + flow balance, the bond-graph port.  The flag marks
  the shared var as exportable across its contacts.

The naming fuzz is partly this: "port" means *terminal* (signal,
unidirectional) and *coupling point* (physical, shared).  The flag
uniformly declares "may be supplied/connected", but what supply
means differs by arc kind.

### First control block — review of the authored variables (same day)

Walking the stored P-controller (`e := s − o`, `y := p ∘ e`):

- **`u` (V_63) is dead weight** — `port` + `info_role input`, but no
  equation references it.  Leftover from the `ẋ=f(x,u)` template; the
  algebraic block's actual inputs are `obs` and `s`.  Delete or wait
  for dynamics.
- **`obs` (V_66)** — correctly declared all along (`port` +
  `Observation` + extensive/flow); only its doc string lied
  ("token-free observation" — fixed via API).  The §18 lock rightly
  refused a redundant `Signal` add on top of `Observation`:
  `Observation` already descends from `Signal`.  First live
  demonstration that the lock steers authors away from bookkeeping
  without semantics.
- **`pGain` (V_59)** — `carriesToken signal` + `extensive/flow`
  contradicts §4 neutrality for coefficients; `portVariable` is
  legitimate (tunable terminal).
- **No control assignment yet** — `s`, `obs` (demand `port`s),
  `pGain` (`instantiated`), `y` (`out`) exist only at variable level;
  endpoint roles still unrecorded.
- **Token picker now shows the ancestry** — the `carriesToken` list
  in `TokenSection` renders `promo:parent` as an indented tree
  (`Observation`/`Manipulation` under `Signal`) so the comparability
  rule is visible at the point of choice ("the user cannot know").

### Documentation gap (user)

"This type of question will be posed by the user — it is not
trivial to see how one defines the various variables and functional
blocks."  The control-block authoring recipe — which flag, which
endpoint, which network, which tokens for `u`/`x`/`y`/`s` — needs a
user-facing worked example.  Open.

## 35. Token layer usability — declaration surface vs algebra — OPEN (2026-11-11)

Raised by the user after the `V_23` (volume) incident: "the whole
token association causes a lot of problems and is very hard for a
user to catch what has to be done and what not — once there is no AI
to check this will become infeasible."  Logged as an open design
question — analysis only, no ruling yet.

### The incident that exposed it

- `V_23` (volume) is flagged `portVariable` ⇒ the 2026-11-10 guard
  requires `carriesToken` ⇒ declared `{mass:1}`.
- `rho := m/V` then derives `{}` — `sig(m) − sig(V)` cancels — and
  the check warns "basis change, not a relation".
- The user tried to remove V's mass token ⇒ blocked twice: the
  guard (port needs a token) and §18 (V is referenced by 15
  equations — tokens and port status both locked).
- The warning is *correct* — the algebra honestly reports that the
  equation carries no net token — but it cannot point at the cause,
  and the causing declaration is unfixable through the UI.

### What the layers actually buy

- `promo:carriesToken` — membership set.  Real consumers: port
  licensing (`satisfy.py`), §32 drives matching, the write guard.
- `promo:tokenVector` — exponent map.  Consumer: only the checker's
  advisory algebra; nothing gates on it.  The consistency rule
  (every member ⇒ nonzero exponent) welds membership to signature:
  a licensing declaration becomes algebraically active.
- §18: token ADDs exempt, ALTERs locked once referenced — the
  declaration is optional until a port forces it, then sticky when
  wrong.

### The traps a user meets

- Two declarations that look like one concept, bound by an
  invisible consistency rule.
- Three leaf states render identically: untracked (absorbs),
  tracked-empty (`{}` → `"1"`), neutral-by-kind (bound value /
  constant / parameter).
- Cross-dialog blast radius: declare on `V`, the warning surfaces
  inside `rho`'s check.
- Advisories point at the equation, never at the declaration that
  caused it.

### Reframing — the algebra is not the bug

The exponent algebra produces the right answers: `x_i = n_i/n`
*should* be token-neutral (a mole fraction is a basis change);
`rho = m/V` *should* derive `{mass}` — and does, once `V` is
neutral.  The noise comes from a licensing declaration (port ⇒
forced mass membership) having algebraic consequences it was never
meant to have.

### Options on the table

- **Neutral-port membership** — smallest change.  Ports may declare
  "no network" (empty `carriesToken` for non-bearing kinds, or a
  neutral token with exponent-0 semantics).  `V` stays a port, goes
  neutral, `m/V` derives `{mass}`, warnings go quiet.  Needs
  licensing semantics for neutral ports — §34's split suggests the
  requirement may be over-broad along exactly that seam: membership
  is meaningful for token-flow *coupling points*, not for signal or
  geometry *terminals*.
- **`tokenVector` derived-only** — users author only `carriesToken`;
  the leaf signature derives from membership + kind convention
  (extensive `+1`, intensive `−1`) and persists as a cache.
  Removes the second declaration, the consistency rule, and the
  declared-vs-derived mismatch advisory.  Composite signatures
  (`{energy:1, time:-1}`) lose their authored form — acceptable
  only if no consumer needs them declared.
- **Set-algebra collapse** — *analysed and rejected*: `a/b` as
  union gives mole fractions a mass membership; as symmetric
  difference gives `rho` no membership.  Exponents carry the
  cancellation information that separates density from ratio.
  Recorded to preempt the obvious simplification.
- **Narrow the declaration surface** — if only ports need
  membership, token declaration becomes a port-authoring step and
  non-ports never see the picker.
- **UX-only mitigation** — live signature preview in
  `TokenSection`; advisories that name the responsible declaration.
  Does not remove the structural complexity; combines with any of
  the above.

### Open

Which direction — and how much of the §24 apparatus survives.  The
synthesis that currently looks strongest: membership authored only
where it means something (ports), the signature always derived, and
neutral ports legal.  Ties into the §34 two-senses finding and the
parked `portVariable`-flip exemption; also part of the recurring
"the user cannot know" theme (§34 doc gap) — this is its
structural version.

### Suggested-fix mechanics (user direction, same day)

The user's pushback: advisories must ship with remediation, not just
diagnosis — "the user cannot fix it in a simple way by declaring V
as tokenless".  Two consequences:

- **Advisories become structured** — `{code, cause, fixes[]}` instead
  of bare strings; the UI renders each warning with fix buttons that
  either apply a concrete edit (via the normal save endpoints) or
  open the responsible declaration.  The `cause` names the operand
  whose signature produced the result (here: `V_23 {mass:1}`
  cancelling `m {mass:1}`), not just the equation.
- **The natural fix must be legal.**  For `V_23` the desired fix —
  "tokenless signature" — is blocked twice today, and both blockers
  turn out to be adjustable without weakening the model:

  1. *Consistency rule* (member ⇒ nonzero exponent): relax to
     **membership-without-signature** — `carriesToken {mass}` +
     `tokenVector {}` = "belongs to the mass network, contributes
     no signature".  Licensing keeps its membership, the algebra
     sees neutral.  `V` stays a mass port AND `m/V` derives
     `{mass:1}`.  This cleanly separates the two predicates into
     what they were always meant to be — licensing vs algebra —
     and makes "declare V tokenless" literally available.
  2. *§18 token-ALTER lock* on referenced vars: `tokenVector` feeds
     only advisories — nothing gates on it — so a signature-only
     change is exemptable by the same argument as the token-ADD
     exemption.  `carriesToken` changes stay locked (licensing is
     a real consumer).  Alternatively a confirm-and-apply path
     showing the referencing equations as impact.

  Both are rulings; the mechanics (structured advisory → fix
  button → confirm → normal save path) then work for every
  warning class, not just this one.

### Ruled & implemented (2026-11-11, same session)

The user ruled for fix mechanics over mechanism redesign: advisories
ship with remediation, and the natural fix is made legal.

- **Membership-without-signature** — `carriesToken {X}` +
  `tokenVector {}` is legal: licensed for the network,
  algebraically neutral.  The containment rule was *deleted*, not
  weakened — the persisted data proved both directions free:
  members need not sign (the geometry-port fix), and composite
  signatures legitimately exceed membership (ten vars sign
  `{mass,time}`/`{energy,momentum}`-style decompositions on a
  single membership).
- **§18 exemption for signature-only changes** — `token_vector`
  feeds only advisory signatures; nothing gates on it.  Dropped
  from the lock set; `carriesToken` stays locked.  This is what
  makes the fix usable on referenced variables — the exact V_23
  case (15 references, port flag locked and untouched).
- **Structured advisories** — `/check` returns `advisories` as
  `{code, message, cause, fixes[]}`.  `token_basis_change` names
  the contributing operand signatures and offers `clear_signature`
  per operand; `token_signature_mismatch` offers `adopt_derived`
  on the LHS var.  `warnings` keeps the same items as strings.
- **UI fix flow** — the check panel renders advisories with the
  operand signatures and fix buttons; clicking a fix shows the
  impact (the §18 reference list — N equations whose derived
  signature changes) then applies via the normal variable save.
  Both `draftVariable` paths emit `{}` when membership is kept
  with an emptied signature (previously `undefined` → re-defaulted
  `{member:1}` — the manual neutral path was inexpressible).
- Tests: signature-only exemption, port + empty signature legal,
  composite-exceeds-membership legal, advisory structure, and the
  persisted-data consistency rule updated to the decoupled form.
  540 backend tests pass.

Still open from §35: the wider surface question (derived-only
`tokenVector`, ports-only declaration) — the fix mechanics landed;
whether the declaration surface shrinks further stays on the table.

### Session completion amendments (2026-11-11)

- Token algebra canonicalises full IRIs, prefixed token fragments and bare
  fragments to the same fragment identity. This removes ghost basis terms
  when mixed persisted key forms should cancel; regression tests cover it.
- The variable creation surface is one foundation/dependent dialog.
  Foundation declares a signature without an RHS; dependent derives it
  from Check. Connectability is independent of the creation mode.
- The fixed units/index signature rule locks on foreign RHS/incidence
  references only. Owning defining equations alone do not make a variable
  used: rewriting its definition is the legal redefinition path. The UI
  lists own definitions separately from foreign uses and blocks Accept
  when a used variable would receive a mismatched signature.
- Final verification: 543 backend tests pass; equation-editor frontend
  tests and TypeScript/Vite production build pass. Serialized data changes
  from the authoring session are included without manual TriG edits.


## 36. Global equation consistency check and feasible fixes (2026-11-11)

### Ruling

The user clarified that consistency during construction is maintained by
rules on equation definition and deletion; lower-triangular construction
is the main structural concern. Token assignment cannot be made equally
sharp. The distinction between membership and signature is already
settled, not reopened: an explicit global consistency check is needed.

Placement: the equation editor, with authoritative backend checking over
one resolved context snapshot (selected artefact plus pins). The user
approved feasible fixes as part of the report. Control semantics is left
for a separate discussion; this feature invents no physics or control laws.

### Implementation

- `GET /api/equation/consistency` checks all attached equations in scope
  using the existing parser, checker and token advisories. It compares
  derived units/index sets to the LHS declaration, including explicit-empty
  token signatures. Errors, advisories, untracked and consistent results
  are separate; expressions with warnings are never counted as consistent.
- Each result names the equation, owner graph(s), expression, declared and
  derived signatures, operand declarations and incompatible sum terms.
  The editor links to variable/equation editors and owning artefacts.
- Feasible `adopt_derived` and `clear_signature` corrections require an
  impact preview (in-scope transitive consumers and cross-artefact direct
  references) and explicit confirmation. Alternative definitions that do
  not agree block a suggested correction rather than silently swapping the
  inconsistency between equations.
- `POST /api/equation/consistency/fix?graph=...` recomputes the report,
  rejects stale revisions or unoffered actions and writes only the offered
  tokenVector. Membership is not invented or altered; units, indices and
  equations are untouched. Frozen variables/equations/versions and foreign
  owning graphs block corrections. Pinned declarations must be edited in
  their owning artefact, never shadow-copied into the selected graph.
- A correction reruns the whole report and refreshes editor context. Local
  context edits mark an existing report out of date. Checks are read-only;
  corrections use ordinary dirty tracking and still require Save for disk
  persistence. There is no blind bulk-adoption operation.

### Limits

This audits declarations and propagation; it does not certify physical
meaning, solver solvability, model-bound port typing or lower-triangular
assignment closure. Structural issues open the authoring editor rather
than rewriting user equations or bypassing referenced-variable locks.
Untracked operations/declarations are visible without guessing signatures.

## 37. Signals and the physical–information interfaces (2026-11-12)

### Ruling

The user clarified that control, or information processing, operates solely
on unidirectional signals. Observation and manipulation are earmarked
signals, primarily used for interaction with the physical system.

Observation reads a physical quantity and makes it available as a signal,
through an instrument in real-world systems. The user explicitly corrected
any restriction to states and secondary states: **a flow can also be
observed**. Reading a flow does not transport the extensive quantity itself.

Manipulation acts through a transducer to the “valves” controlling the flow
of extensive quantities between capacities. The user made the target
explicit: **manipulations act on transport systems**.

Thus observation/manipulation describe the reading/acting interfaces to
physics, not simply all controller inputs/outputs. Connections within
information processing carry signals. Their unidirectionality does not
prevent composition into a feedback loop.

### Documentation and implementation boundary

Recorded as design-principles §16 and reflected in the conceptual
architecture. This is a semantic ruling, not an automatic rewrite of the
ontology, token signatures or user equations. The representation of these
earmarks and alignment of existing declarations remain implementation work.

## 38. Simplify token authoring; preserve signature algebra before removal (2026-11-12)

### Decision and rationale

The user found manual token association/exponent maintenance too difficult
for reliable equation authoring, to the point of threatening usability of
the project. Repairing individual declarations does not address that burden.
The user approved the direction of separating semantic connectivity from
algebra and preserving the existing implementation before changing it.

Control uses normalised, dimensionless signals. Generic controllers define
signal inputs and outputs, not observation/manipulation variables. Those
physical-interface roles are derived at model connection time; manipulation
acts on transport systems. General information processing remains open.
Dimensionless control signals do not imply dimensionless time parameters.

The agreed simplification direction is to retain tokens for semantic
connection membership/licensing, remove manual token-exponent authoring,
signature-driven forced membership and membership-to-signature defaulting,
and remove the associated token-signature authoring advisories from the
required contract. Units, index checks and connection licensing remain.
Do not merely hide exponent controls while retaining unexplained warnings.
Existing declarations require an explicit, impact-reviewed API migration;
no equations or serialized TriG are to be hand-rewritten.

### Preservation checkpoint

Before simplification, save the live store through POST /api/ontology/save,
commit the current code, documentation and serialized artefacts, and create
the annotated tag `archive/token-signature-algebra`. Push the checkpoint
and tag to origin. The tagged data preserves the user-authored state at
this boundary, including existing diagnostic inconsistencies; it is not a
claim of semantic integrity or repair of split graph ownership.

The checkpoint retains token-vector propagation, signature authoring,
actionable advisories, confirmed global-audit corrections and their tests.
Revival should require a demonstrated checking benefit that cannot be
provided by units, indices and connection licensing, without imposing a
second manually coordinated algebra on users. Recover code selectively
from Git rather than maintaining a dormant legacy path or feature flag.

This section records the new direction. At this checkpoint the active
implementation and living implementation contracts still describe the
pre-simplification machinery; align those contracts when the replacement
lands. No token-algebra code or authored declarations are removed here.


### Simplification implementation (2026-11-12)

Removed the checker token-vector propagation module and token-signature
responses/advisories, membership-to-signature defaults, global signature-fix
endpoint and signature categories. Retained expression/unit/index checking,
read-only scoped structural consistency reporting, membership licensing,
port membership guards and the existing mutability/frozen protections.

The editor now offers membership-only Connection networks, with no exponent
picker, signature-derived suggestions or automatic membership selection.
Existing vectors round-trip as inactive metadata; no bulk declaration
migration or authored-equation rewrite was performed. The saved data may
therefore still contain old observation/manipulation memberships. Their
impact-reviewed correction and transport-only actuation licensing remain
follow-up, not silently completed by this change.

Regression coverage checks mixed old signature metadata no longer produces
signal mismatch/squared-signal advisories, units remain enforced, no vector
is defaulted from membership, metadata survives an ordinary edit, structural
reports stay scoped/read-only and membership controls offer no exponents.


### Transport-only actuation implementation (2026-11-12)

Added generic `promo:targetEntityType` / API `target_entity_type` on
connection rules. Resolution requires that endpoint type or a descendant;
missing endpoint types fail closed for constrained rules. A swapped
bidirectional match checks the rule's original target. Rule CRUD validates
and round-trips the constraint, and the ontology editor exposes the target
picker. No rule-name special case is introduced in the resolver.

Seed floor `2026-11-12` adds a transport-system target constraint to the
existing core actuation rule when absent, preserves an explicitly declared
custom target and remains idempotent. Fork floors remain opt-in; frozen
versions are untouched. Tests cover transport descendants, capacity and
environment rejection, generic/swapped constraints, CRUD validation,
removal and idempotent floor application. This does not reclassify existing
controller variables or introduce a persisted sticker.

## 39. Effort coupling — the continuity arc knows its conjugate variable (2026-11-13)

### Problem

A physical token-flow arc asserts **continuity in effort and flow**.
The transport therefore must know *which* effort variable it reads at
each contacted capacity — at connection time, not as a deferred
instantiation inference.  The coupling signature existed in the
vocabulary since §32 stage-2 (`promo:drives` on mechanism leaves,
`function:effort` on variables) but had no consumer: peer matching was
raw token comparability, so any token-comparable variable could serve
as "the effort" and the mechanism's drive signature could not exclude
a wrong one.

### Ruling

- **Match rule (effort-role ports only).**  A port variable classified
  `function:effort` couples iff the peer exports a variable that is
  also `function:effort` **and** carries a token comparable to the
  demand-side mechanism's `promo:drives` (unioned up the
  `promo:parent` ancestry).  Identity (the shared boundary variable)
  always couples.  Flow and other ports bind by plain comparability,
  unchanged — the drive filter does not apply to them.
- **Derived, not stored.**  The pairing is recomputed from the pins —
  mechanism → drives → peer var-set — at both decision points: the
  modeller's connect-time adjudicator (`port_satisfaction`, advisory)
  and instantiation's port binder (authoritative).  No arc payload is
  written; the connection's semantics derive from ontology + library.
- **Distinct status.**  An effort port with no qualifying peer reports
  `effort-unavailable` (instantiation problem kind
  `effort-unavailable-port`), distinct from generic `unbound` — the
  hint names the missing export, not just the empty candidate list.
- **Graceful without drives.**  A mechanism (or non-mechanism demand
  side) declaring no `promo:drives` skips the token half of the rule;
  the effort-role match still applies.

### Implementation

`VarInfo.effort` flags `function:effort`-classified variables
(`_vars_collect` reads the `promo:axisValue` term).  `mechanism_drives`
maps each demand entity type to its drive-token set — supplied to
`build()` and `port_satisfaction()` by both service layers.  The
candidate loops in `satisfy._adjudicate` and `builder.candidates_at`
apply the rule; `emit_port` hints *"peer exports no function:effort
var carrying the mechanism's drive token"*.

Regression coverage: effort binds an effort peer carrying the drive
token; a merely token-comparable non-effort peer is rejected; an
effort peer on the wrong drive token is rejected; absent `drives`
degrades to role-only matching; non-effort ports are unaffected.
548 backend tests pass.

### Open

- **Signal-arc variable selection** (the access issue) — the same
  arc→variable binding slot, semantics differing by arc kind;
  discussion follows this section.
- **Multi-mechanism pairing** — `drives` is unioned over the demand
  type's ancestry; per-contact mechanism resolution remains the §32
  stage-2 `port-domain-ambiguous` tripwire.

## 40. One product, explicit contraction — `*` unified, `.` retired (2026-11-14)

### Problem

Two different operations shared the product surface: `a . b` was the
index-preserving (elementwise) product while `a * b` was an implicit
*reduce* product that contracted the single shared index — and the
explicit form `reduceSum(a . b, i)` used yet a third spelling for the
same underlying multiplication.  `rho * v` looked like a product but
silently summed; there was no way to write an elementwise product over
shared indices with the `*` glyph, and the implicit rule broke down
exactly where it mattered (zero or several shared indices).

### Ruled

- `a * b` is THE index-preserving product: elementwise over shared
  indices, ordered union of operand index structures otherwise
  (scalars included — `half * M` is legal).  It never contracts.
- `a . b` is retired — no `.` infix remains.
- Every contraction is explicit: `reduceSum(a * b, i)` names the
  summed index.  `a : b` (expand) is unchanged.
- The implicit-`Reduce` AST node and the `promolg:ReduceProduct`
  canonical op are gone; `ReduceProduct` survives only as a
  read-side signature so stored `rhsExpression` trees load for the
  migration.

### Migration (load-time, `persistence._migrate_product_operators`)

- Canonical trees: `ReduceProduct(a,b)` →
  `SumOverIndex(IndexPreservingProduct(a,b), shared)` with `shared`
  recomputed bottom-up from declared index structures; `.` spells
  `*` on regeneration.
- Literal-only equations: re-parsed under a legacy table, `_LegacyReduce`
  → `reduceSum( (a * b), i )`, re-printed.  A `*` under an enclosing
  aggregator whose index matches the shared one is already-migrated
  text — the rewrite is idempotent.
- Anomalies (shared index not exactly one, legacy parse failure) are
  logged and left untouched — those expressions were never checkable.
- Real data: all stored equations migrated mechanically; zero
  anomalies.  No equation needed a semantics change — every stored
  `*` contracted exactly one shared index.

Regression coverage: `test_migrate_products.py` exercises literal and
canonical rewrites plus idempotency; parser/checker/codegen/builder
tests cover the new `*` semantics.  548 backend tests pass.

## 41. Reference coordinate and vector components — two new indices — RULED (2026-11-14)

### Problem

The transport laws need the effort drop *along the transport's own
reference coordinate* (the through-direction), but the only direction
carrier in the expression language is `F_k` — node–arc incidence.
Two consequences surfaced after §40 made contractions explicit:

- **Declared vs bound divergence.**  In the declared space `p_mech`
  is `[N]` and `p_mech * F_conv` shares `N`, so the library check
  wants `reduceSum(…, N)` = `Fᵀ·p` per arc.  In the transport's
  *bound* scope `p_mech` binds `{A_conv:[contacts]}` (peer efforts),
  and the physics needs `F·p` = contraction over the contact axis —
  `Σ_a F[T,a]·p_a` = the through-drop `p_C₁ − p_C₂`, signed by the
  per-contact incidences at the transport's row (§15's orientation).
  `reduceSum(…, N)` in that scope computes `p[a]·Σ_n F[n,a]` =
  identically zero.  Verified in live emission: `fmc ≡ 0`.
- **The old implicit `*` hid this** — "contract the shared index"
  resolved per context (N declared, `A_conv` bound).  §40's explicit
  `reduceSum(…, idx)` pinned the declared reading; no single literal
  spelling satisfies both contexts.

The `F·p` trick also conflates roles: node–arc incidence is doing
double duty as the transport's reference direction, and it only works
for a 2-port through-path.

### Proposal (under discussion)

Two orthogonal indices, added to the index algebra:

- **`X` — reference coordinate** (through-direction).  Lives on the
  transport; elements are contacts in coordinate order (`x_in`,
  `x_out` for 2-port).  Contact-bound efforts (`p_mech`, `T`, `μ`)
  bind `X` instead of an arc sub-index — declared *and* bound
  contexts then evaluate the identical contraction.
- **Direction as data**: a signed vector `σ[X]` (`+1` in, `−1` out;
  constant for 2-port, per-contact orientation for n-port — same
  source data as `F`'s transport row).  Laws read
  `fmc = k·A·reduceSum(σ * p_mech, X)` — the drop *is* the coordinate
  contraction, explicit and context-invariant.  `d` (the ±1 sign
  param) becomes derived: `d = sign(reduceSum(σ * p_mech, X))`.
- **`C` — component index** `{x,y,z}`.  Lives on intrinsically
  vector variables: `vx,vy,vz` fold to `v[C]`, `r_x,r_y,r_z` to
  `r[C]` — component equations collapse to one `[C]`-indexed
  equation (elementwise `*` handles components).
- **Scalars stay scalar**: `m`, `n`, `U`, `T`, `p`, `μ`, `c`, `V`,
  and all through-flows (`fmc`, `fhc`, `fnd`) keep no `C`.  A flow
  rate through a transport is a scalar signed by `X`.
- **Momentum becomes `[C]`-indexed**: momentum content `P[C]`,
  momentum flows `fmom[C]`, forces `[C]` — the balance becomes three
  per-component conservation laws (physically correct: momentum
  conserves per component).  Convected momentum is `fmom = fmc·v`
  elementwise over `C`.
- **`F·f` balances unchanged** — `F_k` stays pure incidence; `σ[X]`
  is its transport-row restriction generalised to a first-class
  coordinate.  Arcs keep flows, coordinates keep efforts.

### The X↔C seam

A transport's `X` points somewhere in space.  For convection
(drives `token_momentum`) the pressure-drop force lands on the
momentum component matching the transport's spatial alignment —
placement metadata: the transport instance declares which `C`
direction its `X` is (direction cosines for diagonal cases,
deferrable).

### Ruled (2026-11-14)

1. **σ is instantiation-derived** — like `F_k`: per-model, emitted
   into `model_data` per transport scope.  Values = the transport's
   per-contact orientation signs (= `F_k`'s row at the transport),
   so `σ` reflects whatever orientation was assigned, not a fixed
   `{+1,−1}`.
2. **`X` elements are ordered contacts** — the order IS the
   coordinate direction; n-port gets n elements.
3. **Multi-port ruled now** — `σ` carries per-contact signs from the
   orientation assignment; flows stay per-arc `{A_k}`.  No 2-port
   special-casing.
4. **Token layer unchanged** — `token_momentum` stays one token; the
   `[C]`-indexed carrier suffices.  Token says WHAT flows, index
   says its algebraic shape.
5. **`X↔C` seam lands now** — transport instances carry placement
   metadata declaring which `C` direction their `X` aligns to
   (direction cosines deferred).
6. **Equations rewritten via the editor**, not migrated — the
   rewrite is semantic (new indices, σ), not mechanical; §40's
   lesson is that mechanical migration pins the wrong context.

### Mechanics (implemented 2026-11-14)

- **`X` is one global index** (`idx_x`): `indexClass` `coordinate`,
  `subIndexOf idx_arc` — arc-*like* through the sub-index chain, so
  element resolution, bound ordering and gathers reuse the arc
  machinery unchanged.  It carries **no `selector`** — its elements
  are per-scope contacts, not a fixed model-wide membership, so it
  never enters the resolved sub-index set (and selector-bearingness
  is now the F-factor mechanism test in seed + persistence).
- **`σ` is a scheme object** — `promo:Variable`
  `internalID sigma`, `indexStructure idx_x`, constant+parameter,
  dimensionless, token-neutral — same pattern as `F_k`.
  `SEED_FLOOR 2026-11-14` seeds both records.
- **No contact vars needed**: `p_mech`, `T`, `mu` keep `[N]`.
  In an event-dynamic scope the §32 port swap now binds the
  node-like declared index to `X` — `p_mech {X:[a1,a2]}` — the
  contacts ARE the coordinate elements.  Capacity scopes keep
  declared `{A_k}` bindings (upwind `F·c` contracts `A`
  correctly).  This was simpler than the proposed `p_x`/`T_x`
  retype — the same-IRI gather machinery is untouched.
- **`σ` binds `direction`**: a constant var whose sole index is
  `X` is the direction literal (parallel to arc+node constant →
  `incidence`).  Plan computes the signs — the base-F entries at
  each contact arc's in-scope end, in bound-element order — and
  emits a `ParamSlot` into the `values` channel (1-D vector via
  `_tab`; a sparse matrix would broadcast wrong).  `test_01`:
  `sigma_convection_transport = [+1, −1]`.
- **Laws contract `X`**: `fmc = k·A·reduceSum(σ * p_mech, X)` —
  the drop is the coordinate contraction, signed by `σ`.  `d`
  becomes derived: `d = sign(reduceSum(σ * p_mech, X))`.
- **`F_k` keeps only the balance role**: `reduceSum(F_k * f_k, A_k)`
  and the upwind `½(F − d|F|)·c` equations (lumped scope,
  arc-indexed) are untouched — F never again stands in for a
  reference direction.
- New problem kind `direction-ambiguous` (arc touching the entity
  at both/zero ends) — catalogued.

### Equation rewrite map (editor)

- `E_4`/fmc: `(kConvX*Ayz) * reduceSum((p_mech*F_conv), N)`
  → `* reduceSum((sigma * p_mech), X)`
- `E_11`/d: `sign(reduceSum((F_conv*p_mech), N))`
  → `sign(reduceSum((sigma * p_mech), X))`
- `fhc`, `fQx`: `reduceSum((F_heat*T), N)`
  → `reduceSum((sigma * T), X)`
- `fnd`: `reduceSum((F_diff*mu), N)`
  → `reduceSum((sigma * mu), X)` — `mu` is `[N,S]`-declared,
  binds `{X,S}` in the transport scope, contracts to `[S]`,
  broadcasts onto `fnd`'s `[A_diff,S]`
- `fhd`/radiation law: same `F_heat·T`-pattern
  → `reduceSum((sigma * (T*T*T*T)), X)`
- Balances + upwind pair: unchanged.

### Deferred

- Component fold: `vx,vy,vz`→`v[C]`, `r_x,r_y,r_z`→`r[C]` and the
  elementwise collapse of their equations — independent of the `X`
  work, same migration mechanics.
  **Machinery landed (2026-11-20):** `idx_component` floor-seeded as
  `C` with literal elements `{x,y,z}` via new predicate
  `promo:elements` (fixed indices declare their element set on the
  record; instantiation binds it directly — `index_source`
  `component`).  **Open before the fold:** the language has no
  component selection — `E_12`/`E_15`/`E_23` consume `vx` scalar-wise
  and `E_26`/`E_27` (`Axz`/`Ayz`) multiply *distinct* components, so
  `v[C]`/`r[C]` cannot spell them.  Options: seeded basis vectors
  `e_x[C]` (`reduceSum(e_x * v, C)` — the σ/`F_k` scheme-object
  pattern, needs element-keyed literal values bound on the var) vs a
  selection construct vs re-authoring those equations in the
  `[C]`/`[C,C']` view.
  **Selection ruled (2026-11-23) — seeded basis vectors.**  `e_x`/
  `e_y`/`e_z` are floor-seeded `[C]`-indexed constant+parameter
  variables (dimensionless, token-neutral) carrying the first
  seeded value-cell tables (`{x:1, y:0, z:0}` &c., keyed on the
  index's literal element names — no `atIndexElement` links).
  Value cells now resolve through the artefact's pin scope
  (`_binding_cells` scope walk, least→most specific), so the floor
  tables reach every pinning artefact.  `v_i ≡ reduceSum(e_i * v,
  C)` extracts, `e_x*vx + e_y*vy + e_z*vz` injects,
  `reduceSum(e_x*r,C)·reduceSum(e_z*r,C)` covers `E_26`/`E_27` —
  no `[C,C']` needed for the current equations.  *Remaining:* the
  `v[C]`/`r[C]` consumer rewrites themselves.
- Tensors (stress, momentum-flux) stay out of scope — staged in §42.

### Momentum slice (implemented 2026-11-24)

The `[C]`-fold ruling ("momentum content `P[C]`, momentum flows
`fmom[C]`, forces `[C]`") landed as two authored subjects:

- **Fluid mechanics — convection-transport scope.**  Three per-contact
  exports declared `[A_conv,C,N]` (the `fmc` pattern — the arc slot
  binds the transport's own contacts, the node slot is what the peer
  gathers):
  `fP := e_align * σ*p_mech * Ayz` (pressure force landed on the
  aligned component), `v_str := e_align * kConvX*inv(ρ) *
  reduceSum(σ*p_mech, X)` (stream speed `u = k·Δp/ρ ≡ fmc/(ρ·A)`
  projected onto `C`), `fmom := fmc * v_str` (convected momentum).
- **Mechanics — lumped-capacity scope.**  `P [C,N]` content
  (`P := m·v` definitional), `F_g := m·g·e_z` body force,
  `dPdt := reduceSum(F_conv * (fmom + fP), A_conv) + F_g` per-component
  conservation, `v := P·inv(m)` for the state-formulated regime.

Lessons worth keeping:

- **Emit pairs elementwise axes by index *name*, not bound elements** —
  `e_align{X,C} × fmc{A_conv,N}` produced an outer product even though
  `X` and `A_conv` bind to the same contact arcs.  `e_align` consumers
  must stay `X`-typed; an `A_conv` factor needs an `X`-view alias or a
  `reduceSum`/`F`-contraction.  (`E_v_str`'s first spelling
  `e_align·fmc·inv(ρ·Ayz)` was rejected by the emit — the X-typed
  `kConvX·inv(ρ)·Σσp,X` form is identical via `E_4`.)
- **`v` could not go `port_variable`** — §18 structural lock (12
  referencing equations).  `v_str` carries the stream-velocity role
  instead — the semantically better split anyway (transport stream
  velocity ≠ lump bulk velocity).
- **Export `carriesToken` scopes candidacy** — `v_str` with a mass
  token made it a second candidate for the lumped `fmc` port
  (`ambiguous-port`); momentum-only resolves it.

`test_01`: the transport's sequence is `[E_4, E_v_str, E_fmom, E_fP,
E_29]` with `v_str`/`fmom`/`fP` outputs; `Node_2` declares
`alignedComponent=x`; `alignment-undeclared` fired on demand and
cleared on declaration; generated python emits all three.  **The
lumped balance is wired** (landed same day): `etype_lumped` carries
`state_variables=[dmdt, dPdt]`, ports `fmc`/`fP`/`fmom`, sequence
`[E_m_def, E_F_g, E_dPdt, E_29]` (base `E_29`), `dPdt` marked
output; `dPdt` emits as the second u-state and `fmom`/`fP` gather
the transport's `[C]`-rows.  Three structural changes landed for
it:

- **`state_variables` is set-valued** — `AssignmentOut`,
  `SelectionIn`, `AssignmentInfo`, `EntityInstantiation(Out)` all
  carry lists; `promo:hasStateVariable` writes multi-valued.
  Declared states win on PUT; the base equation's lhs is the
  derived fallback.  `E_m_def` (`m := dmdt`) binds the live mass
  state for `F_g`/`P` instead of instantiating a shadow datum.
- **Identity pairing at ports** (`builder.candidates_at`) — a
  same-IRI donor beats token-comparable substitutes; ambiguity is
  only among substitutes.  Three momentum-tokened exports made
  `fmom`/`fP` ambiguous without it.
- **Vector port gathers** — `Gather.map` is positions along the
  peer's contact axis (`map_index`, `peer_indices` on the slot);
  emitters do axis-takes (`np.take`, `selectdim`, subscripted
  `MultiDimVar.value`) + reshape, so `[C]`-rows gather whole.
  Coverage counts rows × span.

## 42. Tensor-index layer for sheet mechanics — DESIGN PROPOSAL (deferred)

### Motivation

A coming project — deforming sheets driven in a controlled way —
needs mechanics: displacement/velocity fields, stress, strain,
actuation forces, contact regimes.  These are genuinely
*tensor-valued* quantities over the spatial basis `C`, and the
expression language today has no frame semantics for them (§41
deferred).  This proposal stages the work so it can start when the
project does; until then the focus stays on mass and energy for
reactive and passive systems.

### Two senses of "tensor"

- **Array sense — already present.**  Multi-index objects
  (`F[N,A]`, `mu[N,S]`), Einstein-style contraction (implicit `*`
  over shared indices), `reduceSum` traces.  A `σ_stress[C,C']`
  would *store and contract* correctly today.
- **Geometric sense — absent.**  Tensors are defined by their
  transformation law under basis change (material frame vs lab
  frame, anisotropy axes vs world).  ProMo's indices are discrete
  label spaces; nothing enforces frame agreement — mismatched
  frames would contract silently, the same class of bug the §41
  `reduceSum(·,N)` anomaly was, one level deeper.

The staged plan delivers the array layer now and gates the frame
layer on actual physics need.

### Stage A — index, mesh, stencil (reuses §41 machinery)

- **`C` index**: seed `idx_component` `{x,y,z}` + the deferred
  `C`-fold (`v[C]`, `r[C]`, `P[C]`, forces `[C]`) — already ruled
  in §41, first consumer arrives with the project.
- **Paired `[C,C]` self-indexing**: `reduceSum(·,C)` cannot
  disambiguate two `C` slots.  Options: positional contraction
  (`reduceSum(·,C@1)`-style) or primed label copies (`C` vs `C'`
  as distinct index IRIs over the same elements).  Design work —
  small, must be settled before stress/strain equations land.
- **Mesh entities**: the FEM discretisation turns the sheet into
  ProMo's native home — algebraic equations on a discrete
  structure.  Elements/nodes become index-bearing occurrences;
  element–node incidence `E[M,N]` is the same incidence trick as
  `F[N,A]`, carrying assembly.
- **Geometric stencils**: gradient `G`, divergence `D`,
  strain–displacement `B` as *instantiation-computed structural
  operators* — the `σ`/`F` emit-per-scope pattern applied to mesh
  geometry instead of topology.  Operators live in the ontology,
  values land in `model_data`.
- **Physics scope for stage A**: small-strain linear elasticity in
  a single (lab) frame — pure array algebra, no transformation
  semantics required.  Double contraction `Cijkl·εkl` via nested
  `reduceSum` if composable, else a `contract(·,[i,j])` primitive.
- **Actuation & regimes**: `promo:drives` + actuation arcs already
  seeded; contact/slip regimes map onto event-dynamic entities.

### Stage B — frame semantics (gated on physics)

- **Frame as a classification axis** on `[C]`-indexed variables —
  ontology-declared (lab / material / crystal), checked at
  contraction time: mismatched-frame products become checker
  errors, not silent wrong answers.
- **Finite kinematics**: deformation gradient `Fdx[C,C']`,
  objective rates (Jaumann-type correction terms as ordinary
  equation terms once frames exist).
- **`X↔C` seam generalises**: a sheet's `X` (in-plane reference)
  becomes tangent-plane placement metadata — the same seam §41
  drew for transports, now orienting element-local frames.

### Open for the project

- Mesh representation: occurrence composition vs dedicated mesh
  index; where element geometry (areas, edge vectors) lives.
- `C'` naming/positional contraction mechanics — leaning primed
  copies; settle the convention (`C', C'', C'''` vs `C1..C4`)
  before the first stiffness equation (rank-4 needs four).
- `same-element-space` predicate declaring `C'` a copy of `C`
  (ontology data; instantiation binds elements through it).
- `C` fold is prerequisite: seed `idx_component`, fold
  `vx,vy,vz→v[C]`, `r_x,r_y,r_z→r[C]` — do before the project's
  first equations, since `ParDiff(v[C], r[C'])` needs `r[C]`.
- Seeded scheme objects `δ[C,C']` (Kronecker; trace/divergence)
  and `ε[C,C',C'']` (Levi-Civita; curl) — `sigma`/`F_k` pattern.
- Stencil storage format in `model_data` (sparse COO like `F`).
- Whether `d()/dt` needs a material-derivative sibling operator.

### Duplicate slots — analysis (2026-11-20)

The two mathematical grounds for distinguishing same-set index
occurrences:

- **Occurrence (name/position).**  Slots of a multilinear map are
  distinct *arguments*; notation distinguishes them by letter
  (`σ_ij`, i vs j) or prime (`i, i'`).  Necessary but semantically
  empty — the names range over the same space.
- **Variance (co-/contravariant).**  `u^i` vs `v_j`; contraction
  pairs opposite variances.  Real checker-gate material, but it
  presupposes metric + frame semantics (Stage B) — and it never
  disambiguates `[C,C]` anyway: `σ^{ij}`, `ε_{kl}`, `C_{ijkl}`
  are symmetric-variance, so occurrence naming is unavoidable
  regardless.

Precedent: the control case already solved this — `A[dx, x]` uses
distinct IRIs over the same element set (differential index ↔
integral index, §11.5 of the math-language comparison).  `C`/`C'`
is the same mechanism verbatim and composes with §40:
`σ[C,C'] * ε[C,C']` is elementwise over both shared indices, then
`reduceSum(·,C)` then `reduceSum(·,C')` = the double contraction —
zero new machinery.  The only new *data* is a predicate declaring
`C'` "same element space as `C`" so instantiation binds elements
(ontology data, not code).

Positional `C@1` is weaker: symmetric tensors make positions
interchangeable, permutations renumber tags, and it must relax
the unique-IRI invariant (§11.6 — the invariant that keeps
`ReduceProduct` binary and contraction unambiguous) with
IRI+occurrence equality through checker, binder, emitter.

**Leaning: primed copies** (user-agreed 2026-11-20).  Rank-4
(`C_{ijkl}`) needs four — `C, C', C'', C'''`; the naming
convention should be settled before the first stiffness equation.

### Spatial operators — discussion (2026-11-20)

Question raised for fluid mechanics (Navier–Stokes): introduce
named operators (`grad`, `div`, `curl`, `lap`, `D/Dt`), or stay
with `ParDiff` + contraction?

- **Leaning: no named spatial operators** (user's instinct,
  agreed).  They are composite.  `ParDiff` w.r.t. an indexed
  coordinate naturally mints the second copy: the Jacobian
  `J = ParDiff(v[C], r[C'])` is `[C,C']` — field slot vs
  coordinate slot.  Divergence is then the trace, expressible
  with today's machinery plus one seeded scheme object: the
  Kronecker `δ[C,C']` (identity across same-element copies —
  the `σ`/`F` pattern applied to index copies):
  `div v = reduceSum(reduceSum(δ * J, C'), C)`.  The elementwise
  product selects the diagonal; two `reduceSum`s contract.
  Laplacian = `ParDiff∘ParDiff` over the same copies;
  `curl` = Levi-Civita `ε[C,C',C'']` contraction — which needs
  the primed-index machinery anyway.
- **On a mesh the operators are stencils, not expressions** —
  Stage A's `G`, `D`, `B` are instantiation-computed matrices in
  `model_data` (the `σ`/`F` emit-per-scope pattern).  The
  symbolic layer needs no operator vocabulary for them at all:
  the equation says `reduceSum(G * u, M)`, the mesh transform
  computes `G`.
- **Hidden-slot argument.**  Named operators conceal exactly the
  index pairing the checker needs — `∇·v` vs `v·∇` vs tensor
  `div σ` are three different contractions under one glyph; the
  §40 lesson (explicit `reduceSum` pins the context) applies one
  level up.
- **The one real candidate is `D/Dt`** — the material derivative
  is a *different time-derivative semantics* (Eulerian vs
  Lagrangian), not a spatial operator.  Stays in "Open for the
  project"; expressible meanwhile as
  `TotalDiff(u,t) + reduceSum(ParDiff(u,r[C']) * v[C], C')` —
  the advection term stays visible, arguably the more honest
  physics.

### Status

PROPOSAL — not ruled.  Pick up when the sheet project starts;
Stage A is designed against machinery §41 already landed, Stage B
lands only when the physics (large rotation, anisotropy,
material-frame constitutives) demands it.  Leanings recorded
2026-11-20: primed index copies over positional tags; no named
spatial operators — `ParDiff` + contraction (+ seeded `δ`/`ε`
scheme objects) suffices.

## 43. Flow classification grants port export — RULED & implemented (2026-11-15)

### Problem

Port semantics is declared twice: the `function:` axis *says* what
a variable is (flow/effort/state/…), while `port_variable` +
`hasPortVariable`/`stateVariable` *enforce* binding elsewhere.
For flows the duplication was pure friction — flagging every
through-flow by hand (and the flag is structural-locked once
referenced, so fixing it needs an equation-detach dance).

### Ruling

- **`function:flow` ⇒ exportable.**  A through-flow lives on the
  arc by nature — the arc IS the port.  `VarInfo.flow` is derived
  from the classification and `exportable = port_variable or flow`
  replaces the bare flag at every binding site: peer state-hiding,
  candidate preference (`flagged or raw`), self-donation, and
  phantom-boundary exports.
- **`port_variable` shrinks to an override** — the exceptional
  export: non-flow vars a peer must read (measurement/signal
  style, or an unhidden state).  Flows no longer need it.
- **`hasPortVariable` (the demand) is unchanged** — it is
  genuinely per-entity-type information: which of several flows
  the capacity reads is not derivable from the classification.
- **Effort coupling is the precedent** — `function:effort` already
  gated §38 pairing; this completes the pattern rather than
  inventing it.

### Caveat

The label is now load-bearing: a wrong `function:flow` silently
changes binding.  Acceptable under the same trust model as
`function:effort` (classifications are structural-locked while
referenced).

### Migration & verification

- All `function:flow` vars flagged via store mutation
  (`fmc`/`fnd`/`fnc`/`pGain` were already flagged; `fhc`/`fhd`
  were then unflagged — the flag is redundant *and* tripped the
  `portVariable ⇒ carriesToken` data-consistency rule since they
  carry no token).
- `ahc`/`and`/`ahd` were found misclassified `function:flow` —
  reclassified `function:state` (they are accumulations) and
  unflagged; correct labelling, no machinery effect.
- Regression: `test_exportable_flag_or_flow` + `J` fixture moved
  to unflagged `flow=True` so every port-binding test exercises
  the classification path.  560 backend tests pass.

## 44. Balances specialize to connected ports — RULED & implemented (2026-11-15)

### Problem

A behaviour assignment written for all possibilities declares
ports for every mechanism it *could* support (`fmc`, `fnd`,
`fQx`, …).  Instantiated on a model that connects only some of
them, the unused demands previously produced `unbound-port`
problems — pushing toward either zero-instantiating missing
ports (a physical lie: zero flow ≠ absent mechanism) or
proliferating entity types per port configuration.

### Ruling

- **Declared flow port binding nothing ⇒ absent, no problem.**
  No carrier-matching arcs, or arcs whose peers export no
  comparable flow — either way the mechanism isn't connected,
  and the balance simply has no term for it.  The var binds
  its (possibly empty) member list like any other declared
  index; `F·f` over an empty domain contributes nothing.
- **Non-flow demands keep `unbound-port`.**  An unconnected
  effort isn't "no mechanism" — it makes the law ill-posed
  (a transport with no effort cannot compute a flow), so the
  problem report is the intent check worth keeping.
- **`hasPortVariable` stays the contract.**  The declaration
  documents the interface and drives checking; the topology
  decides which declared ports actually bind.

### Implementation

`builder.py` port loop: `var.flow` ports skip `emit_port` when
`pb.status == "unbound"` (all three paths — arc-indexed,
node-indexed, scalar) or when `carrier_ok`/`cands` is empty.
`ambiguous` and `effort-unavailable` still report.

### Verification

`test_absent_flow_port_is_silent`: a declared energy-token flow
port on a mass-only topology emits no `PortBinding` and no
problem, while a non-flow twin on the same topology still
reports `unbound-port`.  561 backend tests pass.

## 45. A bare incidence factor's node axis is never a contraction index — RULED & implemented (2026-11-22; narrowed same day for the upwind selector)

### Problem

`reduceSum(p_mech * F_conv, N)` — the pre-§41 through-drop spelling —
*type-checks* in declared space: `[N]*[A,N] → [A,N]`, contract `N` →
`[A]`, units clean.  It only becomes wrong in bound scope, where the
effort's declared `N` is replaced by the contact coordinate `X` — the
contraction then sums the wrong axis pair and drives the flow to zero
(the §40 incident).  The user meets σ only in the library; nothing
stopped them from re-deriving the broken form, and the failure mode is
silent wrong math, the exact class of mistake the checker exists for.

A check-time gate seemed to need binding knowledge the checker lacks —
whether `p_mech` rebinds is a builder fact.  But the bad *shape* is
decidable from declared data alone.

### Ruling

- **An incidence factor's node axis is never a legal contraction
  index when the factor appears as a bare linear factor.**  Balances
  contract the arc axis (`reduceSum(F*f, A)`); through-drops go
  through the direction vector (`reduceSum(σ*effort, X)`, §41).
- **Refinement (same day): the ban is the linear factor, not the
  axis.**  The first cut rejected *any* `Var` leaf carrying
  `[node, arc]` inside an `N`-contraction — which broke the upwind
  weight `half * (F - d*abs(F))`: there `F`'s node axis *must*
  contract, because the weight selects the upstream node per arc and
  `σ` cannot express it (`σ[X]` has no node axis).  The distinguishing
  shape is linear-vs-nonlinear use of `F`: `effort * F` (bare factor)
  is the §40 bug; `F` nested under `Add`, `abs`, `Power`, … is a
  selector, not a through-drop.  The rule therefore flags only `Var`
  leaves reaching a top-level additive term through
  `IndexPreservingProduct`/`Group` alone.
- **Detection is structural, not semantic.**  The flagged leaf's index
  structure contains both a `node`-source index and an arc-source
  index (arc-like includes declared sub-indices via `subIndexOf`).
  Index *source* is already ontology data (`indexClass` →
  `index_source` alias); the rule keys on the class, never on `F_*`
  IRIs — semantics in the ontology, enforcement in the checker.
- **Both contraction surfaces covered**: `reduceSum(…, I)` and
  `Product(…, I)`.
- **The checker is the teacher.**  The error names the user's own
  symbols and the correct spelling
  (`reduceSum(sigma * effort, X)`), so violating the rule *is* the
  lesson — no prior knowledge of binding scope required.
- **Bound-scope recheck stays the backstop** (`var_bound` →
  re-check in binding context at instantiation).  The two layers:
  authoring catches the shape, instantiation catches the signature.

### The generic class (recorded for the contract vocabulary)

One instance of *declared-space typing is symbolic; element space only
exists in binding scope*.  Siblings: species `S` (fixpoint elements),
mechanism sub-indices (selector membership), the port-var index swap
itself (§32 — currently implicit, could become declared), and the
blocked `C`/`C'` component folds (§42).  The general mechanism —
declare binding contracts on indices/vars, enforce contract-shaped
rules keyed on index class — is the candidate home for any further
rules of this family.

### Implementation

`checker.py`: `_check_contraction_index` fires when the reduction
index has `index_source == "node"` and a *linear-factor* `Var` leaf
of the argument carries both that index and an arc-like index
(arc-source or `sub_index_of` an arc-source).  Linearity is decided
by `_terms`/`_factor_vars`: the argument splits on top-level `Add`
(`Group` transparent), and within each term only leaves reachable
through `IndexPreservingProduct`/`Group` count — a var nested under
`Add`, `abs`, `Power`, … is a nonlinear form and exempt.
`IndexStructureError` with the σ hint.  No schema, vocabulary, or
data change.

### Verification

`test_checker.py` `_flow_space` + seven tests: the bad form errors on
both `reduceSum` and `Product`, including a `p*F` term hidden in a
sum; the balance (`F*f` over `A`), the σ law (`σ*p` over `X`), plain
node contractions (`p*p` over `N`), and the upwind selector
(`half*(F - d*abs(F))` over `N`) stay legal.  574 backend tests
pass — no existing equation regressed, including the real library
`cfV` upwind equation verified against the live store.

## 46. Energy balances are separate objects; friction is a transfer term — CONVENTION (2026-11-22)

### Context

Completing the library energy balances (continuation of the enthalpy
work): `dHdt` already held enthalpy transport + conductive heat + shaft
work.  The question was how to treat work — the ruling, then the
structure that fell out.

### Rulings (library-model conventions)

- **Flow work is inside enthalpy.**  `h = u + p/ρ` already carries
  the `p·fw` volume work of crossing a boundary — no separate term
  (user-ruled; `ah` unchanged).
- **Balances are independent objects, never summed.**  `dHdt`
  (thermal), `dEmdt` (mechanical), `dEtotdt` (total / 1st law) each
  accumulate their own quantity.  The same physical input legitimately
  appears in more than one — `aw` sits in all three — because each
  statement sees the work, not because it is counted twice.  (User's
  bio point: fermenter stirrer power can exceed reaction enthalpy, so
  shaft work must be visible wherever the statement needs it.)
- **Friction is a transfer term, not a sink.**  `fl [A_conv,N]` is an
  *imposed boundary port* (like `fWs`) for transport friction; `al`
  enters `−` in `dEmdt` and `+` in `dHdt` — dissipated mechanical
  power *is* thermal input.  `fl` is defined as transport friction
  only (a stirrer dissipates through `aw`), so nothing double counts.
- **Shaft work is authored as an imposed boundary port** (`fWs
  [A_work,N]`, no equation), not a σ-law transport — the mechanism
  supplies it.
- **Bernoulli-with-friction is a reading, not an equation.**  At
  steady state (`dEmdt → 0`, divide by `fmc`) the balance reduces to
  `Δv²/2 + g·Δz + Δp/ρ = w_s − l_w`; the library stores the balance.
- **`dEtotdt` reuses the enthalpy transport** (`reduceSum(ah,S)` +
  `akp` = the kin+pot leg) — no `h_spec`/`etot` vars.

### Authored records

`g` (ontology `const_g`, 9.81 m·s⁻² — first *physical* constant in the
seed; `SEED_CONSTANTS` extended to 5-tuples carrying optional units).
Library: `fKin`/`fPot`/`fPflow` `[A_conv,N]` advected flows
(`fmc·v²/2`, `fmc·g·r_z`, `fmc·p/ρ`), `fl` `[A_conv,N]` port,
`al`/`amech`/`akp` `[N]` aggregates (`balance` class), `dEmdt`,
`dEtotdt`; `dHdt` gained `+ al`, `balance` class, eq key `E_dHdt`.
Consistency 65/4 bound-scope/0.  Deferred: a λ·(L/d)·ṁ·v²/2
constitutive law can later replace the imposed `fl`.

## 47. Quasi-steady regimes are sibling entity types, not runtime flags — RULED & implemented (2026-11-24)

### Problem

`dPdt` integrated on `etype_lumped` is the correct general model —
explosions and fast transients genuinely integrate momentum alongside
mass/energy.  But in most engineering applications the mechanical DOF
relaxes orders of magnitude faster than the conserved contents, and
integrating it forces a stiff solver — too costly on large models.
Both regimes are legitimate; the choice is per application, not a rule.

### Ruling

- **Regime is assignment-level.**  `state_variables` decides which
  DOFs integrate.  Quasi-steady momentum = `dPdt` leaves
  `state_variables` while `E_dPdt` stays in the sequence — the balance
  emits as a plain scheduled block, an algebraic net-force output that
  *is* the support reaction.  No new backend machinery: the scheduler
  already excludes state LHSs from `defines`, so the same equation
  plays integrated in one assignment and algebraic in the other.
- **Sibling entity type, not a variant flag.**  `etype_lumped_qss`
  (`promo:parent etype_lumped` — capability inheritance carries
  `cap_reaction_host`) keeps the same scale composition
  (uniform/finite, macro dynamic — mass and energy still integrate)
  and binds its own assignment.  Per-node mixing inside one model
  comes free: the fast region keeps the dynamic lump, the bulk takes
  the quasi-steady one.  Mirrors the CWA dynamic/event-dynamic split
  the transport side already expresses.
- **Not a runtime flag.**  The regime changes emitted code shape (the
  state count), so it binds at modelling time — unlike `steady_state`,
  which only re-points the emitted `initial()` t0 solve (`der = 0`
  residuals) and remains available on both variants.
- **What the algebraic balance determines is future work.**  Today the
  net force is a diagnostic (the supports absorb it).  Once a
  velocity-dependent force law lands (the queued `fl` constitutive),
  `ΣF(v) = 0` can instead determine `v` — the algebraic-loop solver
  already exists.

### Implementation

`etype_lumped_qss` via `POST /api/ontology/entity-types`
(`parent=etype_lumped`); its assignment via
`PUT /api/behaviour/assignment` on `…/library/assignments`:
`state_variables=[V_57]`, sequence `[E_m_def, E_F_g, E_dPdt, E_29]`,
ports `fmc`/`fP`/`fmom`, `instantiated=[V_34]`, `outputs=[V_121]`,
`closed=true`.  Author record: `scripts/author_lumped_qss.py`.

### Verification

`test_qss_assignment_emits_balance_algebraically`: a balance equation
kept in sequence but dropped from `state_variables` emits as a
scheduled block (`V_P = …`), with no state unpack, no `dy` slot, and
the §21 output tap preserved.  Live round-trip: the assignment
reports `closed=True` and `reaction_host` inherits via `parent`.
581 backend tests pass.

## 48. Contents bind rate-named state slots through a running Integral, not a rate alias — RULED & implemented (2026-11-24)

### Problem

The library's balances are written as rate equalities
(`dmdt := ΣF·f` — dimensionally true), and the assignment declares
the *rate* var as the state.  Emission's slot pun — "the slot named
`dmdt` carries `∫dmdt = m`" — is correct in generated code but left
no honest way to bind the *content* var.  `E_m_def` asserted
`m := dmdt`: right at runtime, false as a recorded relation — the
consistency checker correctly errored (kg ≠ kg·s⁻¹).

### Ruling

- **The honest record is the running integral.**
  `m := Integral(dmdt :: t in [to, t])` — kg·s⁻¹·s = kg, physically
  true, checker-green.  `E_75` rewritten to this form (class
  `eqclass_generic`; it is a definition, not a constitutive law).
- **Inside an ODE rhs, a `DefInt` over `t` has exactly one
  reading.**  The integrator already accumulates the state's rate —
  `Integral(x :: t in [to, t])` with `x` a declared state IS the
  slot's content.  `plan()` marks such blocks `alias_of` (marker:
  `DefInt` + `VariableReference` body ∈ state_vars + integration
  var == upper bound); `render_rhs` emits the slot name — the pun
  lives in emitted code, not the record.
- **Horizon forms are not aliases.**  `Integral(x :: t in [to, te])`
  (the archival `E_30`) keeps quadrature — var ≠ upper is the
  structural distinction.
- **Non-state integrands are not covered.**  `Integral(y :: t in
  [to, t])` with `y` algebraic would need its own accumulator — no
  machinery; it still emits quadrature (wrong in a derivative body).
  Surface as a plan problem when needed.

### Consequence already visible

`ic_targets` binds the `DefInt` lhs as an accumulator, so `m` now
appears as an IC need — physically correct (`m(t0)` is required; it
equals the `dmdt` slot's `y0`), though reporting it on both vars is
mild noise until the t0 UI learns the alias.

### Implementation

`PlanBlock.alias_of` + `plan._integral_alias` (canonical-gated, so
the `.trig` `rhsExpression` is load-bearing — text-only equations
never alias); `emit_common.render_rhs` short-circuits to the
instance name.  `E_75` rewritten via `PUT /variables` (re-derives
incidence `[dmdt, t, to]`, `rhsExpression` is a
`promolg:DefiniteIntegral`).

### Verification

`test_integral_of_state_emits_slot_alias`: alias block emits
`V_9 = V_1`, no `quad_vec`; `[to, te]` variant stays non-alias.
Library consistency: 0 errors / 69 consistent / 6 bound-scope
(E_75 was the sole error).  582 backend tests pass.

## 49. Darcy friction law — `fl` goes from imposed port to computed export — RULED & implemented (2026-11-24 PM)

### Ruling

The constitutive law §46 queued lands on `fl` itself: the variable
keeps `port_variable` (the lump still gathers it via `al`/`E_63`) but
gains `E_fl`.  An *imposed* boundary port and a *computed* export are
the same graph shape — the port flag declares gathering, the equation
declares how the value arises.

- **Law**: `fl := (half·lam) · ((Lp·inv(dp)) · (fmc·reduceSum(v_str·v_str, C)))`
  — the Darcy-Weisbach dissipated power λ·(L/d)·ṁ·v²/2 per contact.
- **`v_str`, not `v`** — dissipation lives in the pipe (the
  transport's stream velocity); the lump's bulk velocity would be the
  wrong physics.  v² folds `reduceSum(v_str·v_str, C)` per §41.
- **λ, L, d stay separate symbols** — no folded `λL/d` parameter.
  λ is a distinct physics (eventually Re/roughness-dependent) and `dp`
  can later constrain `Ayz`; the law must stay legible.
- **Arc-bound parameters.**  `lam`/`Lp`/`dp` bind `[A_conv]` — the
  arc *is* the pipe — following the `d` (V_26) precedent for
  arc-local quantities; instantiation fills them via
  `instantiated` + value cells.
- **`dp`, not `d`** — the `d` label is taken (V_26, the flow
  direction sign).  Pipe diameter is `dp`.

### Authored records

`V_123 lam` (dimensionless), `V_124 Lp`/`V_125 dp` (m), all
`{det: variable, fun: parameter}` class, token-neutral, `[A_conv]`.
`E_fl` on `V_109` (eqclass_generic); doc updated from "imposed".
`etype_convection_transport` assignment: `E_fl` sequenced after
`E_fP`, `fl` joined `outputs` (same role as `fP`/`fmom`/`v_str`/
`fmc`), `lam`/`Lp`/`dp` joined `instantiated`.  `closed=True`.
Consistency: 0 errors / 70 consistent / 6 bound-scope (76 equations).
Author record: `scripts/author_friction_law.py`.

Still open: the lump-side consumption path (`al`/`dEmdt`/`dHdt` into
an assignment — the energy-balance wiring), and the §47 upgrade this
enables — `ΣF(v)=0` determining `v` on `etype_lumped_qss` once a
velocity-dependent force enters the momentum balance.

### Repairs landed the same session

- **§47 records restored.**  `etype_lumped_qss` + its assignment were
  authored in memory but wiped by a `uvicorn --reload` *before* the
  first save — the `e46d98f` data diff carries no `lumped_qss`
  triples.  Re-ran `scripts/author_lumped_qss.py` and saved.  Lesson
  sharpened: **scripts/ is inside the watched tree** — any source
  edit (including author scripts) reloads and drops unsaved
  mutations; batch mutations and save in one step.
- **Runtime variables are `instantiated`.**  §48's `E_m_def`
  (`Integral(dmdt :: t in [to, t])`) binds `universe!t`, which no
  assignment declared — *both* lumped assignments evaluated
  unclosed (the stored `closed=true` flags predated §48).
  `t` is the solver's integration variable — supplied at runtime
  like `p_mech` — so `V_11` joined `instantiated` on
  `etype_lumped` and `etype_lumped_qss`; both now `closed=True`.
- **`_Matlab.permute` implemented** — the last dialect gap: a rhs
  whose checked index order differs from the lhs declaration now
  emits `permute((…).value, [p])` re-wrapped in the lhs's
  MultiDimVar labels (`.transpose()`/`permutedims` equivalents
  already existed).  `permute`'s dialect signature gained
  `(indices, space)` for the label re-wrap.
  Regression: `test_emit_matlab_lhs_index_conformity`.

## 50. Mechanical balance wired — `fl` gets its consumer — implemented (2026-11-24 PM)

### Ruling

With `fl` computed (§49), the §46 mechanical balance wires into the
dynamic lumped assignment.  `dEmdt := amech + aw − al` is a
**diagnostic output, not a new state** — §46 already ruled balances
are independent objects, never summed; mass+momentum remain the
integrated contents.  The thermal/total balances stay unwired: their
enthalpy leg (`reduceSum(ah, S)`, `ah [N,S]`) pulls the species
layer — separate work item.

### Two gaps the wiring exposed

- **`P` had no content-of-state alias.**  `v := P·inv(m)` (the
  mechanics reading `fKin` needs) requires `P`, whose only equation
  was the definitional `P := m·v` — a loop against `E_v_fromP`.
  `E_P_int` applies the §48 pattern verbatim: `P := Integral(dPdt
  :: t in [to, t])` — the dPdt slot carries P, the alias emits the
  slot name.  `E_P_def` stays for models that *compute* P.
- **`r` is instantiation data on the lump.**  `fPot` reads node
  position; `V_115` joins `instantiated` — geometric datum like the
  arc-bound `lam`/`Lp`/`dp`, per-element value cells.

### Authored

`etype_lumped`: sequence += `E_P_int`, `E_v_fromP`, `E_fKin`,
`E_fPot`, `E_fPflow`, `E_aw`, `E_al`, `E_amech`, `E_dEmdt`
(`E_29` still closes); ports += `fl`, `fWs`; instantiated += `r`;
outputs += `dEmdt`.  `closed=True`.  Consistency 0 err / 71 ok /
6 bound-scope (77 eqs).  Author: `scripts/author_energy_wiring.py`.

`etype_lumped_qss` deliberately untouched — no `dPdt` state means no
`P` slot, so `v := P/m` cannot fire; the quasi-steady energy path
waits on `ΣF(v)=0` determining `v` (the §47 upgrade `fl` now
unblocks on the energy side).

## 51. Thermal/total balances wired — ports cut the species chain — implemented (2026-11-24 PM)

### Ruling

`dHdt`/`dEtotdt` wire into the dynamic lumped assignment on the
§50 pattern — **diagnostic outputs, not states**.  The feared
"species layer" dependency dissolves at the port boundary: every
species-carried flow (`fnc`, `fnd`, `fQx`) is port-carried, so the
convective/diffusive/heat legs gather boundary values and the
reaction/EOS stack behind them never enters the lump's closure.
What the lump actually computes is only `fhc := fnc·h`,
`fhd := fnd·h`, the `F`-gathers `ahc`/`ahd`/`ahq`, and the two
balance readings — the species layer it needs is the **S-index
extent** from §20 distribution, not the species equations.

- **`h` is instantiation data on the lump** (like `Mm`, `N`):
  partial-molar-enthalpy values are property data at this scale.
  The EOS derivation stays in the library for scopes that carry a
  fundamental relation.
- **`E_53` fixed root-cause**: `h := H·inv(n)` divided the `[N]`
  lump total by per-species moles — dimensionally clean,
  physically wrong.  Now `h := ParDiff(H, n)`, the formalism's
  n-conjugate effort of `H` — same pattern as `mu := ParDiff(U,n)`
  and `Cp := ParDiff(H,T)` (precedent for differentiating a
  *defined* potential already existed).

### Authored

`etype_lumped`: sequence += `E_54`, `E_55`, `E_56`, `E_57`, `E_58`,
`E_59`, `E_akp`, `E_dHdt`, `E_dEtotdt` (before `E_29`); ports +=
`fnc`, `fnd`, `fQx`; instantiated += `h`; outputs += `dHdt`,
`dEtotdt`.  `closed=True`; consistency 0 err / 71 ok / 6 bound-scope
(77 eqs).  Author: `scripts/author_thermal_wiring.py`.  Regression:
`test_thermal_balance_wires_species_legs_as_readings`.

`etype_lumped_qss` still untouched — `dEtotdt → akp → fKin → v → P`
needs the absent `P` slot (same §50 deferral).

### Consequences / open

- **`fnc`/`fnd` report `ambiguous-port` on test_01** — the
  convection peer exports five flow-typed port vars, none declared
  as the species-flow pair.  This is the §32 var↔mechanism
  pairing gap surfacing as designed (empty `A_diff`/`S` extents
  still bind the port type-level).  Resolution: transport-side
  species-flow export (needs `cac`'s upwind-`c` gather — §32
  pairing territory), or the §32 resolver itself.
- **`h` needs value cells on species-bearing models** —
  `[N,S]` instantiation data; empty-S models (test_01) need none.
- Mechanical note: assignment `sequence` matches equation **IRIs**,
  not dict keys — `E_61`→`#E_dHdt`, `E_62`→`#E_akp`,
  `E_66`→`#E_dEtotdt`.  Unknown IRIs drop the whole sequence field
  silently (other selection fields still apply) — verify `closed`
  after every assignment PUT.

## 52. Seed inventory audit — surfaces are volumes, environment is the reservoir, seed carries machinery only — RULED (2026-11-25)

The §32 union-index removal surfaced a meta-question: seeded vocabulary
arrives silently — the `A_mass`/`A_energy` unions were minted by
`_seed_arc_sub_indices` at load, never through an editor, which is why
nobody noticed them for weeks.  The whole seed inventory was audited;
the rulings below are recorded in design-principles §17.

### Token rulings

- **`token_mass` stays** — family anchor for the mechanism groupings
  (`mass_transport` declares the family; grain resolves by ancestry)
  *and* the legitimate bulk grain (`V_57`/`V_68`/`V_109` carry it).
  Species (`component_mass`) is the default authoring grain, not the
  only one — grain remains a model-objective choice (§5).
- **`token_charge` stays** — parked, not dead: electrochemistry will
  need it (migration/diffusion in electrolyte, Nernst-Planck), plus a
  `charge_transport` grouping when that lands.

### Surfaces are volumes — the phase-boundary pattern

User-ruled: **a surface is an abstraction; we always deal with
volumes.**  No `surface` etype, no `surface_reaction_host`:

- kinetic wall (no adsorbed inventory) → `point` + `reaction_host`
- thin film with coverage θ / adsorbed state → `lumped` + `reaction_host`
- **phase interface = two point volumes**, one per phase — each
  carries its phase's interfacial state, the jump relation
  (equilibrium: equal chemical potentials; or kinetic transfer rate)
  is an equation over the pair, and diffusion *to* the interface gets
  its driving force from the near-interface node.  Standard
  sharp-interface jump-condition topology, no new vocabulary.
- consequence: `environment` never hosts reactions — a reacting wall
  is a volume between environment and bulk.

### Environment = generic source/sink

`environment` is an unbounded reservoir for tokens of any form —
species, bulk mass, heat, charge, work.  `species_source` is merely
its species leg (gates `promo:speciesAllocation`).  The other legs
arrive with the BC machinery (effort-pinned ports / injected fluxes),
not as N parallel capabilities.  A single reservoir capability
interpreted per token leg is the direction when that machinery lands.

### Seed carries machinery only — `g` moved to the library

- `const_g` removed from `SEED_CONSTANTS` → seed keeps the algebraic
  numerals (`zero`/`one`/`half`); **physical constants are authored
  content** (Boltzmann was already authored in the equation editor).
- `g` re-authored as `library#V_126` — constant-class, value 9.81,
  `universe` network, units `[-2,1,0,0,0,0,0,0]`.
- `E_F_g` re-bound on re-save (`universe!g` resolved self-first);
  `E_fPot`'s bare `g` still hit the ontology's `const_g` — the
  compile-space rule takes the *last* same-network candidate in scope
  order, and pins iterate after self.  rhs qualified to `universe!g`
  (matching `E_F_g`'s style) → re-bound → `const_g` deleted.
- Lesson recorded: **same-label vars across scope do not reliably
  shadow for bare references** — qualify cross-graph references when
  a same-name var exists in a pinned graph.  `SEED_FLOOR` →
  2026-11-25.

### Remaining audit notes (not ruled, parked)

- `e_i`/`e_align`/X/C seeded geometry — machinery-justified (`plan()`
  consumes `e_align` bindings); a geometry-pack split only pays when
  a second geometry exists.
- Scale regimes (`length_*`, `time_*`) — skim-worthiness noted; the
  granularity (`time_nano`/`milli`/`macro`) deserves one pass when
  a non-trivial multi-scale model lands.

## 53. Named component extractions — `x`, `y`, `z` authored — RULED & implemented (2026-11-25)

Prompted by `E_fPot`'s `reduceSum((e_z·r), C)` inline contraction: the
expression language has no `let`/alias mechanism, so an authored
variable *is* the naming mechanism.  Ruling recorded in
design-principles §18 — name contractions that extract a **physical
quantity**; leave basis-vector projections and algebraic fragments
inline.

- `z` (`V_127`, `E_z`), `x` (`V_128`, `E_x`), `y` (`V_129`, `E_y`) —
  `e_i·r` over `C`, `[N]` geometry vars, physical network.
  `E_fPot` → `fmc·g·z`; `Axy`/`Ayz`/`Axz` → `x·y` / `y·z` / `x·z`.
  All consistent; `y` collides with control `V_76` by label —
  `physical!y` qualifiers keep resolution unambiguous.
- Follow-up candidate (same ruling, not yet applied): `v_x`, `v_y`
  velocity components — `kConvX/Y`, `kDiffX/Y`, `kQX/Y` contract
  `e_i·v` inline.

## 54. Darcy flow-law alternatives — quadratic regime beside the linear law — RULED & implemented (2026-11-25)

### Context

The §47 question — which quasi-steady statement determines velocity —
resolved in discussion: pressure-driven networks.  A pressure-given
environment pins nodal pressures; the pressure drop across the network
determines the flow in each branch.  That direction is already the
authored structure — `E_4`/`E_v_str` compute `fmc`/`v_str` from
`kConvX·Δp`; `E_fP` carries the pressure force into `dPdt`.  The open
piece was where the Darcy friction (`fl`, §49) constrains the flow.

### Rulings

- **Darcy-Weisbach is quadratic — an alternative, not a fold-in.**
  `Δp = λ·(L/d)·ρ·v²/2` inverts to
  `v = sign(Δp)·√(|Δp|·d/(λ·L·ρ·½))`, which cannot fold into the
  linear `kConvX·Δp` conductance form.  It lands as *alternative
  equations on the same lhs* — the assignment sequence picks the
  regime (the `E_P_def`/`E_P_int` precedent).  No algebraic loop
  needed: the `sqrt`/`sign`/`abs` repertoire makes the inverted law
  explicit.
- **`fmc` derives consistently** — `fmc = ρ·Ayz·v_darcy` (the same
  quadratic-law velocity), so `fmom = fmc·v_str` and
  `fl = λ·(L/d)·ṁ·v²/2 = |Δp|·ṁ` stay coherent: dissipated power
  equals pressure drop times mass flow.
- **Per-arc mixing → sibling etype** (the `lumped`/`lumped_qss`
  pattern); a uniform whole-model regime is just a sequence swap in
  the BL — nothing changes until the user picks the alternatives.

### Authored records

`E_v_str_darcy` (`V_122`), `E_fmc_darcy` (`V_56`) —
`eqclass_generic`, macroscopic.  `inv(half)` carries the `2` (no
numeric literals).  Consistency: 82 equations, 0 problems; both new
equations check clean.  Author: `scripts/author_darcy_flow_law.py`.

Still open: the `dEmdt = 0` Bernoulli-reading promotion on
`etype_lumped_qss` (the energy-side algebraic path §50 deferred);
`kConvX` could later *derive* from `lam`/`Lp`/`dp` for the linear
regime rather than being authored independently.
