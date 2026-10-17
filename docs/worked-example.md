# Worked example — environment → transport → lumped, end to end

**Status:** living document — started 2026-10-17 (Track 2). Follows the
smallest model that exercises every pipeline mechanism, validated
2026-10-16 with zero reported problems. Concept references point at
`docs/concepts-and-architecture.md` (CA); problem kinds at
`docs/problem-catalogue.md`.

The model, in one line:

```
environment ──arc──► convection transport ──arc──► lumped capacity
  (boundary)              (stateless)                 (holds state m)
```

A boundary entity pins `p`, `T`; a stateless transport conducts a flow
`J` between them; a lumped capacity accumulates mass `m` and reads its
own boundary values through the transport.

---

## 1. What each artefact contributes

| Artefact | Contribution to this example |
|---|---|
| **Ontology** | entity types `environment`, `convection_transport` (child of `mass_transport`, capability `species_transport`), `lumped_capacity`; index `N`, `A`, sub-index `A_conv` (membership via the transport node's type); token `mass` |
| **Var/expr graph** | port variables `p`, `T`, `m`, `J`, `k`, `F[N,A_conv]` (constant-class — reserved for incidence, CA §4.1); the lumped balance `dm/dt = F·J`; the transport law `J = f(k, Δp)` |
| **Behaviour assignments** | lumped: `base_equation` = the mass balance (LHS `m` becomes the state); transport: **no** base equation — it is stateless (CA §4.3); environment: `instantiated` marks on `p`, `T` |
| **Species scheme** | not used in this example — `S` stays unbound (symbolic) |
| **Model** | the three nodes and two token-flow arcs; the environment's placements |
| **Instantiation** | `promo:value` pins on the environment's `p`, `T`; the conductivity `k`'s value |

## 2. What the modeller sees

- Three typed nodes, two arcs. The arcs carry *no declared token* —
  mass is implicit in the transport node's `convection_transport` type
  (CA §4.1), which is what puts both arcs into `A_conv`.
- The environment is **not** a special node type. It is just an entity
  that defines bound, comparable values — the boundary role is emergent
  (CA §4.3).

## 3. What instantiation computes

`GET /api/instantiate/model?graph=<model>&vars=<var/expr>` produces the
report (not yet a persisted artefact):

- **Index sets** — `N = {env, transport, lumped}`, `A = {a1, a2}`,
  `A_conv = {a1, a2}`; per-type subsets `N_env = {env}`,
  `N_lumped = {lumped}`.
- **Bindings**
  - `F[N, A_conv]` → `incidence`: the numeric node–arc matrix, bound
    *on both* the capacity and the transport.
  - `m` → `local` over `N_lumped` — instance `V_m@lumped_capacity`.
  - `k` → `parameter` — value from the instantiation artefact.
  - `p`, `T` (environment) → `constant` — pre-bound `promo:value`.
- **Port resolution**
  - Transport's effort ports bind directly per contact: each arc end
    sees the adjacent capacity's exported effort.
  - The lumped capacity's `p`/`c` ports have no direct peer supply —
    they resolve by **port chaining**: the transport's already-bound
    port of the same variable carries the environment's pin across.
    The initial `unbound-port` problems are retracted when the chain
    closes.
- **Schedule** — `m` is a *state*: a source, not a product of its own
  balance (the balance yields `dm/dt`). The remaining graph is acyclic:
  bound data at level 0, `J` next, the balance last. No
  `algebraic-loop`.

Report outcome: **zero problems** — all ports bound, both assignments
closed.

## 4. What codegen consumes

The assembled equation set is the hand-off:

- `F` numeric → gather/scatter: `F·J` scatters arc flows into node
  balances; `Fᵀ·p` gathers node efforts into arc differences.
- `p`, `T` pinned at the environment → boundary values in the generated
  RHS.
- `m` marked integrator output → appears in `y`, its balance in
  `dydt`; everything else evaluates in schedule order (states →
  secondary → flows, node-local equations parallelisable within a
  level).

## 5. What would have gone wrong

The same model with mistakes produces exactly the catalogue's kinds:

| Mistake | Problem |
|---|---|
| Node left untyped | [`untyped-node`](problem-catalogue.md#untyped-node) |
| `lumped_capacity` never assigned | [`no-assignment`](problem-catalogue.md#no-assignment) |
| Assignment missing the constitutive eq | [`assignment-open`](problem-catalogue.md#assignment-open) |
| Environment's `p` neither `promo:value` nor `Instantiate`d nor port-flagged | [`unmarked-input`](problem-catalogue.md#unmarked-input) |
| Environment forgets to define `p` at all | [`unbound-port`](problem-catalogue.md#unbound-port) |
| Two comparable candidates across an arc, none flagged | [`ambiguous-port`](problem-catalogue.md#ambiguous-port) |
| `F` declared `state`-class instead of `constant` | `unmarked-input` — a `[N,arc]` variable only takes the incidence matrix when constant-class |
| Transport given a `base_equation` | no problem kind — but `m` misbecomes a state and the schedule misorders |

## 6. Takeaways

- **Boundaries are bound values, not special types.** The environment
  works because it defines `p`/`T` with values — same mechanism
  anywhere on the diagram.
- **The balance lives on capacities.** Transport contributes flows; a
  stateless entity declares no `base_equation`.
- **Chaining propagates boundary values through mediators.** The lumped
  node never "sees" the environment — the transport's bound ports carry
  the values across.
- **Problems are the contract.** Nothing is silently defaulted; each
  report kind names the artefact that must change.
