# Behaviour Linker — Implementation Status

**Last updated:** 2026-10-28

## Current state

§21 move-based engine implemented end to end (backend + SPA, 40
closure tests, full suite 421 green).  Design is resolved — see
`behaviour-linker-design-discussion.md` §1–21.

## Backend

`backend/behaviour/`:

- `closure.py` — pure-Python engine, no rdflib/FastAPI deps.
  Implements §8/§12/§13 plus the **§21 move semantics**
  (2026-10-28):
  - selection state = ordered equation `sequence` + `base_equation`
    (state-defining, pinned last; `None` for stateless entities like
    transport systems) + `instantiated` + `ports` + `outputs`;
  - **`apply_move(equations, selection, kind, …)`** — the only
    mutation channel.  Kinds: `pick_base` (select/unselect; unpick
    keeps the equation so the integrator loop surfaces as a reported
    cycle), `pick` (definer for a variable; replaces a previous
    definer = *exchange*, clears instantiated/port marks, keeps an
    output mark), `delete` (drops the equation + its exclusive cone),
    `mark`/`unmark` (endpoint roles, exclusive; marking
    instantiated/port drops the variable's definer), `reorder`
    (desired sequence as position hints only);
  - `_reclose` restores the closed-subgraph invariant after every
    move: drop unknown/dangling equations, prune everything outside
    the **root cone** — the base equation plus definers of declared
    outputs (stateless selections add their tips), pull in
    uniquely-definable definers (`pick`/`mark` only), then emit the
    stable topological order (base last, state edges exempt);
  - four endpoint kinds (§21): **state**, **instantiated**,
    **port**, **output** — an output is an external sink: its
    variable must be *defined*, its definer is a reachability root,
    and an unmatched output joins `unresolved` with `as_output`;
  - per-variable resolution, frontier suggestions, cycle check
    (integrator loop only), conflicts (incl. output+instantiated /
    output+port), order check — unchanged in kind, all recomputed on
    the reclosed selection by `evaluate`;
  - `unconsumed`: defined non-state variables nothing consumes and
    no output claims — dead code / pending output marks; they block
    `closed` (a stateless entity's outputs are its interface);
  - `closed` requires some work — a non-empty sequence, instantiated,
    ports or outputs — with no unresolved inputs, cycles, conflicts,
    order violations or unconsumed tips.
- `service.py` — FastAPI router (`/api/behaviour`):
  - `GET /context?graph=` — entity types (with scale values),
    equations (lhs + incidence), variables of the scoped var/expr
    graph;
  - `POST /evaluate?graph=` — read-only evaluation of a posted
    selection (+ `labels` map); not the mutation channel;
  - `POST /move?graph=` — applies a §21 move to the posted selection
    and returns `{selection, report, pulled, pruned}` — the SPA's only
    mutation channel;
  - `GET /assignment?entity_type=&graph=` — read the stored assignment
    (404 if none);
  - `PUT /assignment?graph=` — re-closes (a `reorder` move) then
    persists the canonical §13 artefact: `promo:BehaviourAssignment`
    resource with `forEntityType`, `hasBaseEquation`,
    `hasStateVariable`, `hasEquationSequence` (`rdf:List`,
    topological computation order, base last), `hasPortVariable`,
    `hasInstantiatedVariable`, `hasOutputVariable`, and a `closed`
    flag so work-in-progress selections can be saved;
  - `DELETE /assignment?entity_type=&graph=`.
- Assignment artefact graph: `{var/expr graph}/assignments`
  (`promo:Assignment` type; stamps the source graph's own
  `usesOntology` pins plus `usesLibrary` back to the source graph,
  2026-09-29); unscoped mode uses
  `https://w3id.org/promo/assignments`.  Created lazily on first PUT.
- `test_closure.py` — 40 tests: engine semantics + §21 moves
  (pick/exchange/delete cascade/mark-drop-definer/unpick-cycle/
  reorder/output demand/rooting/unmark prune/exclusivity) + endpoint
  roundtrips incl. `/move` reclosure and `hasOutputVariable`
  persistence.

`backend/instantiate/` (new, 2026-09-22) — §16 membership resolution:

- `resolver.py` — pure arc→sub-index resolution: token-flow arc joins
  every sub-index whose `selector` matches an incident node's entity
  type or a `promo:parent` ancestor (diffusion arc → `A_diff` +
  `A_mass`).  Reference arcs report empty membership;
  transport↔transport unions both ends.
- `service.py` — `GET /api/instantiate/arc-indices?graph=` returns
  per-arc membership + inverted `by_sub_index` map + the effective
  §15 `reference_from`/`reference_to` per arc; reads the model
  graph's `ModelNode`/`ModelArc` and the ontology across the
  artefact's resolution scope.
- `fbuilder.py` — §15 signed incidence matrices `F[N,A]`: sparse COO
  `(row, col, ±1)` — +1 at `reference_to`, −1 at `reference_from`
  (`F·f` = net inflow).  Base matrix over all token-flow arcs + one
  per declared arc sub-index, all sharing the full node row space.
  `GET /api/instantiate/incidence?graph=` serves them.
- `test_resolver.py` — 10 tests incl. a seeded-model endpoint test.
- `test_fbuilder.py` — 6 tests: sign convention, sub-index column
  restriction, reference-arc exclusion, dangling/self-loop edges,
  endpoint roundtrip.
- `builder.py` — §19 model instantiation (new, 2026-09-22): binds the
  model artefact to §13 assignments and emits the assembled equation
  set.  Index element sets (`N` = nodes, `A` = token-flow arcs,
  `A_k` = members, `N_T` per entity type); variable bindings
  (`incidence` for `constant`-class `[N,A]`-indexed vars → the
  numeric `F` matrices,
  `constant`, `parameter`, `port`, `local` with per-index element
  sets); per-contact port resolution across arcs — R3 rule: peer's
  defined vars with comparable token (`promo:parent` ancestry) minus
  the unflagged state, `port_variable` preferred among candidates;
  `tokenKind` carrier pre-filter; problem report
  (untyped nodes, missing/open assignments, unbound/ambiguous ports,
  unmarked inputs).  `GET /api/instantiate/model?graph=&vars=`
  serves the report incl. the incidence matrices.
- `scheduler.py` — §19 evaluation scheduling (new, 2026-09-22):
  dependency DAG over `(entity_type, equation)` blocks — intra-type
  edges from lhs→consumers, cross-type edges via bound ports;
  state vars are sources (integrator output, not the balance's
  product).  Output: `levels` (condensation-DAG depth — same level =
  parallelisable) + `loops` (SCCs = algebraic loops, reported as
  `algebraic-loop` problems).  Served on `/model` as `schedule`.
  Corollary: `base_equation` is the balance — stateless types
  declare none.
- `test_builder.py` — 23 tests: element sets, all five binding kinds,
  per-contact/scalar port resolution, R3 flag semantics (unflagged
  secondary state binds, flagged state exports, flag disambiguates),
  signal-token comparability, scheduling (linear chain, algebraic
  loop, unbound-port edge-freedom), problem kinds, endpoint
  roundtrip.
- **Index discipline (2026-09-22):** a variable's index structure is
  a fixed sequence of *unique* indices — the checker now rejects
  duplicates and preserves declaration order through the checked
  tree (`Checked.indices` was previously sorted, losing the declared
  axis order).  Element-wise ops require the same sequence, not just
  the same set.  This is the codegen axis convention: `F[N,A]` emits
  rows=N, cols=A, matching the fbuilder matrices.
- **Codegen (2026-09-22):** `plan.py` lowers report+schedule into a
  target-agnostic `CodePlan` (state layout, port gathers as index
  maps, incidence matrices restricted to bound elements, param/input
  slots, ordered blocks with rhs text, per-type emitted-name maps —
  shared var IRIs get type-suffixed names).  `emit_python.py` is the
  first emitter: NumPy derivative function (state unpack, gathers,
  `np.tensordot` balances, `dy` slices).  Targets agreed: Julia
  primary (Tullio/DifferentialEquations), NumPy baseline, Matlab
  legacy.  `EqInfo.rhs` carries the expression text; the `Renderer`
  takes a `names` override for per-instance identifiers.
- **Auto-instantiated endpoints (2026-09-22):** variables of a
  bound-value class (`INSTANTIATE_CLASSES` = constant/parameter) or
  carrying a pre-bound `promo:value` terminate the subgraph search
  without an explicit marking — the class is the ontology-level hint,
  per the hint/binding pattern.  `evaluate()` takes an
  `auto_instantiated` set (computed in `service._collect`); the report
  lists referenced ones under `auto_instantiated` with their candidate
  equations so the UI can offer an override.  Explicit resolutions win:
  a selected defining equation, an `instantiated` marking, or a `port`
  declaration all remove the variable from the auto set.  Auto vars are
  NOT persisted as `hasInstantiatedVariable` — the artefact records
  user bindings; class-based resolution re-derives from the ontology.

## Frontend

`apps/behaviour-linker/` — working SPA (React + Vite, dev on
:3003, `npm run dev:behaviour` / `./dev.sh start behaviour`):

- Sidebar: entity types with stored-assignment badges (closed/wip).
- Base-equation picker with two modes:
  - **with state** — all equations shown, state-class equations sorted to
    the top as hints; selecting any equation makes its LHS the state;
  - **without state** — unpicks the base (`pick_base(null)`); the
    integrator loop then surfaces as a reported cycle until deleted.
- Computation sequence list with ↑/↓ reorder, drag-drop, remove, and a
  per-row **out** toggle declaring the row's LHS an output endpoint.
- **All mutations go through `POST /move`** (serialized per client):
  every pick/exchange/delete/mark/reorder is a re-closure — the engine
  returns the canonical selection, and the UI flashes pulled/pruned
  equations.  Load normalizes legacy artefacts via a `reorder` move.
- **Suggested next equations** panel driven by the engine's `frontier`
  list: one-click addition of equations that resolve an open variable
  and stay inside the selected base cone.
- Unresolved-inputs panel: each unresolved variable offers its
  candidate equations plus "instantiate" and "port" markings;
  output demands are badged `(output)`.
- Roles panel (state / ports / instantiated / **outputs** with
  unmark; an **unconsumed** row offers one-click output marks),
  problems panel (cycles, conflicts, order violations, warnings),
  header open/closed badge + store-dirty badge + assignment-level
  **modified** badge + Save (PUT assignment, then store save) and
  Delete.
- **Printable representation** card: KaTeX-rendered preview of the
  current assignment, a **Print** button (opens a clean print window),
  a **Copy LaTeX** button, and an on-demand **Show source** toggle.
- `?graph=` session param honoured like the other apps.

## Design

Role is defined in ADR-004; the full mechanics are resolved in
`behaviour-linker-design-discussion.md` (§8 closure algorithm, §12
validation scope, §13 assignment artefact, §14 tokens/ports, §15
reference coordinates, §16 arc sub-indices, §17 scale regimes/seed
contract, §18 variable mutability, §19 model instantiation, §20
species allocation, **§21 admissibility** — designed 2026-10-27,
**implemented 2026-10-28**: the selection is a lower-triangular
sequence maintained by moves (pick / exchange / delete / mark /
unmark / reorder / pick base), each move re-closing the subgraph;
four endpoint kinds — state, instantiated, port, **output** (external
sink, reachability root, persisted as `promo:hasOutputVariable`);
`lhs_class` is a candidate hint, not a gate.  Delete semantics:
dependents reopen (no silent cascade through *consumers*); the
deleted equation's exclusive provider cone prunes.  Migration note:
pre-§21 artefacts may hold dead-code equations or lack output marks —
the first `reorder` (load or PUT) re-closes them; a stateless
assignment without output marks no longer reports `closed`.

## Pending items

1. ~~Frontend SPA~~ **Done (2026-09-22):** minimal guided-resolution
   UI live on :3003.
2. Graphical assignment interaction (Graphic Object Editor) — design
   exists, implementation not started.
3. Equation-eligibility hints from ontology (regime/scale filtering of
   candidate lists) — engine accepts any equation today.  **Superseded
   by §21 (2026-10-27):** candidate filtering is folded into the move
   semantics — offered expressions are those that keep the subgraph
   completable.
4. Port satisfaction check against connection rules (§14) — needs the
   Modeller-side arc check (ADR-008 deferred item).  §19 port
   *binding* is done (token + `port_variable` export); the missing
   half is the rule-direction check on connect.
5. ~~Fix marking (three-layer binding model, ADR-008)~~ **Done
   (2026-10-17):** `promo:fix` on `ModelNode` → `fixed` binding;
   modeller gesture via `GET /entity-variables`; instantiation artefact
   + pinned-plan codegen done the same day.
   ~~Instantiation proper~~ **Done (2026-09-22):** §19 report —
   `GET /api/instantiate/model?graph=&vars=` assembles the equation
   set: index element sets, variable bindings (incl. symbolic `F` →
   numeric matrices), per-contact port resolution, problem list.
   ~~Persisting an instantiation artefact~~ **Done (2026-10-17):**
   `promo:Instantiation` + pinned replay.
   ~~§21 admissibility~~ **Done (2026-10-28):** `closure.py` rewritten
   to invariant-restoring moves (`apply_move` + `_reclose`), output
   endpoint persisted (`promo:hasOutputVariable`), `POST /move`
   channel, SPA mutations serialized through it; downstream tests
   updated (donated vars now declare `outputs` — a stateless
   transport's exported flow is an output).
6. ~~§15 orientation capture~~ **Done (2026-09-22, modeller side):**
   `ModelArc.referenceFrom`/`referenceTo` persisted as
   `promo:referenceFrom`/`referenceTo` (token-flow arcs only);
   through-path default on insertion; right-click / `r` reverses;
   arrowhead follows reference direction; open arcs carry
   `refToExternal` across the composite boundary.  Entity-type
   `parent` now exposed via `/api/ontology/entity-types` →
   `BaseEntityDefinition.parentIri` for the is-transport check.
   F-builder done same day: `GET /api/instantiate/incidence` emits
   sparse `F[N,A]` per sub-index + base.
7. ~~UI polish~~ **Done (2026-09-29):** KaTeX rendering — `/context`
   returns server-rendered `lhs_latex`/`rhs_latex` (reusing
   `document.py`'s `_var_symbol`/`_rhs_latex`); SPA renders `lhs := rhs`
   as math with text fallback.  Sidebar entity-type filter box;
   drag-reorder on the sequence (drop = insert before target, ↑/↓
   buttons kept).  With/without-state base-equation picker; closure
   frontier suggestions; assignment-level modified indicator; printable
   LaTeX representation card with print/copy/source toggle.

## Dependencies

- Equation Editor backend (var/expr graph — consumed via
  `scoped_context`, honours `?graph=` pin scoping).
- Ontology (entity types, scale values, tokens, connection rules).
- Graphic Object Editor (shared component, not yet built).
