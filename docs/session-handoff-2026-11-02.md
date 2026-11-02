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

## Next

1. **Instantiate the simple model → codegen → simulate** — first real
   exercise of the `state=None` transport path through `plan.py`
   (`state_variable` is `Optional` but the path is untested live).
2. §21 closure-moves rewrite remains the big queue item.
3. If the model is revisited: `promo:closed` flags were refreshed;
   stored `incidence_list` for `E_30` updated.

## Verify

- Backend tests: `uv run pytest backend/` — was green at wrap (equation
  suite 221 incl. the Integral fix).
- Modeller: `cd apps/modeller && npm run build` then hard-reload
  `localhost:8000/modeller` — the backend serves `dist/`, not source.
