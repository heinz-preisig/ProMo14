# ProMo — Concepts & Architecture

**Status:** living document — started 2026-10-17; **realigned to rulings
through 2026-11-12** (edit rules: `docs/README.md` tier map). Written while
the suite is under construction; sections are updated as concepts land, not
frozen.

**Purpose.** This is the conceptual layer of the documentation. It states
what ProMo is for, the philosophy behind it, and the architecture that
follows — independent of any tool's UI or implementation details. It is the
source from which (a) user guidance material and (b) a publication are
drawn.

- Implementation contracts, endpoints, and module seams → `docs/suite-overview.md`
- Design decisions as they were made → `docs/ADR-*.md`, `docs/behaviour-linker-design-discussion.md`
- Per-tool state → `docs/<tool>-overview.md` / `docs/<tool>-status.md`

Sections marked *(planned)* describe committed design intent not yet
implemented; marked *(under construction)* they are partially built.

---

## 1. Philosophy

### 1.1 Separating engineering from science

ProMo's primary target is **controlled physical systems** — plants and
their control/information layer. It is not a digital-twin tool in the
usual sense, and the architecture is not restricted to physical models:
the ontology has an explicit *information* branch (signals, discrete
event-dynamic systems), and nothing in the artefact/binding model is
physics-specific. Physics is the driving use case, not a hard bound.

Its premise is that two different kinds of knowledge get conflated in
conventional modelling environments:

- **Science** — conservation principles, tokens, mechanisms, constitutive
  relations, species schemes. This is generic: it does not know the plant,
  the topology, or the numbers.
- **Engineering** — the topology of *this* system, the placements, the
  parameter values, the boundary conditions. This is specific: it says
  nothing about physics in general.

Conventional tools store the conflation as a monolithic model file:
equations, topology, parameter values, and solver hints in one artefact.
Reusing "a model" means copying it; changing the physics means editing
someone's engineering; the same mathematical object cannot serve two
targets.

ProMo keeps these apart as **separate artefacts** joined by explicit
binding. Every architectural decision below is a consequence of this one
separation.

### 1.2 One data model — models as building blocks

All artefacts are RDF knowledge graphs under the same vocabulary, and all
models are built on the same data model. A consequence: a finished model is
indistinguishable in kind from an entity — it can be reused as a building
block in a later model (a *composite*), and the mechanism for reuse is
recursion, not export/import.

### 1.3 Content is user-authored, never invented

Equations, topologies, schemes, and values are user content. The tools
parse, check, link, assemble, schedule, and emit code — they never invent
physics. When a need arises that the framework does not express, the
framework is extended by a design decision (an artefact type, a predicate,
a capability), never patched around inside an engine.

### 1.4 Everything inspectable

All artefacts are RDF: addressable (IRIs), diffable, versionable, queryable,
and mappable to external vocabularies (QUDT for units/quantities). There is
no private binary state. What the machine knows about a model is, by
construction, what a user can inspect.

---

## 2. Objectives

What the separation buys — the criteria the architecture must satisfy:

- **Reproducibility** — a model pins its inputs (`promo:usesOntology`,
  `promo:usesSpecies`, …) to versioned artefacts. Re-running instantiation
  is deterministic.
- **Reusability** — science artefacts (equations, schemes) apply to many
  engineerings; engineered models compose into larger ones.
- **Retargetability** — symbolic, checked equations emit to multiple
  numerical backends (Python, Julia, MATLAB — all three emitted and
  verified executing; amended 2026-11-10) and to documentation.
- **Honest algebra** — no numeric literals, units and index structures
  checked at authoring time, checked output trusted downstream.
- **Teachability** — the artefact boundaries are the concepts a user must
  learn; problems the engines report are expressed in that same vocabulary.
- **Extensibility at the data layer** — new physics = new ontology content
  + user equations; new target = a new emitter. The pipeline does not
  change.

---

## 3. The artefact model

The central construct. An *artefact* is a named RDF graph with a type,
an owner tool, and a place in the pipeline. Artefacts reference each other
by pinned IRI links.

> **The ownership rule:** the artefact owns *what exists* and *what can
> happen*; the model owns *where it happens* and *what it means here*;
> instantiation owns *what it is worth*.

| Artefact | Owned by | Contains | Answers |
|---|---|---|---|
| **Ontology** | Ontology Editor | vocabulary: entity types, domains, tokens, indices, classification axes, scales, connection rules, capabilities, graphical symbols | What exists? What may connect to what? |
| **Var/expr graph** | Equation Editor | variables + equations as a checked bipartite graph | What relations are available? |
| **Species scheme** | Species app | components, allocations, reactions — *what can happen* chemically | Which species exist, where they can live, what reactions are possible |
| **Behaviour assignments** | Behaviour Linker | selection: which equations describe each entity type's I/O behaviour (+ graphical assignment) | What is an entity's behaviour? |
| **Model** | Modeller | topology: nodes typed by entity type, arcs typed by connection rules; hierarchy/composites; placements; fix markings | Where does it happen? What does it mean here? |
| **Instantiation** | Instantiation app | value bindings: `promo:value`, `promo:ValueCell`/`ValueFill` tables, initial conditions; persisted `promo:Instantiation` plans | What is it worth? |
| **Glasses** *(planned)* | Graphic Object Editor | domain-specific visual skins | How is it drawn? |
| **Empirical model selection** *(planned)* | — | e.g. EOS choice, data-driven submodels | Which empirical closure? |

Two properties of the table matter more than any row:

1. **Each artefact is independently versionable and pinnable.** A model
   records which ontology and species scheme it was built against;
   changing the science creates a new version, not a silent edit.
2. **The seams are contracts, not code.** Each arrow between tools is a
   declared data contract (see `suite-overview.md` §5). Tools can be
   rebuilt, replaced, or added without touching what is stored.

### 3.1 The three-layer binding model

"How a variable gets its value" is deliberately spread over three layers,
each owned by a different artefact:

| Layer | Artefact | Statement |
|---|---|---|
| **Variable class** | ontology / var-expr graph | the *default* regime — `constant`/`parameter` = bound-value slot; `state`/`flow`/… = computed |
| **Fix marking** | model artefact | per-occurrence override — this variable is an input *in this model* |
| **Value binding** | instantiation | the actual numbers (`promo:value`, ValueCell tables) |

Important consequence (settled 2026-10-17): a boundary condition is a
**bound value**, not a constant-class variable. An environment entity pins
`p`, `T` because the boundary must supply values for ports to resolve —
whether those values are temporally constant is a separate, weaker claim.
The structural requirement ("boundary ports must resolve to bound values")
is enforced by the problem reports (`unbound-port`, `unmarked-input`), not
by hardcoding "environment = constant".

### 3.2 Indices are first-class

Sets over which variables and equations are indexed are semantic objects,
not array dimensions:

- **Topological indices** — `N` (nodes), `A` (token-flow arcs): computed
  from the model topology at instantiation.
- **Computed indices** — `S` (species) and `Q` (active reactions):
  computed by a fixpoint over the species scheme and model placements
  (§20; `Q` landed 2026-09-23, amended 2026-11-10).
- **Sub-indices** — e.g. `A_mass`, `A_diff` select members of `A` via the
  transport node's entity type (§16). Membership is resolved at
  instantiation; the checker sees plain indices.

Equations are written **symbolically over indices**; turning index sets
into concrete tensor dimensions is an instantiation concern. This is what
makes one equation serve a 2-node and a 200-node model.

### 3.3 The species scheme — what can happen, kept outside the model

The species artefact is deliberately *not* part of the model. A
`promo:Species` graph declares the chemistry: `promo:Component`s (the
species), `promo:Allocation`s (where each species can reside), and
`promo:Reaction`s (what can happen). The model never copies any of this —
it *references* the scheme through placements:

- `promo:speciesAllocation` — a node declares which allocation it
  realises (a reservoir injects species).
- `promo:hostsReaction` — a node declares which reactions it may host.
- `promo:permeable` — a transport node declares which species it passes.

Whether a placement is legal is governed by **capabilities** —
`promo:capability` links on entity types, inherited through
`promo:parent`: `species_source` (environments), `reaction_host`
(lumped/distributed/point capacities), `species_transport`
(mass-transport mechanisms). Capabilities are ontology content: the rule
"convection transports species" is data on the type hierarchy, editable
and versioned — not a check baked into the Modeller.

The payoff appears at instantiation: species presence is **computed, not
declared**. A monotone fixpoint (reservoir injection → permeable
transport → conditional reactions, spreading bidirectionally) derives
which species exist at each node and arc — that set is what the index
`S` binds to, and which reactions actually *fire* is what `Q` binds to.
Change the scheme or the placements and `S`/`Q` change everywhere they
are used, with no equation edits.

### 3.4 Behaviour assignments — selection, not authoring

The behaviour-linker artefact answers "which of the checked equations
describe *this* entity type?" Its content is a **selection**: for each
entity type, an ordered sequence of equation IRIs drawn from the
var/expr graph, plus structural marks:

- `base_equation` — *the* balance. Its LHS becomes the entity's
  `state_variable` at closure — which is why a stateless entity
  (transport) must declare none (§4.3).
- `instantiated` — variables the entity supplies as bound values rather
  than computing (boundary conditions).
- `ports` — variables resolved against a peer across an arc (§4.2).
- `outputs` — external observation sinks: defined variables nothing inside
  consumes; reachability roots for the closure (§21, added 2026-10-28,
  amended 2026-11-10).
- `closed` — whether every variable the selection consumes is either
  produced inside it or resolved externally (port, bound value); an open
  assignment reports `assignment-open` at instantiation.

The assignment owns no physics. It is a subgraph of the var/expr
bipartite graph picked under user control and validated for consistency —
the same equations can be selected by several entity types, and swapping
one constitutive relation for an alternative definition is an
assignment edit, not an equation edit.

### 3.5 Structure handles — variables that stand for derived structure

Most variables name quantities: mass, pressure, a conductivity. A few
name *structure*: the equation layer's handle on the network the
model will later supply. The node–arc incidence factors are the
canonical case — `F`, `F_diff`, `F_conv`, `F_heat`, … — one per arc
sub-index (§16, §3.2).

An incidence factor is two halves held deliberately in different
artefacts:

- **The record** lives in the var/expr graph — an ordinary variable
  with a fixed index pair `[A_k, N]`, constant class, dimensionless
  units, LaTeX `F`, and **no token declaration** — structure handles
  stay token-neutral by ruling (design-principles §4; amended
  2026-11-10). It exists so equations can
  reference the matrix *symbolically*: `d(m)/dt = F_diff·J_diff +
  F_conv·m_conv` is physics, written before any model exists.
- **The matrix** is instantiation output — `+1` where an arc's
  reference direction enters a node, `−1` where it leaves (§4.1),
  built from the drawn topology. It is never typed and never edited.

The role is recognized by **reserved shape**, not a flag: a
constant-class variable indexed `[node, arc]` *is* an incidence
handle. There is no marker to set and no format to learn — the shape
is the contract, and instantiation binds every variable of that shape
to the matching matrix.

Two consequences follow. First, the factors are **scheme content**:
each exists because its arc sub-index exists, so they are provided
with the mechanism seed rather than authored — every artefact that
uses the ontology sees literally the same `F_*` objects, and a new
mechanism's factor appears automatically. Second, the indirection is
the payoff of separating science from engineering: flip a reference
direction in the Modeller and only signs in the generated matrix
change — equations, assignments, and code templates are untouched.

The same "symbolic handle → derived matrix" pattern will serve the
stoichiometric matrices when reaction-scheme instantiation lands.

### 3.6 Information processing and its physical interfaces

Ruled 2026-11-12 (design-principles §16; discussion §37): control, or
information processing, operates solely on **unidirectional signals**.
Observation and manipulation are earmarked signals identifying interaction
with the physical system, not generic names for every controller input
and output.

- **Observation** reads a physical quantity into a signal, through an
  instrument in real-world systems. States, secondary states and flows
  may all be observed. A flow measurement is a reading, not transport of
  the extensive quantity.
- **Manipulation** acts on a **transport system**, through a transducer
  to the actuator (the “valve”) regulating extensive flow between
  capacities. It does not act directly on capacities.
- **Internal information processing** transforms and transmits signals.
  Each connection is unidirectional; a network of such connections may
  form a feedback loop.

Control signals are normalised and dimensionless. A generic controller
uses signal inputs/outputs; observation/manipulation are model-connection
roles, not permanent classifications of those controller variables. Time
constants and integration coordinates retain their appropriate units.
General information processing remains open (discussion §38).

Token membership serves connectivity, not exponent algebra. The editor
requires no token-vector authoring or token-signature repairs. Units and
indices remain checked. Existing vectors are retained as inactive stored
metadata; the previous implementation is recoverable at Git tag
`archive/token-signature-algebra` (`bcbf22f`). Transport-only actuation is enforced through the ontology-declared
`targetEntityType` constraint, including descendants. Existing controller
membership corrections remain explicit follow-up.

---

## 4. The pipeline

The suite is a sequence of artefact transforms. Each stage consumes
artefacts and produces artefacts; no stage reaches behind another's
contract.

```
Ontology ──┐
           ├─► Var/expr graph ──► Behaviour assignments ──┐
Species ───┤                                              ├─► Model ──► Instantiation ──► Schedule ──► Codegen
           │                                              │                  │  (values)
           └──────────────────────────────────────────────┘                  │
                                                             distributed ──► Meshing ──► lumped model ──┘
```

1. **Authoring** — ontology, equations, species schemes: the science.
2. **Behaviour linking** — selects, per entity type, which checked
   equations describe its I/O behaviour. The var/expr graph is bipartite
   and lower-triangular; linking picks a subgraph per entity.
3. **Modelling** — topology: nodes typed by entity types, arcs typed by
   carrier (`token-flow` | `reference`) with a per-contact reference
   direction; composites for hierarchy/reuse; placements and fix
   markings. (Amended 2026-11-10: arcs declare no token.)
4. **Species allocation** (§20) — monotone fixpoint computes which species
   are present at which topological extent: reservoir injection →
   permeable transport → conditional reactions.
5. **Instantiation** (§19) — binds the model topology to the assigned
   equations: index sets become concrete element sets, symbolic
   references (`incidence`, `constant`, `parameter`, `port`, `local`,
   `fixed`)
   resolve to bound values or matrices, ports resolve across entity
   boundaries. Output: an assembled equation set + a computed report
   (problems, not silent fixes).
6. **Scheduling** — the assembled equations form a DAG of
   (entity-type, equation) blocks; state variables are *sources*
   (integrator outputs), which leaves only genuine algebraic loops —
   detected as Tarjan SCCs and reported. Levels of the condensation DAG
   define the evaluation order.
7. **Meshing** *(planned)* — artefact-to-artefact transform: a distributed
   (PDE) model → a standard lumped model whose nodes are spatial cells.
   Sits after instantiation, before codegen; lumped/event-dynamic systems
   skip it.
8. **Code generation** — symbolic checked trees → target code.
   Agglomerated tensor form for continuous cores; functional
   model-calls-model at composite boundaries and discrete subsystems.

### 4.1 Reference coordinates (§15)

Arcs carry **directions, not tokens**: drawing order is layout, but every
contact between a flow-system entity and a capacity carries a semantic
reference direction (per-contact sign, persisted as
`promo:referenceFrom`/`promo:referenceTo`). Instantiation derives the
global incidence matrix **F** `[N, A]`; equations reference F
symbolically, so flipping an orientation only flips signs at codegen — the
model document stays untouched. (Amended 2026-11-10: the previous
phrasing "arcs carry tokens, not directions" had it backwards — direction
is declared, token is derived.)

**Tokens are implicit, not declared.** An arc's type records only a
carrier category (`token-flow`, `reference`) — the actual token (mass,
energy, signal) is determined by the connected transport node's entity
type, which is what places the arc into a sub-index like `A_mass` or
`A_conv` (§3.2). One source of truth: re-typing the transport node
re-tokens the arc without touching topology. Consequences:

- The token is *derivable*, never stored — tools that show it must
  compute it (incident transport node → sub-index → token). The
  Modeller displays it: `matchedTokens` on the connect gesture and the
  selected-arc panel (landed 2026-10-17).
- **Capacity↔capacity arcs are unphysical** — ruled and enforced
  2026-11-10 (design-principles §14): every token flow between two
  capacities is transport-mediated, including flows to and from the
  environment.  `physical-same` carries `promo:requiresMechanism` —
  `resolve-connection` skips it unless an endpoint entity type
  reaches a token-bearing mechanism grouping (amended 2026-11-10).

### 4.2 Port resolution at boundaries

Entities meet through ports. A port on entity X resolves against a peer
entity that *defines* a comparable variable — the boundary is where
another artefact supplies the value.

**Everything is a system; an arc is a boundary coupling, not a thing.**
Capacities and transports are the same kind of entity distinguished by
temporal regime: a capacity integrates (dynamic); a transport generates
the flow from the efforts at its ends — the constitutive relation lives
there, never on the arc. Transports come in two physics grades (ruled
2026-11-10, design-principles §14): *true physical transport*
(`distributed` + `dynamic`) holds state of its own, and the
*event-dynamic simplification* is a capacity-free, stateless
approximation — no interior, no balance equation (amended 2026-11-10).
The arc index enumerates boundaries/connections, not arc
objects, and a boundary slot *is* the peer's variable — coupling is
sharing, not copying plus a glue equation (the "cut equations" never
exist):

- *Physical* boundary: effort and flow equal at the contact.
- *Information* boundary: the output *is* the connected input —
  identity, not even equality.

**Bound extent follows the boundary.** A port-connected variable on an
event-dynamic entity binds its *contacted* elements — the peers'
elements at each contact (one slot per boundary); on a capacity it
binds own elements. The transport's domain degenerates to its
boundary, so its port variables hold the boundary values only — the
driving drop across a transport is the signed sum over its contacts,
its own `F` row being the sign vector.

Resolution rules (R3 + 2026-10-16 extension):

- Candidates = peer's defined/comparable variables, preferring explicitly
  flagged state.
- An **identical variable IRI is always comparable** — an environment
  instantiating `p` satisfies a `p` port.
- **Port chaining** — an unbound port may bind through a peer's *bound*
  port of the same variable, propagating boundary values through
  mediating entities (lumped's `p`/`c` bound through the transport to the
  environment's pins).

Unresolvable ports are reported (`unbound-port`, `ambiguous-port`) — the
model is incomplete, not silently defaulted.

### 4.3 Worked example: environment → transport → lumped

The running example (validated 2026-10-16) is the smallest model that
exercises every mechanism: two capacity-type nodes joined through a
transport node by two token-flow arcs.

```
environment ──arc──► convection transport ──arc──► lumped capacity
   (boundary)            (stateless)                  (holds state)
```

- **Index sets.** `N = {env, transport, lumped}`, `A = {a1, a2}`,
  `A_conv = {a1, a2}` (both arcs' mechanism is convection, selected by
  the transport node's type). Per-type subsets: `N_env = {env}`,
  `N_lumped = {lumped}`.
- **Bindings.** The incidence variable `F[N, A_conv]` binds the numeric
  incidence matrix *on both entities* — the constant-class `[N, arc]`
  slot is reserved for exactly this (§4.1). The lumped node's state `m`
  binds `local` over `N_lumped`; the transport's conductivity `k` binds
  `parameter`; the environment's `p`, `T` bind `constant` values.
- **Port resolution.** The transport's effort ports bind directly to
  each peer's exported effort per contact. The lumped capacity's `p`/`c`
  ports find no direct peer supply — they resolve by *port chaining*
  through the transport's already-bound ports back to the environment's
  pins. One propagation pass; the `unbound-port` problems are retracted
  on success.
- **Schedule.** The lumped balance's LHS `m` is a *state* → source, not
  a product of the balance. What remains is acyclic in this example:
  constants/ports at level 0, the transport's `J` next, the lumped
  balance (yielding `dm/dt`) last. No `algebraic-loop` problems.
- **Report.** Zero problems: all ports bound, all assignments closed.
  The assembled equation set — `F` numeric, `p`/`T` pinned, `m` marked
  integrator output — is what codegen consumes.

Two observations the example demonstrates, both worth stating explicitly:

- **A stateless entity declares no base equation.** The transport has no
  balance of its own; giving it one would stamp its LHS as a state
  variable and the scheduler would wrongly treat it as integrator
  output. The balance lives on the capacities; transport contributes
  flows.
- **"Environment" is a role, not a special type.** Nothing in the engine
  knows about environments. An entity that defines bound, comparable
  values is a boundary; the same `lumped_capacity` type would work if it
  exported `p`.

---

## 5. Flexibility by consequence

Each row: a decision, and the flexibility it yields. This is the evidence
that the separation works.

| Decision | Consequent flexibility |
|---|---|
| Artefact separation + pinned references | Swap species scheme, ontology version, or value set without editing the model. Same model → different scenario = different instantiation artefact. |
| Equations symbolic over indices; indices bound at instantiation | One authored equation serves any topology size. Species count is data, not code. |
| Incidence F symbolic in equations | Reorient arcs without touching equations; balances `F·J` and efforts `Fᵀ·Δp` are the same symbolic form in every target. |
| Checked = trusted (publish–consume) | Validation happens once at authoring; downstream stages and generated code carry zero checking overhead. |
| Port resolution by comparability, not wiring | Entities recompose; the "environment" is not a special node type, just an entity that defines bound values. |
| Scheduler: states are sources | Correct handling of differential/algebraic structure falls out of the data; algebraic loops are detected and reported, not hidden. |
| Empirical models as artefacts *(planned)* | EOS/kinetic selection is a pinnable input on top of hard physical-fact equations (e.g. an energy function); symbolic differentiation specialises it — physics and empirics never mix in one equation. |
| Emitters own target layout | One canonical value-cell convention (C-order coordinates) → correct MATLAB/Julia/Python arrays; adding a target = one emitter, no model changes. |
| Capabilities as ontology content | Rules like "this entity can host reactions / source species" are data (`promo:capability` on entity types) — inspectable, editable, versioned — not code conditions. |

---

## 6. What this document is for

- **Users** — the concept vocabulary for the guidance layer (Track 2):
  problem reports and per-tool guides reference these sections.
- **Paper** — §1–2 = motivation; §3 = contribution (artefact/binding
  model); §4 = contribution (instantiation as computation); §5 =
  evaluation of flexibility claims against a worked example
  (environment → transport → lumped, with port chaining and F-binding).
- **Us** — the place where each new §N decision gets promoted once it
  settles. Rule of thumb: when a design-discussion section stabilises,
  distil its *invariant* into §3–5 here and leave the reasoning trail in
  the design doc.

## 7. Terminology & notation

Terms that are easy to get wrong because the project (and the field)
overloads them. This list is normative for new documentation.

- **Equation vs expression.** An *expression* is a checked RHS term. An
  *equation* is the pair `variable := expression` — LHS variable plus
  defining expression. Never call a bare expression an equation. (Legacy
  naming: the internal module is `backend/equation`, artefact name
  "var/expr graph" — both tolerated, but prose uses the definition above.)
- **Network vs domain.** *Network* = the var/expr scope tree in which a
  variable/equation lives and which controls label visibility
  (`universe` → `physical` → `macroscopic` → …; also the `control` and
  `information` branches). *Domain* is overloaded in the field: we also
  use it for (a) the same scope tree (`promo:inDomain`, `network` field
  — historical), and (b) *application domain* = plant type / industry
  sector, which is unrelated metadata. Preferred usage going forward:
  **network** for the scope tree, **application domain** for plant
  type; avoid bare "domain" where ambiguity matters. Unresolved: whether
  `promo:inDomain` / the `network` variable field get renamed.
- **Symbol for pressure.** `p` — lowercase, consistently. (`P` appears
  in legacy data; new content uses `p`.)
- **F and I.** `F` = node–arc incidence matrix `[N, A]`; `I` = identity
  matrix. Never write `I[N, A]` for incidence.
- **Incidence factor / structure handle.** `F_*` = the symbolic variable
  standing for one mechanism's slice `[A_k, N]` of the node–arc
  incidence. The *record* is scheme content (seeded); the *matrix* is
  derived at instantiation. Any constant-class variable indexed
  `[node, arc]` is by convention an incidence handle — the shape is
  reserved (§3.5).
- **Variable class names.** The physical-branch axes are `determination`
  {constant, variable} and `function` {state, effort, flow, frame,
  reaction, parameter}; `port`/`derived` are structural facts
  (flag / equation presence), not axis terms.

## 8. Open threads

Tracked here so the document stays honest about what is built vs.
designed:

- Composite/reuse semantics — **landed** (§22 designed 2026-10-28; §33
  copy-vs-reference ruled 2026-11-08): `refersTo` + per-occurrence
  override map on the composite, the artefact's root-composite open
  arcs as the declared interface (strict boundary enforced
  2026-11-10 — only declared ports are connect targets), per-use-site
  instantiation keyed by occurrence path (landed 2026-11-10),
  `reference-cycle` detection. Insert is two-mode: click = editable
  copy, Ctrl+click = referenced read-only occurrence (amended
  2026-11-10).
- Incidence-factor seeding — designed + implemented 2026-11-01 (BL
  doc §25): `F_*` records are floor seeds derived from the arc
  sub-indices (`_seed_incidence_factors`), hand-authored copies are
  stripped by `_migrate_incidence_factors`, and the legacy
  `sign(F_conv * p_mech)` equation was rewritten to the `[A_k, N]`
  contraction. Same day §26 closed the IRI question it exposed:
  instance IRIs are absolute and live under the owning artefact's
  namespace (`{graph}#name` for var/expr content) — the relative
  `promo:X` spellings are rehomed by `_migrate_variable_iris`
  (duplicates consolidated, references and JSON-literal tokens
  rewritten), mints updated, and the variable write path now rejects
  relative IRIs — the deferred same-IRI guard landed there.
- Meshing (distributed-systems-design.md).
- Empirical model selection artefact (energy-function + EOS pattern).
- Instantiation artefact — done 2026-10-17: `promo:Instantiation`
  artefact type; `POST /instantiations` persists the `CodePlan` JSON
  with `generatedFrom` + full pin set, `GET /instantiation-plan` reads
  it back. Pinned replay done too: `GET /code?instantiation=<iri>` and
  `POST /initial?instantiation=<iri>` emit from the persisted plan
  (problem kinds stored as `promo:problems`; var/expr scope comes from
  the artefact's `usesLibrary` pin, `?vars=` overrides).
- Fix marking (ADR-008 layer 2) — engine done 2026-10-17: `promo:fix`
  on `ModelNode` (modeller PUT/GET persists), binds `fixed` (fix wins
  over defining equations); problems `fix-conflict`, `fix-partial`,
  `fixed-unbound`; modeller gesture done too — selected leaf shows a
  "Fix (bound at this node)" checklist fed by
  `GET /entity-variables`. BL admissibility — **landed 2026-10-28**
  (behaviour-linker-design-discussion §21): admissibility is
  positional lower-triangularity maintained by moves (pick / exchange
  / delete / mark-unmark / reorder / pick base), each re-closing the
  subgraph — not a validation pass; a fourth endpoint kind —
  **output** (external sink, reachability root, persisted as
  `promo:hasOutputVariable`) — was added (amended 2026-11-10).
- Track 2 complete at seed level: problem catalogue
  (`docs/problem-catalogue.md`), doc anchors on `ProblemOut`, per-tool
  guide (`docs/what-am-i-authoring.md`), end-to-end example
  (`docs/worked-example.md`), `/docs/` renders HTML with scrolling
  anchors.
- `promo:inDomain` / `network` field naming — see §7.
- Arc-token display — done 2026-10-17: `matchedTokens` on
  `AllowedConnection` (backend `matched_tokens`), shown in the
  connect-gesture arc-type list and the selected-arc panel.
  Capacity↔capacity is no longer a derivation question — §14 (ruled
  2026-11-10) declares such arcs unphysical, and enforcement landed
  the same day via `promo:requiresMechanism` on `physical-same`
  (amended 2026-11-10).
