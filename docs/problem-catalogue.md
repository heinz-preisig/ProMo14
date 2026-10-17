# Problem catalogue

**Status:** living document — started 2026-10-17. Add a section whenever
an engine starts emitting a new problem kind; keep `kind` strings
character-identical to the code that emits them.

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

---

## Not yet emitted — expected kinds

Reserved for engines/stages under construction. Listed so the catalogue's
shape is stable before they land:

- **`unfixed-input` / fix-marking violations** — when model-artefact fix
  marking (ADR-008 layer 2) is enforced rather than deferred.
- **Meshing problems** — distributed-systems stage: unsupported geometry,
  boundary-condition gaps.
- **Codegen problems** — unbound parameter slots reaching the emitter
  (currently surfaced as generic `problems` on `/code`, not kinds).
