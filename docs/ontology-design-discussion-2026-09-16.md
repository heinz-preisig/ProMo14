# Ontology design discussion — 2026-09-16

Classification kinds, token semantics, phase, signal subtokens, implicit equations.

Status: **implemented 2026-09-16** — seeds revised in
`backend/core/graph_store.py`, existing data patched by
`scripts/extend_ontology_hap.py`, `kind` fields surfaced through the
API (`models.py`, `service.py`) and the ontology editor UI
(`types.ts`, `App.tsx`).

## Trigger

The seeded ontology duplicated vocabulary: domains `transport`, `reactions`,
`properties`, `geometry` AND role-axis terms `transport`, `property`,
`conversion`, `observation`, `network-structure`. Two different classification
kinds had been merged into one vocabulary. This discussion separates them.

## Three orthogonal classification kinds

| kind | machinery | classifies | determines |
|------|-----------|------------|------------|
| physics structure | domain tree + connection rules | nodes — where they live, how they connect | connectivity pattern |
| entity abstraction | entity types = structural dimension compositions | nodes — what they are | math structure (ODE/PDE/algebraic, lumped/distributed) |
| graph position | role axis (variable classification) | variables | position in the var/expr bipartite graph |

### Domains + arc rules = physics structure

The capacity | transport | service | information-processing taxonomy is
*emergent* from arc attributes, not a label:

- capacities connect via `carrier=token-flow` arcs (`physical-same`)
- transport mediates token-flow between capacities
- service domains are reachable only via `carrier=reference` arcs (`access`) —
  request-response satellites
- `sensor` / `actuation` / `signal` define the information branch's coupling

Same philosophy as the Behaviour Linker: state is emergent from the subgraph;
"service domain" is emergent from the arc pattern.

### Role axis = var/expr graph position only

Roles name a variable's position in the bipartite graph — identical vocabulary
in every domain:

- `state` — the cycle variable (time-derivative LHS); `differential-state` child
- `secondary-state` — derived image of state (placement under `state` vs
  `derived` still open)
- `derived` — defined by another equation, acyclic
- `port` — unresolved input at the subgraph boundary
- `effort`, `flow` — interface roles tied to token-flow arc semantics
  (effort = equality condition, flow = conservation condition)
- `parameter` / `constant`, `frame`

Dropped domain echoes: `transport` (renamed `flow`), `property`, `conversion`,
`observation`, `network-structure`. Rationale: a variable's domain membership is
carried by its defining equation's domain; role is subgraph-relative — T is
`derived` in the properties subgraph, a `port` in the capacity subgraph. A
domain-echo class freezes one subgraph's perspective onto the variable globally.

The information role axis (`state, input, output, constant, parameter`) was
already clean — all graph positions.

## Phase = content dimension, not structural

Pseudo-phases (averaged-mixture models) show phase is not a matter taxonomy —
it is a *constitutive selector*: "which property model serves this node."

- Dimension records get a `kind` attribute: `structural` | `content`.
- Structural dims (time, length): mandatory in entity-type composition.
- Content dims (phase): never compose entity types; bound per model-node
  instance (`hasPhase`); consumed by the `properties` domain for constitutive
  routing via access-arc wiring.
- Seed vocabulary: `phase { solid, fluid { liquid, gas }, pseudo { … } }` —
  hierarchical, user-extensible.
- Avoids behaviour-equivalent entity duplication: one `lumped capacity` entity
  type covers all phases; phase-specific equations live in per-phase property
  networks in the service domain (where the difference is real).
- Phase boundaries are still `physical-same` token-flow arcs — continuity is
  global, phase never enters rule matching. Multiphase region = one capacity
  per phase + phase intrafaces. Single-node multiphase would need a phase
  index — deferred.

## Token kinds: conserved vs reference

The original definition "what lives in a domain" holds, but the mode of living
differs:

- **Conserved** (mass, energy, momentum, charge, component_mass): accumulate in
  capacities (state = amount of token), transferred by token-flow arcs, appear
  in balances with signs (`F·fx`).
- **Reference** (signal): not accumulated, not conserved — circulates as
  *access to a variable* (its value/reference exposed via a port). Reading
  never depletes; no balance.

Signal = the currency of ALL reference-carrier arcs:

- `sensor` (phys→info): a physical node exposes x, y to an observer
- `actuation` (info→phys): a controller exposes its output to the transport law
- `access` (phys→phys): request-response = a pair of access arcs
- `signal` (info→info): output of one function = input of the next

"Signal" is a control-flavoured name for the general mechanism "variable
access"; the four rules are the direction×scope combinations of that one
mechanism.

Proposal: token records get a `kind` attribute: `conserved` | `reference` —
mirrors `carrier` on rules; enables checker validation (token-flow arcs carry
only conserved tokens; reference arcs only reference tokens).

### Signal token binding — RESOLVED

`signal` was bound to `transport` only within physical — too narrow:
control observes x (macroscopic) and y (properties); access arcs need
it on service domains. **Decision:** `signal` is bound to
`domain_root` — inherited by every branch (supersedes the interim
physical-root + information binding; see decision 4 below). Any
physical node can expose variables; the information branch processes
them.

## Signal subtokens

The token hierarchy (`promo:parent`, same mechanism as `component_mass < mass`)
allows signal refinement. Seeded minimally:

```
signal { observation, manipulation }
```

- `sensor` carries `signal.observation`; `actuation` carries
  `signal.manipulation` — rule semantics become token-enforceable once token
  matching is implemented.
- Token matching should be ancestor-aware (same as domain matching): a rule
  carrying `signal` accepts any subtoken; a rule carrying `signal.observation`
  requires that subtoken specifically.
- Naming: observation/manipulation (function relative to the plant) over
  input/output (viewpoint-relative, already role terms on the information
  axis).
- Control-internal refinement deliberately deferred: controller-state,
  state-estimate, control-error, setpoint, feedforward — depends on which
  control structures are canonically supported (error-feedback vs
  state-feedback vs observer-based). Adding subtokens later is additive,
  ADR-006-safe.

## Canonical computation pattern

The block diagram in words — reference semantics for the role axis:

```
x  :: state               y  :: secondary state
fx :: flow                rx :: reaction rate
dx :: differential state (accumulation)

x  := ∫ dx dt              given initial state
y  := g(x, y)              state-variable transformation — may be implicit
fx := transport-law(effort ∈ y, y)
rx := reaction-law(y)
dx := F · fx + rx          F = incidence matrix of the model graph
```

- Loop: `x → y → (fx, rx) → dx → ∫ → x` — one cycle, closed by integration;
  everything else is the function DAG. Model = state holders + one DAG.
- `F` is the model topology projected into the equation — comes from the
  Modeller's flat graph at codegen, NOT a variable role (this is what
  `network-structure` was groping for).
- Control wraps the loop: `sensor` arcs read x, y; `actuation` writes into the
  transport law (valve coefficient, manipulated effort).

## Implicit equations — explicit-first rule

- The lower-triangular bipartite graph is built from explicit definitions only.
- An implicit equation `g(x, y) = 0` may only be authored *after* the
  solve-for variable already exists in the graph; the editor searches the
  graph for the variable and defines it as a **root problem** solved
  separately.
- Root problem = a definition kind, not a graph cycle:
  `y ← root-problem(g, inputs)` is acyclic and orderable; iteration is
  encapsulated inside the node. The "only one cycle" rule stays absolute —
  the sole cycle is the integration loop.
- The explicit-first rule anchors the unknown unambiguously and makes implicit
  forms *alternative definitions* — consistent with multiple equation
  definitions + BL selection (e.g. ideal law vs cubic EOS).
- Consequences: equation editor needs a "solve g(…) = 0 for y" construct +
  pre-existence validation; BL treats root problems as ordinary resolution
  options; codegen maps them to iterative solver blocks.

## Genericity note

The framework is generic — `physical`/`information` are seed content, not
schema. The real abstraction is carrier semantics + token kinds; branch names
are labels. The `branch` attribute on domains must stay a display/grouping
label, never a semantic switch.

## Decisions taken at implementation

1. Signal token domain binding: **`domain_root`** (inherited by every
   branch). Supersedes the earlier physical-root + information binding
   — the root domain is the global scope.
2. `secondary-state` placement: **child of `derived`** — it is an
   acyclically computed image of the state, not part of the
   integration cycle.
3. Control-internal signal taxonomy (controller-state, state-estimate,
   control-error, setpoint, feedforward): **deferred by design** —
   depends on which control structures are canonically supported.
   Adding subtokens later is additive, ADR-006-safe.
4. **Root domain + binding scope semantics** (added same day, UI
   work): the domain tree has an explicit `domain_root` above both
   branches. A scale dimension's `hasDomain` binding defines the
   subtree where its values apply: bound to root = global, bound to a
   branch = inherited down that branch, bound to a subdomain = that
   subtree only (not usable for entity-type composition, which is
   branch-scoped). `time` is bound to root (dynamic systems are
   global); `length` stays on `physical`. Information entity types
   carry no scale values — `temporal_type` only. The entity-type
   editor enforces this by filtering the scale-value list to
   structural dimensions whose bound domain is an ancestor-or-self of
   the entity type's branch root.

## Implemented

- `graph_store.py`: role terms = graph positions only; token `kind`
  (conserved|reference); signal subtokens observation/manipulation;
  `domain_root` above both branches; signal bound to root; `time`
  bound to root (global), `length` to physical; dimension `kind`
  (structural|content); phase content dimension
  {solid, fluid{liquid,gas}, pseudo}; sensor→observation,
  actuation→manipulation sharedTokens; information entity types carry
  no scale values.
- `extend_ontology_hap.py`: removes domain-echo role terms, patches
  token/dimension kinds, adds phase dimension, creates `domain_root`
  and reparents both branches, rebinds `scale_time` to root, moves
  signal to root, strips physical scale values from information
  entity types, rewires rule sharedTokens.
- `models.py` / `service.py` / `types.ts` / `App.tsx`: `kind` fields
  on tokens and scale dimensions, with editor dropdowns.
- `hap-example-mapping.md`: role vocabulary updated; `network`
  eliminated (topology at codegen).
