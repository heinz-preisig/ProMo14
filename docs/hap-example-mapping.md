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
| `Instantiate(x, value)` | constant/initial value | `promo:Instantiate` — unchanged |
| `Integral(f :: t in [to,te])` | state integration | unchanged — marks state variable |

## 5. Old variable types → role axis

Old `type` column maps onto the new multi-axis classification
(`role` axis + others):

| Old type | New classification (proposal) |
|---|---|
| `state` | role=state (emergent in BL — tagged as hint) |
| `secondaryState` | role=state, secondary |
| `diffState` | role=state, differential-form |
| `effort` | role=effort |
| `transport` | role=flow (24 vars — the fluxes/coefficients) |
| `internalTransport` | role=flow, internal |
| `properties` | role=property |
| `conversion` | role=conversion |
| `observation` | role=observation |
| `frame` | role=frame (time, position) |
| `network` | role=network-structure (selection matrices `S_*`, `F_*`, `I_*`, `A_*`) |
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

- **Domains:** `physical`, `information` (roots only — user extends)
- **Tokens:** energy, mass, momentum, charge, entropy, component_mass
  (physical); signal (information)
- **Role axis:** physical {state, effort, transport, frame, constant,
  parameter}; information {state, input, output, constant, parameter}
- **Scales:** time {molecular, nano, milli, macro} × {constant,
  dynamic, event-dynamic}; length {infinitesimal{point, finite},
  microscopic{uniform, distributed}, macroscopic{uniform,
  distributed}, infinite{uniform}}
- **Entity types:** environment, lumped, distributed, point,
  transport_system, info_constant, info_dynamic, info_event
- **Rules:** physical-same, physical-cross (bidir), signal (unidir)
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
| Old var types: state, effort, transport, frame, constant | role terms exist | covered |
| `secondaryState`, `diffState` | — | **Add child terms under `state`** |
| `properties`, `conversion`, `observation`, `network` | — | **Add role terms** (property, conversion, observation, network-structure) |
| Indices N, A, S | node, arc, species | covered |
| Reaction index `q` | — | **Add index** with `conversion` source kind |
| `Instantiate`, `Integral` equations | `instantiate`, `balance` classes | covered |

**Verdict:** structurally the seed covers HAP. The ontology work is
small and entirely in the editor: ~3 subdomains, ~5 role terms, 1
index. No code changes needed.

## 8. Open questions for review

1. **Transport node granularity** — one transport-system node per
   mechanism (convection/diffusion/controlled) as the old arcs suggest,
   or merged? Old structure says: separate.
2. **`>>>` elimination** — confirm ports fully replace the projection
   equations; `reactions` domain then has `c`, `x`, `T` as input ports
   and `np` as output port.
3. **Selection matrices** (`S_Ip`, `S_Iq`, `F_NI_*`, `I_NA`, `A_Npq`) —
   do these survive as network-structure variables, or does the new
   index machinery make them implicit?
4. **`physical` network** — fundamental thermo (`U`, `S`, `V`, `n`,
   `p`, `T`) is a separate domain in old data. Keep as separate domain
   under the physical branch, or fold into `macroscopic`?
5. **Control/signal branch** — `pControl` event node + signal arc:
   first information-branch example; check the signal connection rule
   covers it.
