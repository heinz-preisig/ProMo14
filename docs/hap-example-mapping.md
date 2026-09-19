# HAP Example — Old → New Structural Mapping

Working document: first-pass proposal for re-expressing the
`processes_001_HAP` equation system under the ProMo14 modelling
approach (transport system = event-dynamic distributed **node**; arcs =
intraface continuity only; `>>>` links = ports).

Source material:
`~/1_Gits/CAM/Ontology_Repository/processes_001_HAP/`
- `equations_global_ID_to_internal.json` — 101 equations, each with
  `lhs`, `rhs` (internal math language), `network`
- `equations_just_list_internal_format.txt` — same, readable form
- `variable_assignment_to_entity_object.json` — **the old BL output**:
  per entity object: `var_eq_forest` (computation sequence),
  `init_vars` / `input_vars` / `output_vars`, `index_set`
- `variables_{root,physical,macroscopic,reactions}.csv` — variable
  labels, types, units (8-exponent SI + QUDT IRI), docs
- `LaTeX/main.pdf` — write-up

## 1. Equation pool by network

| Network | Count | Content |
|---------|-------|---------|
| `root` | 6 | Frame + constants: `zero`, `one`, `oneHalf`, `to`, `te`, `t_interval` — all `Instantiate` |
| `physical` | 8 | Fundamental thermo: `V = r_x.r_y.r_z`, `p = ParDiff(U,V)`, `T = ParDiff(U,S)`, `R`, `cp`, `rho`, `Axy/Axz/Ayz` |
| `macroscopic` | 76 | Capacity + transport physics: fluxes (`fnc`, `fnd`, `fq`, `fw`), transport coefficients (`kdA`, `kcA`, `kqA`, `kdAFick`, `rhoA`, `hA`), balances (`dH`, `an`), state integrals (`H`, `n`), electrical, measurement norming |
| `reactions` | 7 | Kinetics: `K = Ko.exp(-Ea/RT)`, `probability`, `np` production rates |
| `macroscopic >>> reactions` | 3 | Projections out: `_c`, `_x`, `_T` |
| `reactions >>> macroscopic` | 1 | Projection back: `_np` |

## 2. Old entity objects → new placement

| Old entity object | Old kind | New placement |
|---|---|---|
| `macroscopic.node.mass\|constant\|infinity.massSource` | node | Capacity node, constant behaviour (mass reservoir / environment) |
| `macroscopic.node.mass\|dynamic\|lumped.dynamicMass` | node | Capacity node, dynamic lumped |
| `macroscopic.node.mass\|dynamic\|lumped.dynamicReactiveLump` | node | Capacity node, dynamic lumped + reaction coupling |
| `macroscopic.node.energy_mass\|dynamic\|lumped.dynamicMassEnergy` | node | Capacity node (empty assignment in old data) |
| `macroscopic.arc.mass\|convection\|lumped.convectiveMassFlow` | **arc** | **Transport-system node** (event-dynamic distributed) |
| `macroscopic.arc.mass\|diffusion\|lumped.diffusionalMassTransfer` | **arc** | **Transport-system node** |
| `macroscopic.arc.mass\|convection\|lumped.controlledMassFlow` | **arc** | **Transport-system node** (with signal input port) |
| `control.node.signal\|event\|AE.pControl` | node | Event-dynamic node, information branch |
| `control.arc.signal\|link\|unidirectional.signal` | arc | Signal arc — stays an arc (passes signal, no computation) |
| `macroscopic >>> reactions (c/x/T)` | pseudo | **Ports**: `reactions` domain's `c`, `x`, `T` bound to `macroscopic` counterparts |
| `reactions >>> macroscopic (np)` | pseudo | **Port**: `np` production rate flows back into macroscopic balance |

## 3. The essential change: transport equations move

Old: convective/diffusive flux equations lived **on the arc**
(`fnc_x = fV . c_AS`, `fnd_x = kdA_x . (Ayz.F) *N chemPot`, ...).

New: those equations live on the **transport-system node**. The arc
between capacity node and transport node only asserts continuity
(intraface): the flow variable is *the same variable* on both sides —
no equation, just identity.

Consequence for the balance equations: `dH = aHnc_x + aHnd_x + ... +
aq_* + aw` and `an = anc_x + and_x + V.np` stay on the capacity node,
but the `aH*`/`an*` terms (old `F *A` arc→node aggregations) become
references to the transport nodes' output flow variables via ports.

## 4. Old operators → new index machinery

| Old operator | Meaning | New approach |
|---|---|---|
| `I_NA * N x` | inject node-indexed `x` onto arc index set | index-source projection (node→arc) — ontological index, resolved at authoring |
| `F * A x` | aggregate arc flow into node balance | arc→node projection — becomes port reference to transport node output |
| `F * N x` | arc-indexed → node-indexed effort/flow pair | same projection machinery |
| `* S x` | species-index expansion | token/species index source |
| `>>> net` equations | cross-network projection | **ports** — no equation; binding declared in assignment artefact |
| `Instantiate(x, value)` | constant/initial value | `Instantiate(proto)` — instance declaration (ADR-008); the value binds at the instantiation stage, universal constants carry `promo:value` |
| `Integral(f :: t in [to,te])` | state integration | unchanged — marks state variable |

## 5. Old variable types → role axis

Old `type` column maps onto the new multi-axis classification
(`role` axis + others).  Updated 2026-09-16: the role axis names
var/expr **graph positions** only — domain echoes removed (see
`ontology-design-discussion-2026-09-16.md`).

| Old type | New classification |
|---|---|
| `state` | role=state (emergent in BL — tagged as hint) |
| `secondaryState` | role=secondary-state (child of `derived`) |
| `diffState` | role=differential-state (child of `state`) |
| `effort` | role=effort |
| `transport` | role=flow (24 vars — the fluxes/coefficients) |
| `internalTransport` | role=flow |
| `properties` | role=derived — computed in the `properties` service subgraph; a `port` where the capacity consumes it |
| `conversion` | role=derived — reaction rates computed in the `reactions` service subgraph |
| `observation` | role=port — variable exposed on a `sensor` arc |
| `frame` | role=frame (time, position) |
| `network` | **eliminated** — `F`, `S_*`, `I_*`, `A_*` are model topology projected into equations at codegen, not variables |
| `constant` | role=constant |

## 6. What the old assignment artefact tells us

`variable_assignment_to_entity_object.json` is a worked example of the
BL output contract:

- `var_eq_forest` ≈ `promo:hasEquationSequence` (ordered computation)
- `init_vars` ≈ variables needing `Instantiate` (constants/ICs)
- `input_vars` ≈ `promo:hasPortVariable` / externals
- `output_vars` ≈ entity outputs (what arcs/ports expose)
- `index_set` ≈ the entity's index source (`N_dyna`, `A_conv`, ...)

The `dynamicReactiveLump` (15 init, 6 in, 4 out, 4 forests) is the
richest example — good BL test case.

## 7. Coverage check: seed ontology vs. HAP needs

Seed contents (`graph_store.seed_default_ontology`):

- **Domains:** `root` (global scope) → `physical`, `information`
  (user extends)
- **Tokens:** energy, mass, momentum, charge, entropy, component_mass
  (kind=conserved, physical); signal {observation, manipulation}
  (kind=reference, bound to `root` — inherited by every branch)
- **Role axis:** physical {state{differential-state}, derived
  {secondary-state}, effort, flow, port, frame, constant, parameter};
  information {state, input, output, constant, parameter}
- **Dimensions:** structural — time {molecular, nano, milli, macro} ×
  {constant, dynamic, event-dynamic} (bound to `root` — global);
  length {infinitesimal{point, finite}, microscopic{uniform,
  distributed}, macroscopic{uniform, distributed}, infinite{uniform}}
  (bound to `physical`).  Content — phase {solid, fluid{liquid, gas},
  pseudo} (bound to `physical`; bound per node instance, consumed by
  the properties domain)
- **Entity types:** environment, lumped, distributed, point,
  transport_system, info_constant, info_dynamic, info_event
- **Rules:** physical-same (bidir, token-flow), access (phys→phys
  reference), sensor (phys→info, carries observation), actuation
  (info→phys, carries manipulation), signal (info→info)
- **Indices:** species (→ component_mass token), node, arc
- **Equation classes:** generic, instantiate, balance, empirical,
  user_function

### HAP requirements → coverage

| HAP need | Seed coverage | Action |
|---|---|---|
| Domains `macroscopic`, `reactions`, `control` | roots only | **Create subdomains** in ontology editor; assign tokens (inheritance is additive) |
| Entity types: massSource, dynamicMass, dynamicReactiveLump | `environment`, `lumped` | covered |
| Old arc entities (convective/diffusional/controlled mass flow) | `transport_system` | covered — the new node kind exists |
| `pControl` event node | `info_event` | covered |
| Reactions entity | `point` (event-dynamic/infinitesimal) | covered |
| Signal link | `signal` rule + `info_*` types | covered |
| Old var types: state, effort, transport, frame, constant | role terms exist (transport → `flow`) | covered |
| `secondaryState`, `diffState` | `secondary-state` < `derived`, `differential-state` < `state` | covered |
| `properties`, `conversion`, `observation`, `network` | `derived`, `port`; `network` eliminated (topology at codegen) | covered — no domain-echo terms |
| Indices N, A, S | node, arc, species | covered |
| Reaction index `q` | — | **Add index** with `conversion` source kind |
| `Instantiate`, `Integral` equations | `instantiate`, `balance` classes | covered |

**Verdict:** structurally the seed covers HAP. The ontology work is
small and entirely in the editor: ~3 subdomains, 1 index. The role
vocabulary is now graph-position only — no HAP-specific terms needed.

## 8. Open questions for review

1. **Transport node granularity** — RESOLVED (2026-09-15): separate
   transport-system nodes per mechanism. Mechanisms are physically
   distinct: mass diffusion, heat diffusion, radiation, volumetric
   (convective) flow; controlled flow maps into convective; forced and
   natural convection are mostly separate.

   Combined transport systems: when mechanisms are independent but
   co-located, use **parallel transport nodes** on the same connection
   (each exports its own flow; the capacity balance sums them). When
   the physics genuinely couples (Soret/Dufour, heat–mass coupling —
   one mechanism's equations reference the other's internals), the
   coupled equations must live in **one node**: the shared variables
   are not at the port interface, so the scope can't be split.
2. **`>>>` elimination** — RESOLVED (2026-09-15): replaced by the two
   arc concepts, which are distinct:

   - **Continuity arcs** (physical intraface): effort equality + flow
     conservation between connected physical nodes.
   - **Accessibility arcs**: **uni-directional** variable visibility —
     a variable in one node is accessible to another node (e.g. `T` in
     a lumped capacity read by an information-processing node; the
     control output read back). Information systems use these, not the
     continuity arcs of physics.

   The variable lives in exactly one node; no copy, no projection
   equation. The **port** is the equation-level declaration ("this
   comes from across an arc"); BL treats it as an external endpoint
   and the modeller binds it along the arc.

   For `reactions` (resolved 2026-09-15): the reaction domain behaves
   like an **information-processing domain** — physical content,
   information-style connectivity. It reads `c`, `x`, `T` via
   accessibility arcs, computes the kinetics, and exports `np` via an
   accessibility arc; the capacity's species balance consumes `np` as
   a source term. No continuity arc — nothing crosses a boundary, the
   reaction generates within the capacity. It stays on the physical
   branch because its variables are physical quantities (tokens,
   units); the branch says what variables *are*, the arc type says how
   the node *connects*. Consequence: accessibility arcs must be
   permitted between physical domains — `physical-cross` covers them,
   or accessibility becomes its own rule kind usable across branches
   (physical→physical for reactions, physical→information for sensors,
   information→physical for actuators).

   **Connectivity patterns (2026-09-15):** the information-flow shape
   distinguishes service domains from control. A *service* domain is
   request-response: the host sends state-dependent information and
   gets the result back to itself — both arcs connect the same pair
   of nodes (satellite of one host). *Control* is routed: the input
   comes from one place (the measured capacity's `T`) and the output
   goes to a different place (the transport law). The controller is
   thus the **transport system of the information branch** — a
   mediator between two endpoints, like physical transport between
   two capacities, but on accessibility arcs.

   Resulting taxonomy: **capacity** (state, balances; continuity
   arcs) · **transport** (flows between two capacities; continuity
   arcs) · **service** (satellite of one host, request-response;
   accessibility arcs — reactions, properties, geometry-as-model) ·
   **information processing** (signals routed between a source and a
   different destination; accessibility arcs — control).
3. **Selection matrices** (`S_Ip`, `S_Iq`, `F_NI_*`, `I_NA`, `A_Npq`) —
   RESOLVED (2026-09-15): **eliminated**. They belonged to the old
   *interface* mechanism — the special arcs that transferred
   information between physical and information systems. That concept
   is replaced by accessibility arcs + ports, where the routing is the
   arc binding itself; there is nothing for the matrices to do.
   Caveat: if `S_Iq` carried stoichiometric content (species×reaction
   coefficients), that is chemistry data, not routing — it then lives
   as parameters inside the `reactions` domain's kinetics.
4. **`physical` network** — RESOLVED (2026-09-15): it is a **service
   domain** (same pattern as `reactions`): reads the host's
   fundamental state (`U`, `S`, `V`, `n`) via accessibility arcs,
   computes equation-of-state and property relations (`p`, `T` via
   `ParDiff`, `cp`, `rho`, `h`), exports them back to the host.
   Separate domain, sibling of `macroscopic` — not folded in.
   Named `properties` (2026-09-15). The `property` role term still
   classifies the variables — axis classifies, domain hosts.

   **Domain structure decided (2026-09-15):** `geometry` is also a
   service domain — with it segregated, ALL secondary-variable
   computation lives in service domains behind access arcs;
   capacities keep only primary state + balances. `transport` is a
   domain hosting the transport nodes (`massFlow`, `heatFlow`,
   `controlledMassFlow`) — flat, since every `physical` subdomain
   inherits all root tokens anyway (additive inheritance makes
   per-mechanism token scoping moot under the current root).
   Service is a modelling pattern, not schema — nothing is
   hard-wired. Resulting tree:

       root                global scope: signal token, time scale
       ├── physical
       │   ├── macroscopic     capacity: mass, component_mass, energy
       │   ├── transport       transport nodes (flat)
       │   ├── reactions       service
       │   ├── properties      service
       │   └── geometry        service
       └── information
           └── control         pControl: signal
5. **Control/signal branch** — mechanically RESOLVED (2026-09-15):
   the seeded `signal` rule is unconstrained + unidirectional, so it
   covers every accessibility-arc case (physical→information sensor,
   information→physical actuation, physical→physical service
   coupling). Naming RESOLVED (2026-09-15): `signal` stays the
   information-side rule; a new rule type `access` covers
   physical→physical service couplings — same attributes
   (unidirectional, reference) but domain-constrained to
   `physical`→`physical`, so the resolver prefers it over `signal`
   for those pairs (constrained rules sort first).

   **Framing (2026-09-15):** service domains fit the functional
   paradigm — the secondary-state, observation, reaction-rate and
   effort-variable calculations form ONE acyclic, lower-triangular
   network of functions. Access/signal arcs are data-flow edges of
   that network (same mechanism: unidirectional + reference; the
   branch of the endpoints is data, not arc semantics). There is no
   call/return — a service's outputs are referenced by consumers via
   a second arc. Acyclicity of the reference subgraph is the
   BL-checkable constraint (the computation sequence); capacities
   hold the only cyclic part — state feeding back through
   integration. Model = state holders + one function DAG.

   **Final rule set (2026-09-15):** reference arcs are a complete
   2×2 over branch pairs — `access` (physical→physical, service
   couplings), `sensor` (physical→information, measurement),
   `actuation` (information→physical, loop closure; may be narrowed
   to →transport), `signal` (information→information). All
   unidirectional + reference; scope same|cross follows the branch
   pair. The `signal` token lives on `domain_root` — inherited by
   every branch: any physical node can expose variables
   (sensor/actuation/access) and the information branch processes
   them (updated 2026-09-16: was information branch + transport). `physical-same` (bi, token-flow, scope=same)
   covers all intra-physical continuity including different
   subdomains (liquid–gas). `physical-cross` was retired 2026-09-15:
   token-flow + scope=cross can never apply (cross-branch pairs share
   no tokens), and its original different-physical-domains case is
   scope=same under the ancestor semantics.

   **Design tension → resolution direction (2026-09-15):** naming arc
   kinds in the ontology freezes vocabulary that downstream tools
   then depend on — against the flexibility principle. Resolution:
   **bake the semantics into the connection rules** — arcs are
   associated with rules, so the rule *is* the arc-type definition.
   A rule carries constraint (domain restrictions + `scope` =
   same|cross|any) and semantics (`direction` = uni|bi, `carrier` =
   token-flow|reference). An arc references its rule; tools read
   attributes, never names. Frozen core = three small enums; rule
   names (`physical-same`, `signal`, `access`, ...) stay
   user-extensible seed vocabulary. Requires moving the same/cross
   logic in `resolve_connection` off the rule_type name onto the
   `scope` attribute.
