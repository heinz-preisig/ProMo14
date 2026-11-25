# Design principles — ProMo14

Living — realigned to rulings through 2026-11-24.

Curated record of the global ideas and the deliberate deviations from
mainstream modelling of controlled physical systems.  Each entry states
the principle, its rationale, and where it is encoded so the rationale
survives across sessions and contributors.

Read this first when picking up work on the suite — the ontology and the
test suite carry the enforceable details; this document carries the
*reasoning*.

---

## 1. Semantics lives in the ontology, not in code

Code reads ontology-declared categories — `indexClass`, `tokenKind`,
`capability`, mechanism→token (`promo:token` on grouping entity types),
entity-type ancestry — rather than hardcoding meaning.  When a needed
semantic does not exist, **extend the ontology**; never special-case
code.

*Encoded:* `promo#` vocabulary = types only; instance IRIs under
`{graphIRI}#`.  Ancestry patterns: `core/capabilities.py`.

## 2. Equations are purely symbolic; instantiation is numeric-only

The expression language has **no numeric literals by design** — equations
carry *all* relations; instantiation carries only literal numbers.
Computed values and initial conditions must be `initialise`-class
equations, never expression-valued cells.

*Decision:* user-ruled 2026-10-28 (`docs/value-expression.md` records the
rejection after an implemented-then-reverted attempt).  Do not re-propose.

- **Corollary (ruled 2026-11-24, BL §48): a recorded equation must be
  a true relation.**  `m := dmdt` was runtime-correct only because the
  emitted slot named `dmdt` carries `∫dmdt` — as a flat equation it
  was false and the consistency checker rightly errored.  The honest
  record is `m := Integral(dmdt :: t in [to, t])`; emit interprets a
  `DefInt` over a declared state to the running bound as the
  accumulator slot (`PlanBlock.alias_of`), so the pun lives in
  generated code, never in the artefact.

- **Corollary (ruled 2026-11-24, BL §51): a derivable property may
  still be instantiation data.**  `h := ParDiff(H, n)` is the true
  relation and stays in the library — but a scope that does not
  carry the EOS layer cannot sequence it, so `etype_lumped` takes
  `h` as `instantiated` property data (the `Mm`/`N` pattern).  The
  choice is per-assignment, never per-variable: both the equation
  and the instantiation channel coexist.

## 3. Tokens describe semantic connectivity, not a second equation algebra

Amended 2026-11-12 (discussion §38): token declarations answer which
networks may connect and which physical mechanisms move or are driven by
which quantities. They are not manually coordinated exponent vectors.

| Layer | Declaration | Answers |
|-------|-------------|---------|
| Connection rules | `promo:sharedToken` | What may flow between domains? |
| Mechanism groups | `promo:token` | Which token family does this mechanism move? |
| Mechanism leaves | `promo:drives` (set-valued) | Which effort token drives this mechanism? |
| Variables | `promo:carriesToken` | Which networks license this variable at a connection? |

**Arcs declare no token** — carrier category only. The connected entity
semantics and ontology rules determine what the connection means.
Membership matching uses token ancestry comparability and the declared
carrier kind. Units and indices remain the equation algebra's checked
signature; membership neither generates nor constrains token exponents.

Amended 2026-11-13 (discussion §39): a token-flow arc asserts continuity
of effort and flow, so the effort pairing is **derived at connect time**,
never stored on the arc — a `function:effort` port couples iff the peer
exports a `function:effort` variable carrying a token comparable to the
mechanism's `promo:drives`. Missing effort reports
`effort-unavailable`; the rule does not apply to non-effort ports.

Amended 2026-11-15 (discussions §43, §44): **export is
classification-driven** — a `function:flow` variable is peer-readable
across a contact without `portVariable`; the flag stays as the
explicit override for non-flow exports (§43).  **Demand stays
declared** — `hasPortVariable` is the entity type's contract, and a
declared flow port that binds nothing (no carrier-matching arcs, or
contacts whose peers export no comparable flow) is *absent*, not
unbound: balances specialize to the connected topology and emit no
term for an absent mechanism (§44).  `unbound-port` still reports
for non-flow demands — an unconnected effort makes the law ill-posed,
not absent; `ambiguous` and `effort-unavailable` are unchanged.

Manual `tokenVector` authoring, propagation, signature-driven membership,
membership-to-vector defaults and token-signature advisories have been
removed. Existing stored vectors are inactive metadata, retained without
bulk data migration; they do not affect checking or connection licensing.
The previous implementation and API-saved artefacts are preserved at Git
tag **`archive/token-signature-algebra`** (checkpoint `bcbf22f`).

## 4. What carries tokens and what does not — the neutrality ruling

User-ruled (2026-11-05): **extensives, rates/flows, and efforts carry
tokens; frames, coefficients, constants, and geometry stay neutral.**

- Neutral: position (`r_*`), time (`t`, `to`, `te`), direction flags,
  universal constants, transport coefficients (`kConv*`/`kDiff*`/`kQ*`),
  interface areas (`Axy`/`Axz`/`Ayz` — "associated with all transfers,
  so neutral").
- Rationale for coefficients: the transfer *law* computes the
  transferred token via the driving effort — the coefficient's own
  signature is redundant.

*Encoded:* `seed.py _seed_incidence_factors` materialises `F_*`
records token-free and strips legacy declarations at load (floor
migration — file-level strips alone get resurrected);
`test_graph_store` asserts neutrality.

The neutrality ruling concerns meaningful network membership; it does not
require users to encode algebraic cancellation or coefficient exponents.
Equation checking uses units and indices (amended 2026-11-12, §38).

## 5. Mass granularity is a model-objective choice

`token_mass` and `token_component_mass` are **linearly dependent**:
`mass = Σ n_i·M_i` (molar-mass-weighted sum).  A model picks its grain —
crude total mass, or species-resolved component mass.

- The mechanism vocabulary declares only the **family** (`token_mass`
  on `mass_transport`); the grain resolves via token ancestry.
- Overdetermination rule: *all* species of an extent tracked **plus**
  the total ⇒ a redundant balance.  Partial species + total is a valid
  closure (implicit remainder).  The check is cardinality-dependent —
  needs the species-set `S` machinery; deferred until a consumer exists.

Amended 2026-11-25 (§32 follow-up): the species grain is the basic
one — the token-level union arc sub-indices `A_mass`/`A_energy` and
their derived `F_mass`/`F_energy` factors were removed.  Nothing
consumed them, every balance contracts per-mechanism legs, and a
union-typed flow var cannot be paired to a mechanism.  Bulk totals
live on the carrier mechanism (convection carries net mass — `E_29`
contracts `A_conv` only); arc-typed vars always declare their
mechanism sub-index.

## 6. Everything is a named graph — artefact lines, pins, resolution scope

One `rdflib.Dataset`; every artefact is a named graph (draft + frozen
versions).  Pins (`usesOntology`, `usesLibrary`, `usesSpecies`,
`usesAssignment`, `usesModel`) form a dependency DAG — the resolution
scope is self-first, then pins breadth-first.  Reads resolve across the
scope; writes go to the editable graph only (`editable_param` vs
`graph_param`).

*Deviates from:* file-per-model and global-namespace approaches — every
resource is graph-scoped and versioned by artefact line.

## 7. Writes go through APIs; the data files are serialized persistence

`data/*.trig` is serialized store output — apps/APIs only, never manual
edits.  Guards enforce **conscious** semantic change:

- **Additive token declarations exempt** from the structural lock —
  declaring tokens on an untracked var changes no equation semantics.
- **Altering/removing carriesToken** on an equation-referenced variable
  remains guarded: membership affects port licensing. The simplification
  does not silently reclassify existing variables or bypass this lock.
- **Fixed signature on used variables** (ruled 2026-11-11): an unused
  variable may be redefined; a used variable must keep its units and
  index structures — every equation attached or rewritten on it must
  derive exactly the declared signature.  **"Used" means foreign
  references only** (amended same day): `via="rhs"`/`"incidence"`
  uses in *other* equations lock; the variable's own defining
  equations (`via="lhs"`) are the definition itself — rewriting them
  is exactly how a signature gets redefined, so they do not lock.
  The write path 409s structural edits gated on foreign refs; the
  editor rejects a signature-mismatched Check result at Accept.
- Frozen (`promo:frozen`) resources are proven — unfreeze first.
- Detached/orphaned resources get swept via
  `DELETE /api/equation/equations/{iri}` (added 2026-11-05 for the
  E_2/E_3 shadow cleanup).
- **Write-path membership guard** (amended 2026-11-12): a connectable
  variable (`portVariable`) requires `carriesToken`. Membership creates no
  algebraic signature. Existing vector metadata is preserved but ignored
  by the checker; no automatic declaration migration is performed.

*Benign delta class:* a stale line may show live-only vocabulary
self-declarations (`a rdf:Property`/`rdfs:Class` stamps the serializer
emits per line) until its next save — seen on model-2/model-3 in the
2026-11-10 review; isomorphic otherwise, self-heals.

## 8. Indices are algebraic, not positional

Index conformity is checked by index **IRI sets** (ordered-union);
`dialect.permute` normalizes operand order to the declared lhs order.
Element-wise `+`/`-` likewise conform by set (ruled 2026-11-13):
the result order follows the left operand and the renderer permutes
the right one (`_align`) for position-bound targets — matlab binds by
label.  A differing index set still fails.
Different index sets bind positionally (flat) — required by loop
residuals.  `subIndexOf` partitions are the mechanism sub-indices
(`idx_arc_convection` ⊂ `idx_arc_mass` ⊂ `idx_arc`); the checker
contracts by exact IRI only — sibling contraction is a known open gap
(`E_29`).  Product notation (ruled 2026-11-14, §40): `a * b` is the
index-preserving product — elementwise over shared indices, ordered
union otherwise; `.` is retired and contractions are always explicit
(`reduceSum(body, K)` / `Product(body, K)` name the index to
eliminate — `E_42`: `reduceSum(F_diff * fnd, A_diff)` reduces
`A_diff` while `N,S` survive).  The global consistency report marks
equations over a coordinate-class index (`σ[X]` — `X` binds contact
arcs only at instantiation) **bound-scope** rather than error: their
declared index signature is unverifiable in declared space by
construction, so only units are compared there and binding-scope
typing is checked at instantiation.

Amended 2026-11-22 (§45, with same-day refinement): **a bare
incidence factor's node axis is never a contraction index.**  A
`reduceSum`/`Product` over a node-source index whose argument
contains an `[node, arc]`-carrying variable *as a linear factor*
(`effort * F`) is rejected — that form type-checks in declared
space but evaluates the wrong contraction once the effort binds the
contact coordinate `X` in bound scope (the §40 zero-flow
incident).  The through-drop spelling is `reduceSum(σ * effort,
X)`.  Incidence factors nested inside nonlinear forms are exempt:
the upwind selector `half * (F - d*abs(F))` contracts `N`
legitimately — there `F`'s node axis *must* contract to select
the upstream node per arc, and `σ[X]` cannot express it.
Detection is structural: the argument splits on top-level `Add`,
and only `Var` leaves reachable through `IndexPreservingProduct`/
`Group` count as linear factors.  Detection keys on the
ontology-seeded `index_source` alias (`node`/`arc`/`coordinate`),
never on `F_*` names; arc-like includes `subIndexOf` sub-indices.
Bound-scope recheck at instantiation remains the backstop.

## 9. Species distribution is computed, not declared

The §20 fixpoint engine (`instantiate/distribute.py`) computes per-node/
arc species sets `S` and active-reaction sets `K` from topology and
capability declarations — species ride *on* mass-family arcs rather
than getting their own network.  Stoichiometry ν is a parameter-class
variable indexed `[S,K]`, valued at instantiation — scheme equations
need no coefficient slots.  (Reaction index renamed `q`→`K`,
2026-11-12 — ProMo12 convention `N_{S,K}`.)

## 10. No OWL — RDFS only

The vocabulary deliberately stays at RDFS level: `promo:parent`
ancestry chains supply the subclass/subproperty semantics the suite
needs.  Richer inference is resolved in code over declared predicates,
not in a reasoner.

## 11. The suite emits; the user runs

The suite's contract ends at the **model interface** — it emits
self-contained bundles, it does not execute simulations (ruled
2026-11-05).  Each target's export (`POST /api/instantiate/code/export`)
carries everything an external run needs: the model source
(`derivative`/`initial`/`outputs`), `model_data.json` (incidence
matrices + value-cell literals + IC pins), a `run.*` driver script and
target harness (python `.sh` wrapper, julia `Project.toml`, matlab
`@MultiDimVar` vendored class).  Simulation execution is external and
**user-owned** — the suite ships in a small docker without solver
runtimes.  In-service `POST /initial` remains for verification (t=0
consistency), not production runs.

## 12. Submodel composition — occurrence vs definition tiers

**Ruled 2026-11-05** (after the "should every group be a graph?"
discussion): the two tiers stay.

- *Occurrence* = tree node — label, layout, boundary wiring,
  `overrides`, optional `refersTo`.  Uniform already; occurrence-level
  identity is unavoidable (two uses of one submodel need distinct
  positions/wiring).
- *Definition* lives either in-doc (composite = `treeId`, no IRI —
  private, unversioned, zero blast radius on edits) or in its own
  graph (`refersTo` pin — shareable, versioned, edits propagate).
- **Extract** promotes in-doc → artefact; **Dissolve** demotes —
  one-way copy.
- **Two uses of an artefact-level definition** (amended 2026-11-08,
  §33): *referenced* — sealed, renders in-place read-only, only
  declared ports connectable (strict boundary; dissolve is the
  escape hatch) — or *copied* — insert+dissolve: pasted content
  becomes ordinary host content, every leaf a legal connection
  surface, provenance = `dissolvedFrom` and dies if the composite
  is ungrouped.  Copy = private editable reuse; reference =
  curated, versioned, contract-bound reuse.

*Not adopted:* every-group-an-artefact — it forces ad-hoc groupings
through pin/version lifecycle and reintroduces a private tier anyway
("internal artefacts").  *Adopted direction:* uniform **addressing**,
not uniform persistence — composites get `{graph}#c_N` identity when a
consumer needs it (`refersTo` into a sub-part, per-occurrence override
keying).  Occurrence-path namespacing at instantiation landed
2026-11-10 — §22 Option A below.

## 13. Arcs bind only leaf entities — open arcs preserve the invariant

**Ruled 2026-11-06** (the openArc mechanism is a basic principle that
"got forgotten over time"; it is construction, not bookkeeping):

- The model is a **flat graph of basic entities**: `ModelArc` endpoints
  are always *leaf* node IRIs — never a composite, never the view.
- The tree is an **overlaid hierarchy** for making large models
  manageable — a view organisation, not a parallel node layer.
- An **open arc** arises when a leaf-bound arc's far endpoint falls
  outside the current view's scope (zoom into a composite where an
  inside leaf is connected outward): the end "is not defined" *in that
  view*, so the arc renders open as a boundary stub/terminal.
- Completing a stub binds the open end to a **leaf inside** — the arc
  is re-rooted to a real leaf↔leaf connection, never to the composite.
  The mechanism is what lets the overlaid hierarchy exist without ever
  violating the flat-graph invariant.

- At **artefact scope** an open end is not an incomplete arc but a
  **declared port** — the artefact's interface (amended 2026-11-08,
  §33): a complete contract of what flows, direction, and expected
  peer.  Two origins: *severed* by extraction (contract inherited
  from the cut arc) or *authored* by declaring the imagined peer
  (phantom) — the connection rules derive the contract, the
  direction convention stays a flippable choice.  Open ends persist
  indefinitely; nothing is auto-deleted or forced to complete.

*Encoded:* `ModelArc.sourceIri/targetIri` = leaf IRIs;
`CompositeDoc.openArcs` carries the boundary terminals;
`reconnectOpenArc` resolves a stub to an inside leaf.

---

## 14. Token flows are transport-mediated — capacities never connect directly

User-ruled (2026-11-10): **every token flow between two capacities
requires a transport system between them — including flows to and
from the environment.**  A direct capacity↔capacity arc is
unphysical, whatever the capacities' sizes.

- **Capacities** store extensive quantities.  `temporalType`
  distinguishes finite `dynamic` (lumped, point) from infinite
  `constant` — the environment is the *infinite capacity*: it
  provides and consumes extensive quantities at constant effort.
  That effort is what drives the physical process — the boundary
  condition lives on the environment, not on the arc.
- **Transport systems** generate the flow from the efforts at their
  ends — the constitutive relation lives there, never on the arc.
  Two physics grades:
  - *true physical transport* — `spatialType: distributed`,
    `temporalType: dynamic`: has capacity of its own (material in
    transit stores);
  - *engineering simplification* — `temporalType: event-dynamic`:
    capacity-free, a time-scale assumption collapsing the
    transport's dynamics.
- **Regime is per-assignment, inside the capacity too (ruled
  2026-11-24, BL §47):** the time-scale assumption isn't only a
  transport property.  `etype_lumped_qss` — a `promo:parent` child of
  `etype_lumped`, same scale composition — binds an assignment that
  drops `dPdt` from `state_variables`; the balance stays in sequence
  as an algebraic net-force output (support reaction).  Sibling
  etype, not a runtime flag: emitted state count differs, so the
  binding is modelling-time and per-node mixing comes free.  Use the
  quasi-steady lump on large models; keep the dynamic one where the
  fast mechanical mode matters.
- **Licensing consequence (enforced 2026-11-10):** the domain+token
  rules (`physical↔physical` + `sharedToken`) alone were too
  permissive — they licensed capacity↔capacity arcs.  `physical-same`
  now carries `promo:requiresMechanism`: `resolve-connection` skips
  the rule unless at least one endpoint *entity type* reaches a
  token-bearing mechanism grouping (`mechanism_token` walk over
  `promo:parent` → `promo:token` on `mass_transport`/
  `energy_transport`).  Callers pass `source_etype`/`target_etype`
  alongside the domain pair; without them the check is skipped
  (read-compat).  Role is declared in the ontology — the grouping
  supertype — not derived from scale signatures.

---

## 15. Construction rules and global structural checks complement each other

Amended 2026-11-12 (discussions §36, §38): definition/deletion rules and
lower-triangular ordering maintain consistency during construction. The
explicit equation-editor audit rechecks the selected artefact and pinned
scope for expression validity, units and index conformity.

The report distinguishes structural errors from structurally consistent
equations, exposes operand declarations and links to owning authoring
surfaces. It is read-only; it does not certify physical meaning, connection
licensing, solver solvability or assignment closure. Local edits make a
report stale. Token-signature categories and correction writes are removed;
authored equations and declarations are never rewritten to silence errors.

## 16. Information processing uses unidirectional signals

User-ruled 2026-11-12 (discussion §37): control, or information processing,
operates solely on **unidirectional signals**. Observation and manipulation
are **earmarked signals**, primarily marking interaction with the physical
system rather than ordinary internal information processing.

Control signals are **normalised and dimensionless**. Generic controllers
define signal inputs/outputs, not observation/manipulation variables; those
roles belong to model connections. This does not erase physical time units
from time constants or integration coordinates. General information
processing beyond control remains an open design question.

- **Observation** reads a physical quantity into a signal, through an
  instrument in real-world systems. It may read a state, secondary state
  or **flow**; it is not restricted to stored quantities. Reading a flow
  is distinct from transporting the extensive quantity itself.
- **Manipulation acts on transport systems**, through a transducer to the
  physical actuator (the “valve”) regulating the flow of extensive
  quantities between capacities. It does not act directly on capacities
  or bypass the transport system.
- These earmarks distinguish reading/acting interfaces to physics, not
  every controller input/output. Internal connections carry signals;
  unidirectional connections may compose into a feedback loop.

*Encoded (2026-11-12):* the actuation rule declares
`promo:targetEntityType` = the transport-system type. Resolution checks the
target's ancestry, including for swapped bidirectional rules; missing
endpoint type information does not license a constrained rule. This is a
generic ontology constraint, not a hardcoded actuation exception. The seed
floor adds the constraint to the core rule when absent; explicit custom
targets are preserved. Frozen ontology versions are not migrated.

*Implementation boundary:* role display remains derived from connection
rules; no separate persisted sticker is introduced. Existing controller
memberships are not automatically migrated; user equations remain untouched.

## 17. Surfaces are volumes; environment is the generic reservoir; the seed floor is machinery only

Ruled 2026-11-25, after a full audit of what `seed.py` mints silently
(BL §52):

- **Surfaces are not entities.**  A surface is an abstraction of a
  thin volume; surface reactions and phase boundaries are modelled as
  `point` (kinetic wall, no adsorbed inventory) or `lumped` (thin
  film *with* inventory/coverage) nodes — both already carry
  `reaction_host`, so no `surface` etype and no
  `surface_reaction_host` capability exist or are wanted.  A phase
  interface is **two point volumes**, one per phase, giving the
  interfacial state each side's diffusive flux needs; the jump
  relation (equilibrium or kinetic) is an equation over the pair —
  the standard sharp-interface structure, expressed with the
  existing topology.
- **`environment` is the generic source/sink** for tokens of any
  form — species, bulk mass, heat, charge, work.  `species_source`
  is only its species leg (gates `promo:speciesAllocation`); the
  other legs arrive with the boundary-condition machinery
  (effort-pinned ports, injected fluxes), not as N new capabilities.
  Environment never hosts reactions — a reacting wall is a volume
  *between* environment and bulk.
- **The seed floor carries machinery, not physics.**  Seeded
  constants are the algebraic numerals (`zero`, `one`, `half`).
  Physical constants are authored content: `g` moved from the seed
  to the library (`V_126`, constant-class, value 9.81) on
  2026-11-25, matching the Boltzmann precedent.  Seeded vocabulary
  is the only channel that mints resources without an authoring
  gesture — keep it minimal and auditable; token vocabulary itself
  stays (`token_mass` is the family anchor + bulk grain,
  `token_charge` is parked for electrochemistry).

## 18. Name component extractions, not basis-vector projections

Ruled 2026-11-25 (BL §53): a `reduceSum`-style contraction that
extracts a **physical quantity** gets its own named variable; a
basis-vector projection or algebraic fragment does not.

- `x`, `y`, `z` — `e_i · r` contracted over `C` — are authored
  geometry variables `[N]`, physical network
  (`term_function_geometry`, token-neutral).  `E_fPot` now reads
  `fmc·g·z`; the projected areas read `Axy = x·y`, `Ayz = y·z`,
  `Axz = x·z`.
- Contrast: `e_z` in `E_F_g`'s `m·g·e_z` is a **basis vector** —
  it projects a scalar into a frame, it is not a named quantity;
  it stays inline.
- The test: does the subexpression denote a quantity another
  equation would reuse (elevation, velocity components, projected
  area)?  Name it.  Is it just how the algebra happens to group?
  Leave it inline — named fragments multiply the variable count
  without adding meaning.

## Open deviations / known gaps

- Transport **interface arity** — opened 2026-11-10; ruled: derive,
  don't declare.  Topology is per-instance by construction: *N*
  token arcs on one transport node = *N* boundaries (a cooling fin
  coupled to several solids and the air is legal topology).  The
  canvas refuses only same-pair same-carrier duplicates — never
  counts ports.  Arity is *derived from the assigned behaviour's
  index structure*: a per-arc-indexed constitutive (`F[A_arc]`,
  `k[A_arc]`) is open by construction; a scalar/pairwise coupling
  (`F = k·Δe`, scalar `k`) is exactly-2 by construction — a third
  arc has no slot to bind.  Residual gap: `port-coverage` flags
  the numeric mismatch (3 peers → 9 bound slots) but cannot name
  the semantic reason ("convection is pairwise"), and whether a
  mechanism *family* is intrinsically pairwise (through-law vs
  distributed) may still warrant an ontology-side note on the
  constitutive relation rather than the etype.
- `E_29` sibling sub-index contraction (`idx_arc_convection` vs
  `idx_arc_mass`) — checker machinery gap; the current model avoids it
  (uses same-index `F_conv . fmc`).  Options recorded in the
  2026-11-03 handoff.
- Component fold (§41/§42) — machinery **landed 2026-11-20**:
  `promo:elements` literal element sets on index records plus
  `idx_component` `C = {x,y,z}` (`index_class "component"`).
  Component selection **ruled 2026-11-23 — seeded basis vectors**:
  `e_x`/`e_y`/`e_z` are `[C]`-indexed constant+parameter scheme
  objects (the σ/`F_k` pattern — dimensionless, token-neutral)
  carrying the first floor-seeded value-cell tables, keyed on the
  index's literal element names.  `v_i ≡ reduceSum(e_i * v, C)`
  extracts, `e_x*vx + e_y*vy + e_z*vz` injects, cross-component
  products contract each factor against its own `e_i` — so
  `E_26`/`E_27`-style terms need no `[C,C']` machinery.  Value
  cells resolve through the artefact's pin scope
  (`_binding_cells`, least→most specific — artefact's own cells
  win).  **Consumer fold landed 2026-11-24** — `r` (ontology
  `V_115`, physical, `[N,C]`, frame) and `v` (library `V_116`,
  macroscopic, `[N,C]`) declared; `v := ParDiff(r,t)` replaces
  `E_6`/`E_9`/`E_10`; the coefficient triples extract components
  (`kConvX := …·reduceSum(e_x·v,C)` &c.); `Axy`/`Axz`/`Ayz`,
  `fKin` and `fPot` contract `e_i·r` / `v·v`; `vx`/`vy`/`vz` and
  `r_x`/`r_y`/`r_z` deleted.  **X↔C seam landed 2026-11-24** —
  `promo:alignedComponent` literal on `ModelNode` declares which
  `C` element a transport's `X` aligns to (element *name*;
  direction cosines deferrable to a richer value).  Seeded
  `e_align [X,C]` (constant+parameter, dimensionless,
  token-neutral) binds it via the new `alignment` binding — the
  σ/`direction` pattern with a component axis: per contact, the
  touched node's unit `C` vector, demand-driven
  (`alignment-undeclared`/`-invalid`/`-ambiguous` problems only
  fire once a consumer binds).  `fP[C] := reduceSum(e_align *
  σ*p_mech, X)` lands a scalar `X` force on the right momentum
  component — the prerequisite for `P[C]` is in place.
  **Momentum slice landed 2026-11-24** — two subjects, per ruling:
  fluid-mechanics contact exports on the convection transport
  (`fP := e_align·σ·p_mech·Ayz`, `v_str := e_align·kConvX·inv(ρ)·Σσp,X`,
  `fmom := fmc·v_str`), mechanics content/balance on the lump
  (`P`, `F_g := m·g·e_z`, `dPdt := F_conv·(fmom+fP) + F_g`,
  `v := P·inv(m)`, `P := m·v`).  Per-contact exports declare the
  mechanism's arc index (`[A_conv,C,N]` — the `fmc` pattern): the
  node slot is what the peer gathers on, and the emit pairs
  elementwise axes **by index name**, not bound elements —
  `e_align{X,C} × fmc{A_conv,N}` is an outer product, so an
  `e_align` consumer may only multiply `X`-typed operands (an
  `A_conv` factor needs an `X`-view alias or a contraction).
  `v` could not go port (§18 lock) — `v_str` carries the
  stream-velocity role, token-scoped to `momentum` so it never
  candidates a mass-flow port.  `test_01`: transport wired
  (5-eq sequence), `Node_2` declares `x`; emit verified.
  *Remaining:* genuine tensor objects (`r:r'`, stress) stay §42.

  **Lumped balance landed 2026-11-24** — `etype_lumped` conserves
  two contents at once (`dmdt` + `dPdt`), which forced three
  rulings:
  - **`state_variables` is set-valued.**  A lumped entity
    conserves several contents simultaneously; the assignment
    carries a *list* (promo:hasStateVariable multi-valued), the
    closure engine still derives the primary state from the base
    equation's lhs, extras are declared.  `m` binds the live mass
    state through the `E_m_def` alias (`m := dmdt`), not a shadow
    datum — `dPdt` is marked an output so the closure counts it
    consumed.
  - **Identity pairing wins at a port.**  A port var takes its
    own kind from the peer when the peer supplies it; ambiguity
    is only among token-comparable *substitutes* (`fP`/`fmom`/
    `v_str` are all momentum-tokened — identity disambiguates).
  - **Port gathers are axis-takes, not flat picks.**  `Gather.map`
    holds positions along the peer bound axis carrying the
    contact elements (`map_index`, `peer_indices`); each dialect
    emits a native axis-take (`np.take`/`selectdim`/subscripted
    `value`) so vector ports gather whole `[C]`-rows.  Coverage
    counts rows × span.
  `test_01` emits: `dPdt` is the second u-state, `fmom`/`fP`
  gather the transport's `[C]`-rows, balance residual verified.
  *Same-day addenda:* runtime-supplied universe variables are
  `instantiated` — `t` (`V_11`) joined `instantiated` on both
  lumped assignments after §48's `E_m_def` integral bound it and
  broke closure; §49 landed the queued Darcy law — `fl`
  keeps `port_variable` but computes via
  `E_fl = λ·(L/d)·ṁ·v²/2` (`v_str`, not `v`; `lam`/`Lp`/`dp`
  arc-bound `[A_conv]` instantiation params), upgrading it from
  imposed boundary port to computed export without changing the
  gather semantics for the lump; and §50 wired the mechanical
  balance into `etype_lumped` — `dEmdt` as diagnostic output
  (balances are readings), `E_P_int` replicating the §48
  slot-alias for `P`, `r` joining `instantiated` as per-node
  geometric datum.  *2026-11-25 addendum (§54/§55):* the §47
  "ΣF(v)=0 → v" upgrade resolved differently — velocity is
  determined pressure-driven *on the arc*: `E_v_str_darcy`/
  `E_fmc_darcy` (quadratic `Δp ∝ v²` via `sign`/`abs`/`sqrt`
  — explicit, no algebraic loop) sit beside the linear
  `kConvX` laws as alternatives on the same lhs; the
  assignment sequence picks the regime.  The lump's contact
  velocity arrives via the `v_str` port: `E_fKin` fixed in
  place (`v`→`v_str`, its only consumer — the §49 physics
  ruling applied consistently), `E_P_int`/`E_v_fromP` dropped
  from `etype_lumped` (dead cone), `v_str` joins `ports` on
  both lump assignments, and `etype_lumped_qss` carries the
  full energy wiring (`dEmdt` diagnostic, no `v`/`P`).
- Overdetermination check — designed (§5), unimplemented.
  Overdetermination = **declared constraints creating algebraic
  dependencies between vars declared independently**.  Sources:
  constancy constraints (`V` const → `m = ρV` links mass/density),
  constitutive closures (EOS, incompressibility), normalization
  (`Σ x_i = 1`), token granularity (`mass = Σ n_i·M_i`).
  **Constancy is instance-scoped** (ruled 2026-11-05): the same var
  may be dynamic on one entity and pinned on another — even within
  one model — so it cannot be `var_class=constant` on the record.
  It is a per-element pin like an IC but for all `t`; the natural
  home is the instantiation/value channel alongside `valueCell`
  (a `promo:hold`-style declaration), demoting the pinned element's
  state to a `der=0` constraint.  The check itself is DOF counting
  over declared structure: `states + algebraics` vs
  `equations + constraints`.
- Cross-artefact consistency review — deferred until all apps are
  operational (impact analysis, publish-boundary SHACL, transactional
  mutation, atomic multi-file persistence, stale `closed` assignments).
- Occurrence-path namespacing — **landed 2026-11-10** (§22 Option A:
  the use site is the unit of instantiation).  Each
  (occurrence, entity type) pair instantiates independently: nodes
  partition by longest occurrence-path prefix, inner arcs qualify
  like nodes (`{occ}/{inner}`), var instances carry the path
  (`{occ}/{internal_id}@{et}`), the schedule DAG runs on
  `(occ, et, eq)` nodes, plan slots/blocks carry explicit
  `occurrence` ownership (a bound boundary arc doesn't disqualify),
  emitted names get the occurrence's composite-IRI-fragment chain as
  tag (`c_2_V_5`-style), and value cells resolve qualified-first
  then prefix-stripped (submodel defaults apply, host pins win).
  Sub-plans persist populated per occurrence and replay standalone
  via `?instantiation=<artefact>#occ_N` (`_pinned_plan`).  *Remaining:* shared-`var_class`
  constants still duplicate per occurrence (dedup later); a
  spurious shared loop can tag an occurrence whose own DAG is
  acyclic (aggregated port edges are conservative).
- `promo:Mechanism` vocabulary (§32 stage 2) — **partially landed
  2026-11-11**: `promo:drives` floor-seeded on mechanism leaves
  (effort-token coupling signature; `carries` = the inherited
  `promo:token` family — free) plus the `mechanism_drives`
  ancestry-union walk.  Still unbuilt: the pairing resolver in
  `builder.contact_arc_domain` (`port-domain-ambiguous` still
  terminates), the effort-availability advisory at contacts,
  `conjugates` (entropy — no consumer), and the `promo:Mechanism`
  resource layer (needed only when one etype hosts two mechanisms).
  First consumer = the first multi-mechanism model.
  *§56 progress 2026-11-25:* charge transport landed as a
  **single** mechanism — `etype_charge_transport` +
  `etype_conduction_transport` (`drives charge`), `idx_arc_charge`/`A_el`,
  `F_el`, and the `qel`/`fe`/`Ue`/`Cel`/`kEl`/`Rel` family with
  closed assignments (capacitive conductor ruled).  The electrode
  (charge + mass on one boundary) remains the pairing resolver's
  first real consumer.
- Seed-derived vs ruled drift — floor migrations can silently
  re-implement superseded semantics (found 2026-11-06: F_* token
  decls resurrected post-strip).  Review audits the seed layer
  against the rulings, not just data files.
- Mediated-flow licensing (§14) — enforced 2026-11-10 via the
  ontology-declared `requiresMechanism` rule constraint.  Compatibility
  callers omitting endpoint entity types still skip this check; new
  callers must supply them.
- §33 machinery — authored/phantom ports: landed (`14d6aff`);
  strict referenced boundary: **enforced 2026-11-10** — the
  connect gesture's automaton swallows an armed completion at any
  leaf not declared a port (the artefact's root-composite open
  arcs, `externalIri` = inside leaf); standalone instantiation
  with phantom closures: ruled, partial — the overlay
  (`_phantom_overlay`) materializes phantom peers for severed and
  authored terminals; evaluate-on-use items remain open.
- **Existing token declarations and physical-interface licensing** —
  generic controller variables may still carry observation/manipulation
  memberships from earlier authoring. Correction requires explicit impact
  review, not automatic data rewriting. Transport-target actuation licensing
  is implemented; no persisted role sticker is needed where the role can
  be derived. General information processing remains open.
