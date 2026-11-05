# Design principles — ProMo14

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

## 3. The token model — three layers, each answering a different question

| Layer | Declaration | Answers |
|-------|-------------|---------|
| Connection rules | `promo:sharedToken` | What *may* flow between domains? |
| Entity types (mechanism groups) | `promo:token` on grouping types | Which token family does this mechanism move? |
| Variables | `promo:carriesToken` (membership) + `promo:tokenVector` (algebraic signature) | What does this variable quantify? |

**Arcs carry no token declaration** — carrier category only
(`token-flow` vs `reference`); the token falls out of entity types and
licensing rules.  Direction and token were relocated off the arc
deliberately (§15/§23 of the design discussion).

Key rules (all test-enforced):
- `carriesToken ⊆ tokenVector` — every declared member appears with a
  nonzero exponent; the vector may legitimately contain conjugate/derived
  terms beyond membership.
- `tokenVector` is derivable from the defining equation's rhs via the
  checker (`TokenVec` propagates exponents through operators);
  `carriesToken` remains a semantic, user-confirmed choice.
- Ports license via token **ancestry comparability** (`promo:parent` on
  tokens), filtered by `tokenKind`→carrier (`conserved`→token-flow,
  `reference`→reference).

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
- **Altering/removing** tokens on an equation-referenced var 409s —
  it changes what downstream checks derive.
- Frozen (`promo:frozen`) resources are proven — unfreeze first.
- Detached/orphaned resources get swept via
  `DELETE /api/equation/equations/{iri}` (added 2026-11-05 for the
  E_2/E_3 shadow cleanup).

## 8. Indices are algebraic, not positional

Index conformity is checked by index **IRI sets** (ordered-union);
`dialect.permute` normalizes operand order to the declared lhs order.
Different index sets bind positionally (flat) — required by loop
residuals.  `subIndexOf` partitions are the mechanism sub-indices
(`idx_arc_convection` ⊂ `idx_arc_mass` ⊂ `idx_arc`); the checker
contracts by exact IRI only — sibling contraction is a known open gap
(`E_29`).

## 9. Species distribution is computed, not declared

The §20 fixpoint engine (`instantiate/distribute.py`) computes per-node/
arc species sets `S` and active-reaction sets `Q` from topology and
capability declarations — species ride *on* mass-family arcs rather
than getting their own network.  Stoichiometry ν is a parameter-class
variable indexed `[Q,S]`, valued at instantiation — scheme equations
need no coefficient slots.

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

---

## Open deviations / known gaps

- `E_29` sibling sub-index contraction (`idx_arc_convection` vs
  `idx_arc_mass`) — checker machinery gap; the current model avoids it
  (uses same-index `F_conv . fmc`).  Options recorded in the
  2026-11-03 handoff.
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
