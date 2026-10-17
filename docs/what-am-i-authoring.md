# What am I authoring? — per-tool guide

**Status:** living document — started 2026-10-17 (Track 2).

One section per tool. Each answers three questions: which artefact this
tool owns, what a *correct* artefact looks like, and which problems it
can produce or prevent. Vocabulary follows
`docs/concepts-and-architecture.md`; problem kinds link to
`docs/problem-catalogue.md`.

Rule of thumb across all tools: **the artefact owns *what exists* and
*what can happen*; the model owns *where* it happens and *what it means
here*; instantiation owns *what it is worth*.** If you're about to put
information on the wrong side of that line, stop — it belongs in another
tool.

---

## Ontology Editor

- **Owns:** the ontology artefact — the vocabulary everything else uses:
  entity types, domains/networks, tokens, indices, classification axes,
  scales, connection rules, capabilities, graphical symbols.
- **Correct when:** every entity type a model will use exists, with its
  capabilities declared (`species_source`, `reaction_host`,
  `species_transport`, …); connection rules cover the arcs you intend to
  draw; indices and sub-indices exist for every index your equations
  carry.
- **Produces:** nothing numeric — but missing vocabulary surfaces
  downstream as [`untyped-node`](problem-catalogue.md#untyped-node),
  [`inadmissible-gesture`](problem-catalogue.md#inadmissible-gesture), or
  connection rules that refuse an arc.
- **Not here:** variables and equations (Equation Editor); which
  equations apply to a type (Behaviour Linker); any topology (Modeller).

## Equation Editor

- **Owns:** the var/expr artefact — variables and equations as a checked
  bipartite graph. An *equation* is `variable := expression`; the RHS
  alone is an expression.
- **Correct when:** every definition passes the checker (syntax, units,
  index structure, acyclic incidence). Port variables are declared, not
  defined — they are the leaves. Bound-value slots are marked
  `constant`/`parameter` (determination axis) or get an `Instantiate`
  equation. An `[N, arc]`-indexed variable intended as the incidence
  matrix **must be constant-class** — that slot is reserved for F.
- **Produces:** checked output is trusted downstream — errors here
  surface as
  [`missing-equation`](problem-catalogue.md#missing-equation) /
  [`missing-variable`](problem-catalogue.md#missing-variable) in
  assignments that reference deleted things.
- **Not here:** which equations an entity *uses* (Behaviour Linker);
  numeric values (instantiation); `promo:value` beyond universal
  constants.

## Behaviour Linker

- **Owns:** behaviour assignments — per entity type, an ordered selection
  of equation IRIs from the var/expr graph plus marks (`base_equation`,
  `instantiated`, ports), and the entity's graphical assignment.
- **Correct when:** each entity type used in a model has a **closed**
  assignment. Remember: `base_equation` *is* the balance — a stateless
  entity (transport) must declare **none**, or its LHS becomes a fake
  state variable and the scheduler misreads it. Variables the entity
  supplies as bound values belong in `instantiated`, not in the sequence.
- **Produces:**
  [`no-assignment`](problem-catalogue.md#no-assignment) (missing
  assignment), [`assignment-open`](problem-catalogue.md#assignment-open)
  (free ends left), and — via wrong marks —
  [`unmarked-input`](problem-catalogue.md#unmarked-input) and
  [`algebraic-loop`](problem-catalogue.md#algebraic-loop).
- **Not here:** new equations (write them in the Equation Editor first);
  topology (Modeller).

## Modeller

- **Owns:** the model artefact — topology (nodes typed by entity type,
  arcs typed by connection rule), hierarchy/composites, placements
  (species allocations, hosted reactions, permeables), and fix markings.
- **Correct when:** every node is typed; arcs connect only where rules
  admit them; species placements only appear on capable entities. Arcs
  do **not** declare their token — the token is implicit in the
  transport node's type (concepts §4.1). Boundary conditions are *bound
  values* on a boundary entity (e.g. an environment holding `p`, `T`),
  not constant-class variables forced anywhere.
- **Produces:**
  [`untyped-node`](problem-catalogue.md#untyped-node),
  [`inadmissible-gesture`](problem-catalogue.md#inadmissible-gesture),
  [`unbound-port`](problem-catalogue.md#unbound-port) /
  [`ambiguous-port`](problem-catalogue.md#ambiguous-port) when boundary
  entities don't supply what ports need.
- **Not here:** equations, species definitions, numeric values — all
  referenced, never authored.

## Species app

- **Owns:** the species scheme — `promo:Component`s, `Allocation`s,
  `Reaction`s: *what can happen* chemically, independent of any plant.
- **Correct when:** components cover every species your equations
  index over `S`; allocations exist for every reservoir you intend;
  reactions are declared where they may fire. The model references the
  scheme; it never duplicates it.
- **Produces:** the distribution fixpoint can only inject what
  allocations declare — a species missing from a model usually means a
  missing `speciesAllocation`/`permeable` placement *in the model*, or
  a missing allocation *in the scheme*.
- **Not here:** where species actually are (computed at instantiation);
  kinetic equations (Equation Editor); stoichiometry tables
  (instantiation value cells).

## Instantiation app

- **Owns:** value bindings — `promo:value` scalars, `ValueCell`
  parameter/IC tables, initial conditions. "What is it worth."
- **Correct when:** every external input has a source: bound value,
  port resolved to a peer, or `Instantiate`. Parameters get cells for
  every coordinate they index over — missing cells emit as `NaN` in
  generated code.
- **Produces:** the instantiation *report* (not a persisted artefact
  yet) — read its problem list; each `kind` links into
  `docs/problem-catalogue.md`.
- **Not here:** anything structural — topology, equations, species.
  If a problem's remedy says "the model is missing…", that edit happens
  in the Modeller or Behaviour Linker, not here.

---

## Cross-reading

- `docs/concepts-and-architecture.md` §3 — the artefact table and
  ownership rule this guide applies.
- `docs/problem-catalogue.md` — full cause/remedy per problem kind.
