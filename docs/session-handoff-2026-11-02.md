# Session handoff — 2026-11-02

## What was done

### Simple-system assignments — all closed, transport corrected

The library's three assignments are clean and live-closed:

- **environment** — `inst [p_mech]`, nothing else.
- **convection transport** — *stateless* event-dynamic form: `base=null`,
  `state=None`, sequence `[E_4]`, port `p_mech`, inst `F_conv`, out
  `fmc`.  `state` was previously `fmc` — wrong twice over (a flow
  variable can't be a state, and the transport models no capacity).
  The engine already accepts `base=null`; the hardcoded
  `state = lhs(base)` derivation simply doesn't fire.
- **lumped** — sequence `[E_29, E_30]`, base `E_30`, state `m`, port
  `fmc`, closed.

Housekeeping: deleted a stale `assignment_etype_lumped` artefact and a
dangling `V_13` instance of the deleted `k_conv`.

### §28 design decisions (doc appended)

- **Event-dynamic = stateless assignment shape**; regime switching is
  an artefact/assignment swap at model time — not parametric
  C→0 (algebraic-state/DAE machinery stays deferred).
- **Entity types already carry `temporal_type = event-dynamic`** — the
  no-accumulation signal exists; wiring it into closure is open.
- **Transport equations live on transport entities**; lumped owns
  balances over ports.  BL candidate visibility ("claimed by X") is a
  UI problem, not a prohibition.

### Modeller — four fixes (all tsc clean, bundle rebuilt)

- **Screenshot** wired: `stageRef` + `toDataURL({pixelRatio: 2})` →
  timestamped PNG download.
- **Token indication**: `fetchEntityTokens` walks each entity type's
  `promo:parent` chain to the `transport_system` child
  (convection → `mass`); token-flow arcs get a mid-arc label and a
  per-token stroke (mass `#2980b9`, energy `#e67e22`, selection red
  wins).  `source`/`target` on `resolve-connection` are *domain* IRIs
  — token reads off the incident transport node per §16, never the arc.
- **Margin-zone bug**: `insertNodeAt` had no clamp — creation clicks
  could place nodes in the ancestor/sibling render margins (Node_1 was
  stuck there; drag was already clamped, which is why it couldn't go
  back).  Both paths share `clampToPanel`.
- **Extent contract for the graphic designer**: `SceneNode.halfExtent`
  + `graphicalHalfExtent`/`entityHalfExtent` — constraints read the
  object's own bounds (derived from the graphical definition), so the
  clamp survives custom graphics with zero code changes.  Designer
  MUST declare a bounding box.

### Equation editor — UI + a checker fix

- Removed the dead `EquationList` panel (its × filtered session state,
  persisted nothing); enlarged the variable expand caret; added real
  per-equation delete (removes the record from the owning variable's
  `equations` map and saves); `DeleteVariableDialog` builds the
  deletion cone from `ownerIri` + `incidence_list`.
- **`checker.py`**: `Integral`'s `::`-bound integration variable is
  excluded from incidence (same precedent as `Instantiate`'s
  prototype); bounds stay.  `E_30`'s stored incidence refreshed via
  PUT.  221 equation tests pass.

## Findings (unfixed, by design)

- **`resolve-connection` matches domain pairs + tokens only** — all
  physical entity types share `domain_physical`, so env→env is
  licensed for token-flow by `rule_physical-same`.  "Token exchange
  needs a transport endpoint" can't be expressed → entity-role-aware
  rule schema needed (ontology data, not a gesture hardcode).  Also:
  the sync resolver's cache-miss answer `allowed`+`[]` shows a 'valid'
  hover before the authoritative answer lands.
- **Delete cone is single-artefact**: variable delete sees var/expr
  refs only; assignment endpoint refs are cross-artefact and invisible
  → dead IRIs possible (the `V_13` case proved it).  Proposed: a
  read-only integrity-audit view + delete-cone extension.

## Evening — instantiation solve chain (first live exercise)

The simple model's `t=0` solve was walked end-to-end.  Four machinery
bugs fixed along the way, one real semantic question left open.

### Fixed (all committed, 345 instantiate+equation tests pass)

- **`np.atleast_1d` → `np.ravel`** at every concat site in
  `emit_python.py` — value-cell tables keep their bound index shape
  (`A_conv[1]×N[1]` → `[[v]]`), `atleast_1d` left them 2-D and
  `concatenate` choked on mixed dims.
- **`service.py` `par` dict → `np.atleast_1d`** — JSON scalars became
  0-d arrays; port-gather fancy indexing `[[0]]` can't index a 0-d.
- **`codegen.py` Integral bounds → `np.asarray(x).item()`** — NumPy 2.x
  (venv is on 2.5.3) rejects `float()` on ndim≥1 arrays; `.item()`
  enforces scalar-ness on any size-1 shape.
- **Multi-peer port gather — the real bug.**  `plan.py` grouped a port
  var's contacts by `(etype, var)` and served ALL contacts from
  `pbs[0]`'s peer: the transport's `p_mech` emitted
  `V_34_environment[[0, -1]]` — `Node_3` isn't in env's 1-element
  field, `pos.get(el, -1)` returns the sentinel, Python reads `-1` as
  a valid index → `[p_env, p_env]` → `F@p = 0` → **zero flow,
  silently**.  Now: contacts batch into runs sharing a peer
  (single-peer ports keep the old single-gather shape); runs split at
  peer changes and emits concatenate siblings in contact order —
  `np.concatenate([env[[0]], lumped[[0]]])` → `[2, 1]`.  `gather_multi`
  added to the `emit_common` base + all three dialects (matlab
  `vertcat`, julia `vcat`); all gather emission sites dedupe by
  instance.
- **Client**: empty par inputs were silently dropped → `KeyError` on
  the server; the solve card now names missing pars before sending.
  FillAdder value field disabled until a key is set; small fonts +2px.

### Verified

`initial()` returns `y0 = [0.]` end-to-end (pars or cells for the
`V_34`s — both paths work now that gathers concatenate correctly).

### Open (needs user decision / next session)

- **`derivative()`/`outputs()` IndexError** — `fmc` is declared
  `A_conv[2]×N[1]` but `E_4`'s RHS produces a per-node value (`F@p`
  contracts the contacts → 1 element).  t=0 survived because `fmc` is
  an unknown there (both arc slots bound to the same value — the
  physically right "same flow on both arcs").  `derivative()` computes
  it → 1 element → the lumped's arc gather `[[1]]` fails.  Question:
  does a RHS whose index space is smaller than the LHS's **broadcast
  implicitly** over the missing index?  §29 in the design doc.
- **Value cells keyed by variable, not occurrence** — the three
  `p_mech` rows (env/transport/lumped) edit ONE shared `V_34` table;
  that's what makes the element-keyed gather work, but the Values card
  shows it as three independent-looking tables.  Also: `save cells` is
  replace-semantics on the shared table — a save from a cleared draft
  wipes it (cell state kept flipping during the session).  §29.
- **Gather `-1` sentinel** — `pos.get(element, -1)` emits a valid
  negative index when a contact's element isn't in its peer's field;
  should surface as a problem instead of silently aliasing the last
  element.  §29.

## Next

1. **Index-broadcast decision** (§29) then `derivative()`/`outputs()`
   → `Generate code` (julia target) → simulate.
2. §21 closure-moves rewrite remains the big queue item.
3. If the model is revisited: `promo:closed` flags were refreshed;
   stored `incidence_list` for `E_30` updated.

## Verify

- Backend tests: `uv run pytest backend/` — was green at wrap (equation
  suite 221 incl. the Integral fix).
- Modeller: `cd apps/modeller && npm run build` then hard-reload
  `localhost:8000/modeller` — the backend serves `dist/`, not source.
