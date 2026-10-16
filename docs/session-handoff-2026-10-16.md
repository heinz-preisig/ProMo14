# Session handoff — 2026-10-16

## What was done

End-to-end Behaviour Linker / modeller / instantiation validation on `test_01`
(`https://w3id.org/promo/model/`): environment — arc — convection_transport — arc — lumped.

### Modeller validation
- Connection gesture confirmed: **left-click source, then right-click target**
  (`useCanvasEvents.onSceneRightClick` → `resolveConnectionAsync` → `pickArcType` → `insertArc`).
- Canvas shows 2 arcs; `/api/ontology/resolve-connection` on physical↔physical
  returns `rule_access` and `rule_physical-same` (token-flow carrier).

### F_conv classification fix (data, in `data/library.trig`)
- `promo:portVariable true → false`, `promo:variableClass "state" → "constant"`.
- Rationale: `F_conv` is the convection **incidence matrix** ([node, arc_conv]-indexed);
  `builder.py` only selects `incidence` binding for constant-class vars with both
  node-like and arc-like indices. It is supplied by topology, never a port.
- Was edited directly in the file because the equation-editor hides the
  determination axis while `portVariable` is true (by design — port is structural),
  making the fix unreachable from the UI.

### R3 port-resolution extensions in `backend/instantiate/builder.py`
User decision: **"the environment is the system boundary"** — boundary entities
export pinned values to their neighbours' ports.

1. **Identity comparability** — a peer var with the *same IRI* as the port is
   always comparable, even when `carriesToken` lists are empty (previously
   `any(_comparable(...))` over empty token sets filtered out env's `P`/`c`).
2. **Per-contact binding for node-indexed ports** — `p_N` at a transport reads a
   value at *each* contact, not one aggregate value. Node-indexed ports now emit
   one `PortBinding` per incident arc (same loop as arc-indexed); only truly
   scalar ports aggregate all contacts.
3. **Port chaining (fixpoint)** — an unbound port may resolve through a peer's
   *bound* port of the same variable, iterated to a fixpoint so chains extend
   through ports that were themselves bound by chaining. Boundary values
   propagate through mediating entities (transport) to downstream capacities.

### Modelling correction (user)
- Lumped's `p` was wrongly a port — chaining it to the same boundary as the
  transport's other contact makes `F^T·p` zero → no flow. `p` is now
  **instantiated** on `etype_lumped` (a value-binding endpoint).
- `c` stays a port: it is the **concentration carried in the mass flow**
  (donor/upstream quantity), correctly read from the boundary.

## Current report state
`/api/instantiate/model?graph=https://w3id.org/promo/model/`:
- **Zero problems.** All assignments closed (environment, transport, lumped).
- `F_conv` → `incidence` binding on both transport and lumped (matrix over `A_conv`).
- `p` on transport bound per contact: `P @ Node_1` (env) on Arc_1, `P @ Node_3`
  (lumped) on Arc_2.
- `c` bound to `c @ Node_1` everywhere (env donor concentration; transport's
  Arc_2 contact and lumped's port both chain to it).
- Schedule: clean levels, no algebraic loops. One `ic` need: `n` on lumped.
- `test_builder.py`: 65 passed.

## Known issue: donor semantics of chained `c`
`c` currently reads the boundary value regardless of flow direction. For
reverse flow the donor should be the lumped's own `c`. Direction-aware donor
selection would consume the §15 reference direction per arc contact — **open
design question, not implemented**.

## Remaining validation checklist
- Species gesture gate: allocation/reaction/permeable gesture on an incapable
  node → expect 422, graph untouched.
- Instantiation UI: value cells + t=0 solve (incl. supplying the `n` IC).
- `remoteCatalogue` bug: `branch` → domain IRI map iterates all domain records
  sharing a branch; `"physical"` resolves to `domain_properties` instead of
  top-level `domain_physical` (last match wins). Harmless today; fix pending.
- Hub artefact delete lifecycle: 409 while referenced → 200 after removal.
- `inv` on indexed args still literal-only (5 library equations uncanonicalised);
  stale `root!` qualifiers unresolved — open decision from 2026-09-27.

## Deferred design questions
- Port direction check (§19 deferred).
- Fix marking on model artefact (ADR-008) — separate from instantiated marking.
- Instantiation artefact persistence for codegen.
- `usesSpecies` / `usesModel` pins.
