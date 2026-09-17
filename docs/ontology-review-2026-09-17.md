# Ontology framework review — 2026-09-17

Multi-pass review of the ProMo14 ontology contract and its implementation.
Method: (0) contract review — restate negotiated semantics, find
ambiguities; (1) semantic core consistency — seed vs migration vs live
`data/ontology.trig`; (2) invariant enforcement map — backend vs UI-only
vs unenforced; (3) contract soundness for consumers — `RdfContext`,
`resolve-connection`, BL artefact; (4) edge cases — cycles, collisions,
orphans, versioning.

## 1. The contract (ruled 2026-09-17)

### 1.1 Domain tree and scope

- Explicit `domain_root` above `physical` and `information`. Tokens and
  scale dimensions bound to root are inherited by every branch.
- Rule `scope` is **branch-relative**: `same` = the endpoints' top-level
  ancestors (children of `domain_root`) coincide; `cross` = they differ;
  `any` = unconstrained.  Replaces the pre-`domain_root` definition
  ("same = shared ancestor"), which became void once every pair shared
  root as ancestor.
- Root is a **singleton branch**: root↔physical = `cross`,
  root↔root = `same`.  Defined-but-rarely-used; harmless if it never
  fires.
- `domain.branch` is a **display label only**, never a semantic input.
  Invariant: `domain.branch == top-ancestor.branch`; root carries none.

### 1.2 Connection = variable identification

An arc does **not** generate cut equations (`v_A = v_B`).  It declares
that the connected ports' variables **are** the same variable — one
unknown, visible under each entity's own label.

- `token-flow` arc: per shared token, carries a shared **(effort, flow)
  pair** across the boundary — bond semantics.  The arc stores nothing:
  the effort is one value on both sides; the flow is one variable,
  continuous across the boundary (what leaves A enters B, sign per arc
  orientation).
- `reference` arc: the target's input variable *is* the source's output
  variable; direction records causality only.
- **Sharing is symmetric; causality is not.**  Both endpoints' balances
  and laws reference both boundary variables, but the effort's value is
  set by the connected capacities' state while the flow's value is
  computed inside the transport system as a function of the boundary
  conditions — the negative effort gradient sets the physical
  direction.  The arc's source→target orientation is bookkeeping only —
  it fixes which endpoint's balance sees `+f` vs `−f`.  Flow variables
  are owned by the transport node (own IRI); only identified efforts
  need a deterministic canonical name (e.g. source port's
  `internal_id`).
- Transport behaviour lives in transport-system **nodes** (CWA 4.1.5),
  which reference the shared boundary variables directly.  The arc
  itself computes nothing.
- Codegen consequence: arcs produce variable aliasing/merging, not
  equations — no extra rows in the bipartite graph.

### 1.3 `sharedTokens`

- `sharedTokens` = the tokens whose transfer the rule licenses.
  `token-flow` → continuity per matched token; `reference` → signal
  value conveyed.
- Applicability: `effectiveTokens(src) ∩ effectiveTokens(tgt) ∩
  rule.sharedTokens ≠ ∅`, ancestor-aware on the token tree.
- Token matching = **comparability** (provisional — revisit when
  modelling starts): rule token R matches bound token B iff one is
  ancestor-or-self of the other (same root-to-leaf path).  Binding a
  parent activates its refinements; binding a subtoken alone activates
  only that refinement.
- **Empty `sharedTokens` = no token licensed = rule never applies**
  ("no token, nothing transported").  Authoring-time warning candidate.

### 1.4 Intraface visibility

Variable visibility is a property of the **intraface**, not the rule:
the arc exposes each endpoint's *full boundary state* — not just
conjugate efforts — to the other side's transport laws.  Required
because e.g. mass diffusion is commonly written f(concentration), not
f(chemical potential).  Cross-coupled laws are checked at equation/BL
level, not by the rule.

### 1.5 Rule resolution

`resolve-connection` returns the **set of licensed connection kinds**
for a pair — multiple matches are not competitors (a phys→phys pair may
carry both a token-flow arc and a signal tap).  Ordering is cosmetic:
deterministic total order = specificity distance, then IRI.

### 1.6 Namespace discipline (combination)

- `promo#` = **vocabulary only** (classes/predicates).
- Instance IRIs mint under the owning graph's namespace —
  `{graphIRI}#`, e.g. `promo/ontology#` for the core ontology.
  Extension ontologies get their own graph IRI → own instance namespace
  → union-of-named-graphs cannot collide.
- External public IRIs (QUDT etc.) are **referenced**, never minted into
  or redefined.  Entities MAY carry external mapping links
  (`skos:exactMatch`/`skos:closeMatch` or `promo:mappedTo` — **not**
  `owl:sameAs`) to public ontology concepts; annotation-only, additive
  under ADR-006.

### 1.7 Versioning boundary

- `data/ontology.trig` = mutable working draft; no rules apply inside.
- Publishing freezes a named graph under a version IRI
  (`promo/ontology/1.0`).  From then on ADR-006 applies: additive /
  annotation / deprecation only; deletion only if unreferenced;
  semantic change = new version + re-validation.
- Artefacts declare `promo:usesOntology → versionIRI` so re-validation
  has a target.

## 2. Findings

### 2.1 Data bugs — FIXED 2026-09-17

- **Duplicate Extensity axis** (`axis_Extensity`, UI-created under
  `promo/ontology#`, vs seeded `axis_extensity`): removed by a general
  (name, domain) dedupe pass in `extend_ontology_hap.py`.
- **Entity types missing scale values**: `etype_point` gained
  `sval_time_macro_event_dynamic`; `etype_transport_system` gained
  `sval_time_macro_event_dynamic` + `sval_length_macroscopic_distributed`
  (CWA 4.1.4/4.1.5).  Verified; 112 tests pass.

### 2.2 Structural inconsistencies (open)

- **IRI scheme**: seed/migration mint instances under `promo#`;
  `service.py` POSTs mint under `promo/ontology#`.  Per §1.6 the
  **seed is the anomaly** — instance IRIs should migrate to
  `promo/ontology#` (references must be rewritten; deferred).
- **Label-predicate sprawl**: `rdfs:label` (tokens), `promo:label`
  (axis terms), `promo:name` (domains), `promo:axisName`,
  `promo:scaleName`, `promo:scaleValueLabel`.  Readers cope via
  fallbacks; consolidate to one canonical label predicate.
- **Classes never declared**: `promo:Domain`, `promo:Token`, etc. appear
  only as `rdf:type` objects — no `a rdfs:Class` triples.  Matters for
  the published artefact's self-description.
- **`temporal_type` vs time scale value** on entity types: redundant
  attributes, nothing keeps them consistent.

### 2.3 Enforcement map

- **Backend** (`service.py`): only 404 (missing IRI) and 422 (empty
  name/label/type).  `_cascade_delete` removes contained children +
  incoming refs — prevents dangling triples but **silently strips
  references** (deleting a token removes it from rules' `sharedTokens`
  with no warning).  No "in use" guard.
- **UI-only** (`App.tsx`): all vocabulary via `<select>` (scope,
  carrier, direction, tokenKind, dimensionKind, temporal/spatial,
  branch); scale-value binding-scope filter (line ~323); root-parent
  lock.
- **Unenforced** (neither layer):
  - domain cycles — parent `<select>` filters only self (line ~441);
    descendants selectable;
  - IRI collisions — `create_*` mints `{prefix}_{name}` unchecked;
    duplicate name silently overwrites (how `axis_Extensity` arose);
  - empty `shared_tokens` (dead rule per §1.3);
  - `branch` ≠ top-ancestor (§1.1 invariant);
  - referential integrity — `source_domain`/`target_domain`/`token`/
    `scale_values`/`parent` IRIs never checked to exist;
  - token matching in `resolve_connection` (absent);
  - `temporal_type` ↔ time scale value consistency.

### 2.4 `resolve_connection` (`service.py:641`)

- **`scope="cross"` dead**: `common = src_chain ∩ tgt_chain` always
  contains `domain_root` → every cross rule filtered.  Needs the
  branch-relative fix (§1.1).
- **Crash bug**: a `bidirectional` rule matching only via the swapped
  pair (line 636) then hits `src_chain.index(rule.source_domain)`
  (line 678) → `ValueError` → 500.  Seed rules are symmetric so it
  doesn't fire today; any asymmetric bidirectional rule does.
- **No token matching**: `shared_tokens` never consulted (§1.3).
- **Tie order nondeterministic**: sort key = specificity only; ties
  inherit rdflib iteration order (§1.5 wants IRI tie-break).
- **Stale fallback**: lines 666–670 derive scope from retired
  `physical-cross` name — dead vocabulary.

### 2.5 `RdfContext`

- Equation-checker contract (variables/indices/`accessible_networks`)
  sound; cycle guard present.
- `connection_rules` exposes full records incl. `shared_tokens` — good
  for BL.
- **Gap**: `domain_tokens` = direct `hasToken` only; no effective-token
  computation (own + inherited + comparability).  Needed by both the
  resolver fix and BL.

### 2.6 Edge cases

- **Cycles**: creatable via UI; `_domain_ancestor_chain` /
  `accessible_networks` terminate via `seen` guards but silently
  truncate — a cycle corrupts scope/branch computation silently.
- **Collisions**: unchecked `create_*` minting (§2.3).
- **Orphans**: none beyond undeclared classes (§2.2).
- **ADR-006**: `_cascade_delete`'s silent ref-stripping is fine for the
  working draft, forbidden for published versions — applies at version
  boundaries (§1.7).

## 3. Recommended actions (priority order)

1. ~~`resolve_connection`: branch-relative scope + bidir-swap crash fix +
   token matching + IRI tie-break.~~  **DONE 2026-09-17** — plus
   `matched_tokens` in the response and shared `RdfStore` helpers
   (`ancestor_chain`, `effective_tokens`, `tokens_comparable`).
2. ~~Backend validation pass: vocabulary Literals on the models,
   referential-integrity checks, IRI-collision 409, empty-`sharedTokens`
   warning, domain-cycle rejection, `branch` invariant.~~
   **DONE 2026-09-17** — except the empty-`sharedTokens` *warning*
   (accepted as legal-but-dead; needs UI surfacing, not a backend
   rejection).  `index_class` left unconstrained (ontology-level vocab
   not pinned); `branch` validated dynamically against domain branch
   labels rather than a fixed Literal.
3. ~~Seed IRI migration `promo#` → `promo/ontology#` for instances~~
   **DONE 2026-09-17** — seed + migration now mint under
   `promo/ontology#`; `extend_ontology_hap.py` rehomes existing
   `promo#` instance IRIs dataset-wide (vocab = predicates + rdf:type
   objects stay).  356 triples rehomed in `data/ontology.trig`;
   idempotent.
4. ~~Declare vocabulary terms (`a rdfs:Class` / `a rdf:Property` — RDF
   level only, no OWL) for the published artefact.~~  **DONE
   2026-09-17** — `RdfStore.declare_vocabulary` derives the vocabulary
   from the graph itself (predicates → `rdf:Property`, `rdf:type`
   objects → `rdfs:Class`); called by seed and migration; 41 terms
   declared in `data/ontology.trig`.
5. ~~Consolidate label predicates.~~  **DONE 2026-09-17** — canonical:
   `rdfs:label` = display label, `promo:name` = key-ish name,
   `promo:shortName` = index symbol.  Retired `promo:label`,
   `promo:scaleValueLabel`, `promo:axisName`, `promo:scaleName`;
   migration rewrote 57 triples in `data/ontology.trig` (retired terms
   remain declared as `rdf:Property`).
6. ~~Reconcile `temporal_type` with the time scale value~~  **DONE
   2026-09-17** — consistency check in `create_entity_type`: a bound
   temporal-triple leaf must agree with `temporal_type` (422 on
   mismatch or multiple temporal leaves); no leaf bound →
   `temporal_type` stands alone (information types).
7. ~~Versioning machinery: `promo:usesOntology` on artefacts; publish =
   freeze named graph under version IRI.~~  **DONE 2026-09-17** —
   `RdfStore.freeze_version(v, graph_iri=None)` copies any artefact
   graph (default: working ontology) into `{source}/{v}`, stamps
   `a promo:Version` + `versionOf`/`versionInfo`/`publishedOn`,
   self-describes via `declare_vocabulary`, refuses re-freeze and
   empty sources.  `promo:usesOntology` and `promo:generatedFrom` are
   declared unconditionally in the vocabulary (artefact-facing terms —
   stamping wires in when artefact persistence lands).
   `export_ontology.py --version X.Y` freezes (if new) and exports the
   frozen graph.

   **Artefact chain** (ruled 2026-09-17): versioning is a dependency
   chain, not per-tool bookkeeping — ontology version → var/expr
   library version → BL assignment → model → generated code.  The
   var/expr library is a *vocabulary artefact* (models reference
   equations by IRI; a semantic change silently rewrites every
   dependent model) → same freeze discipline via the generic
   `freeze_version`.  Models freeze on publish for Model Reuse.
   Generated code is a *derived* artefact: not versioned itself, it
   carries provenance — `promo:generatedFrom` → model version IRI +
   codegen version + timestamp in the file header.  Working drafts
   stay unversioned; only publish freezes.  Open machinery for later:
   SHACL shapes per artefact type at the publish boundary
   (re-validation against the declared `usesOntology` version), and a
   reference index for ADR-006's "deletion only if unreferenced".

## 4. Provisional / revisit

- **Token comparability matching** (§1.3): collect experience once
  modelling starts.
- **External mapping links** (§1.6): adopt `skos:exactMatch` (or
  `promo:mappedTo`) when QUDT unit wiring lands.
- **Generated/editable code split**: if users hand-extend generated
  code, codegen must emit separated generated/editable regions (or
  files) — decide before codegen lands; painful to retrofit.
