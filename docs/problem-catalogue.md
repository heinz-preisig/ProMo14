# Problem catalogue

**Status:** living document — started 2026-10-17; **realigned 2026-11-10**
(edit rules: `docs/README.md` tier map). Add a section whenever
an engine starts emitting a new problem kind; keep `kind` strings
character-identical to the code that emits them — enforced by
`test_problem_catalogue_coverage`.

This is the Track 2 guidance seed: one entry per problem the engines can
report, each with **cause** and **remedy** in the vocabulary of
`docs/concepts-and-architecture.md`. Problems are the teaching surface —
they state what the artefact is missing, never silently fix it.

Emitted today by `backend/instantiate` (`/api/instantiate/model`, `/code`,
`/initial`), keyed by `Problem.kind`:

| kind | stage |
|---|---|
| `untyped-node` | topology read |
| `no-assignment` | behaviour binding |
| `assignment-open` | behaviour binding |
| `missing-equation` | behaviour binding |
| `missing-variable` | behaviour binding |
| `unmarked-input` | variable binding |
| `unbound-port` | port resolution |
| `ambiguous-port` | port resolution |
| `algebraic-loop` | scheduling |
| `inadmissible-gesture` | artefact validity |
| `unfilled-cells` | value binding |
| `bad-fill` | value binding |
| `fill-conflict` | value binding |
| `port-coverage` | code plan |
| `port-domain-unresolved` | port typing (§32) |
| `port-domain-ambiguous` | port typing (§32) |
| `species-port-mismatch` | occurrence composition |
| `uncovered-override` | occurrence composition |
| `reference-cycle` | occurrence composition |

---

## Topology problems

### `untyped-node`
**Message:** `model node <id> has no entity type`

- **Cause.** A node in the model artefact lacks `promo:entityType`. The
  engine cannot know which behaviour assignment, ports, or capabilities
  apply — the node is decorative, not semantic.
- **Remedy.** In the Modeller, assign an entity type to the node (or
  delete it if it was a stray). Every model node must be typed.

## Behaviour-binding problems

### `no-assignment`
**Message:** `no behaviour assignment for <entity type>`

- **Cause.** The node's entity type has no §13 behaviour assignment — no
  selected equation set was ever linked to it. The artefact exists
  (ontology knows the type) but its behaviour is undefined.
- **Remedy.** In the Behaviour Linker, assign the equations describing
  this entity type's I/O behaviour, then re-instantiate.

### `assignment-open`
**Message:** `assignment for <entity type> is not closed`

- **Cause.** The assignment exists but is not closed: it defines some but
  not all of the variables the entity's behaviour needs (open = free
  ends remain in the subgraph). Reported alongside the instantiation so
  the user sees it; often paired with `unmarked-input`/`unbound-port` for
  the variables left dangling.
- **Remedy.** In the Behaviour Linker, extend the assignment until it
  closes — typically add the missing constitutive equation or mark the
  remaining variables as ports/inputs.

### `missing-equation`
**Message:** `assignment references unknown equation <iri>`

- **Cause.** The assignment's equation sequence names an equation IRI
  that is not in the var/expr artefact — usually a deleted equation, or
  the model is pinned to a different `var/expr` graph than the
  assignment was built against.
- **Remedy.** Re-open the assignment; re-select a valid equation for
  that slot. If the equation was deliberately removed, choose its
  replacement.

### `missing-variable`
**Message:** `assignment references unknown variable <iri>`

- **Cause.** Same class of problem as `missing-equation`, but for a
  variable IRI — the assignment references a variable that no longer
  exists (or lives in a different var/expr version than the one loaded).
- **Remedy.** As above: repair the assignment against the current
  var/expr artefact.

## Variable-binding problems

### `unmarked-input`
**Message:** `<var> is an external input of <entity type> but is neither
marked port nor instantiated`

- **Cause.** A variable is consumed by the entity's equations but
  produced by no equation in the assignment — an *external input*. The
  engine needs to know where its value comes from: either it is a port
  (resolved against a peer entity, §4.2) or a bound value
  (constant/parameter with `promo:value`, `Instantiate`, fix marking).
  Neither is declared. Exempt: `incidence`-class and `constant`-class
  bindings.
- **Remedy.** Decide the variable's source *in this model*: flag it
  `port_variable` if a neighbour supplies it, or bind a value if the
  entity owns it. This is the "boundary conditions are bound values"
  rule — an environment's conditions get `promo:value`; a peer-supplied
  quantity becomes a port. See concepts-and-architecture §3.1.

## Port-resolution problems

### `unbound-port`
**Message:** `port <var> on <entity type> at node <id> …` (message may
append `— peer state is comparable but not exported (set port_variable
or add a measurement variable)`)

- **Cause.** The variable is flagged as a port, but no peer entity across
  the arc defines a comparable variable to bind against — after both
  passes (direct comparability, then port chaining). Either the peer
  doesn't define the variable at all, or it defines it without exporting
  it.
- **Remedy.** The boundary must supply a value. Either the peer entity
  defines/binds the same variable (e.g. an environment holding `p`,
  `T`), or — if the peer *has* the quantity but doesn't export it — set
  `port_variable` on the peer's variable or add a measurement variable.
  If the port was wrongly declared, unflag it and bind a value instead.

### `ambiguous-port`
**Message:** `port <var> on <entity type> at node <id> …`

- **Cause.** More than one peer variable is comparable to the port —
  the engine refuses to guess. Flagged state candidates are preferred;
  ambiguity means no single winner emerged.
- **Remedy.** Remove the ambiguity: flag the intended source variable
  (`port_variable`/state flag on the peer), or rename so only one
  comparable variable exists across the arc. The model should say which
  peer supplies the value, not leave it to inference.

## Fix-marking problems (ADR-008 layer 2)

`promo:fix` on a `ModelNode` marks a variable as bound *at that
occurrence* — a per-node override of the variable's class regime. A
fixed variable binds as `fixed`: a `promo:value` inlines it like a
constant; otherwise it becomes a codegen input slot (value cells or
`par`). Fix **wins** over a defining equation — the equation is dropped.

### `fix-conflict`
**Message:** `<var> is marked fixed on <type> but is defined by
<eq> — the equation is dropped`

- **Cause.** The variable is both fix-marked and equation-defined in
  the same entity's assignment. Bound *and* computed is
  overdetermined — the fix takes precedence.
- **Remedy.** Decide which owns the value. To compute it, remove the
  fix mark. To prescribe it, the conflict is informative only — but the
  dropped equation may leave its other outputs' consumers unsatisfied;
  check for follow-on `unmarked-input`s.

### `fix-partial`
**Message:** `<var> is fixed on <k> of <n> <type> nodes — the fix
applies to the whole type's binding`

- **Cause.** Some but not all nodes of an entity type carry the mark.
  Bindings are per entity *type* (index element sets span all its
  nodes), so a per-node mark can only widen to the type — the unmarked
  nodes read values too.
- **Remedy.** Mark the variable on **all** nodes of that type if the
  widening is intended (silences the report), or split the entity types
  if the two occurrences genuinely differ.

### `fixed-unbound`
**Message:** `<var> is marked fixed on <type> but has no bound value
(set promo:value or a value cell)`

- **Cause.** A fix mark without data: no `promo:value` scalar and no
  value cells cover the bound extent. (Cells are invisible to the
  builder — the service retracts this problem when cells exist.)
- **Remedy.** Bind the value: `promo:value` for a scalar, or a
  `ValueCell` table when the variable indexes over nodes/arcs.

## Scheduling problems

### `algebraic-loop`
**Message:** `algebraic loop <i>: <equation ids>` (also surfaced in
`schedule.loops` with member blocks sharing a loop id)

- **Cause.** The assembled equations contain a simultaneous set: each
  equation's LHS is needed by another in the set — a Tarjan SCC. Not an
  error per se: it is a real algebraic loop requiring an iterative solve
  (`fsolve`) or tearing. State variables never produce this (states are
  sources — their values come from the integrator).
- **Remedy.** Decide how the loop is solved. Often a missing constitutive
  equation or a wrongly-assigned state causes spurious loops — check the
  loop members first. Genuine loops (e.g. recycle) get `fsolve`/tearing
  at codegen; the schedule already isolates them into a shared level.

## Artefact-validity problems

### `inadmissible-gesture`
**Message:** emitted by `graph_violations` — per-gesture text

- **Cause.** The model artefact contains a construct that violates a
  declared rule (e.g. a placement the entity type's capabilities don't
  admit, or content written bypassing the tool's gate). Reported rather
  than silently instantiated.
- **Remedy.** Fix the flagged construct in the owning tool — the message
  names the violation. If the rule itself is wrong (capability missing
  on the entity type), that's an ontology change, not a model change.

## Value-binding problems (§20 cells + fills)

`promo:ValueCell` tables and `promo:ValueFill` selectors supply parameter
and IC values (`docs/value-cells.md`, `docs/value-fill.md`). Fills
resolve to concrete cells at `plan()` time.

### `unfilled-cells`
**Message:** `<what> cells for <var> are not all filled — falling back to
a par lookup`

- **Cause.** A bound variable has a value table but at least one
  coordinate in its bound extent has neither a cell nor a matching
  fill — so no complete table exists to emit. The emitter falls back
  to a runtime `par[…]` lookup for the whole variable.
- **Remedy.** In the Instantiation app, fill the missing coordinates —
  a `*` or sub-index fill covers uniform slices in one stroke. Missing
  cells emit as `NaN` only when a partial table is emitted; an
  unfillable slot silently becomes a par input, so check the report
  before assuming the numbers you saw came from the table.

### `bad-fill`
**Message:** `<n> fill pattern(s) with the wrong axis count ignored`

- **Cause.** A `ValueFill`'s `promo:fillPattern` has a segment count
  different from the variable's index structure — the pattern can
  never match any coordinate, so it is ignored.
- **Remedy.** Fix the pattern in the Instantiation app — usually a
  variable gained or lost an index after the fill was authored.

### `fill-conflict`
**Message:** `<n> cell(s) covered by equal-specificity fill patterns
(first: <coord>) — resolve explicitly`

- **Cause.** Two fills of equal specificity score cover the same cell
  (e.g. `a1|*` and `*|s2` both reach `a1|s2`). The engine refuses to
  pick a winner — which value you get must be auditable.
- **Remedy.** Make one selector strictly more specific (a concrete
  cell beats every fill; a concrete segment beats a sub-index beats a
  `*`), or delete the redundant fill. Cross-artefact overlaps score
  the same way — provenance never decides.

## Code-plan problems

### `port-coverage`
**Message:** `<var> gathers <n> peer element(s) into <m> bound slot(s) —
contacts over-cover the slots | slots left unbound`

- **Cause.** A port gather supplies more or fewer peer elements than
  the variable's bound slot count — the plan cannot map contacts to
  slots one-to-one. The python emitter pads/truncates deterministically;
  the problem tells you the shape was off.
- **Remedy.** Check the topology around the port — usually an arc's
  sub-index membership or a port's bound extent changed after values
  or assignments were authored.

## Port-typing problems (§32)

Port variables bound on an entity type get typed by the mechanism that
carries them — inferred from the arc sub-index covering the entity's
contacts.

### `port-domain-unresolved`
**Message:** `no arc sub-index covers <etype>'s contacts — port vars
can't be bound-typed (§32)`

- **Cause.** The entity type has contacts but no mechanism sub-index
  covers them, so the port variables' carrier mechanism is
  undetermined.
- **Remedy.** Give the entity's contacts a mechanism — usually the
  transport entity type on the arc needs a `selector`-bearing
  sub-index, or the model is missing the transport node between
  capacities.

### `port-domain-ambiguous`
**Message:** `<etype>'s contacts are covered by several mechanism
sub-indices at equal depth — port vars need var↔mechanism pairing (§32)`

- **Cause.** More than one mechanism sub-index covers the same
  contacts at equal specificity — e.g. a boundary carrying mass and
  heat together. Coverage exists but cannot pick one mechanism.
- **Remedy.** Pair each port variable to its mechanism — the
  `promo:Mechanism` `drives`/`carries` vocabulary (§32 stage 2) is
  the designed slot; until it lands, split the boundary so each arc
  carries one mechanism.

## Occurrence-composition problems (§22/§33)

Referenced submodels (`refersTo`) merge their content into the host at
instantiation, keyed by occurrence path.

### `reference-cycle`
**Message:** `transitive self-reference at <comp>: <iri> is already on
the reference path`

- **Cause.** An occurrence refers (possibly transitively) back to an
  artefact already on its own reference path — a model referencing
  itself through a chain.
- **Remedy.** Break the cycle — dissolve the occurrence (one-way copy
  to in-doc content) or re-point `refersTo` to a different artefact.

### `species-port-mismatch`
**Message:** `occurrence <comp>: arc <a> species <list> not in <tag>
vocabulary`

- **Cause.** A boundary arc carries species (permeable/distributed
  set) that the host's or the referenced artefact's pinned species
  scheme doesn't declare — the occurrence's species vocabulary and
  the host's disagree across the boundary.
- **Remedy.** Pin a compatible species artefact (`usesSpecies` +
  occurrence override), or extend the host scheme with the missing
  components.

### `uncovered-override`
**Message:** `occurrence <comp>: override species artefact <iri> lacks
<list>`

- **Cause.** The occurrence's species-artefact override doesn't
  declare components the referenced submodel needs — the override
  narrows rather than covers the scheme.
- **Remedy.** Point the override at a scheme containing the listed
  components, or add them to the override scheme.

---

## Not yet emitted — expected kinds

Reserved for engines/stages under construction. Listed so the catalogue's
shape is stable before they land:

- **Meshing problems** — distributed-systems stage: unsupported geometry,
  boundary-condition gaps.
- **Mediated-flow violations** — when the §14 ruling (capacity↔capacity
  arcs unphysical, ruled 2026-11-10) gains role-level enforcement, its
  reports land here.
- **Codegen problems** — emitter-level failures beyond `port-coverage`
  (e.g. an index-set mismatch that cannot emit), currently raised as
  `VarError` rather than reported kinds.
