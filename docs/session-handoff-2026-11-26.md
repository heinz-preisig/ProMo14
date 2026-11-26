# Session handoff — 2026-11-26 (charge_02 codegen + port closures)

Six commits, `2dea1ef` → `e120f7b`.  Suite 592 green; store
saved; tree clean at `e120f7b`.  `charge_02` emits **0 problems**
in python/julia/matlab — the DL pair is fully wired.

## Landed

**Emit re-parse fix** (`8348338` — the blocking bug):
`promo:rhs` text is scope-relative to the equation's authoring
network.  Codegen re-parsed every block under a blank
`expression_definition_network`, so a same-label var in another
in-scope network ambiguated bare refs (model-charge-2: `r` in
E_50 hit `physical!r` vs `reactions!r`).  Now
`EqInfo.network` → `PlanBlock.equation_network` → `render_rhs`
builds a per-block `CompileSpace` with the equation's network +
the context `network_tree` — the same convention persistence
regen/document/consistency already used.  Regression:
`test_render_rhs_uses_equation_network`.

**In-flight recovery** (`9a90840`, `2dea1ef`): flat-position
port gathers (contact pins arc axis AND peer-node axis),
arc-indexed port candidacy restriction, species index
discriminated by `token_component_mass`.

**charge_02 port closures** (`96738e8`, `e120f7b`):
- Feed contact (Arc_9): env assignment instantiates `mu_el` —
  env is the boundary, same channel as `Ue`/`p_mech`.
- DL-metal contact (Arc_4): dl_metal defines `Ue` via existing
  `E_Ue_cap` (`Ue := inv(Cel)*qel` — same rhs as `E_phi`) in
  sequence+outputs → lead2's `Ue` effort port binds by
  **identity** (`w_iri == v_iri` skips all token/effort/drive
  filters).  phi stays `token_signal`-only — §57 intact.

**Guard amendment** (`e594af2`, **flagged for design review**):
`_structural_changes` token exemption widened from
untracked-only to any pure addition (new ⊇ old).  Pure adds
remove nothing — they can only widen port candidacy, which
surfaces as Problems not silent corruption; removals/replacements
stay locked.  Test: `test_added_token_membership_exempt_when_referenced`.

## Traps hit (don't repeat)

- **Port demand surface derives carrier-kinds from the port
  var's own tokens.**  A dual-membered port var claims contacts
  of *all* its token families — `phi += token_charge` bound
  Arc_4 but made dl_elyte's phi port demand an effort at the
  ionic contact (Arc_5).  §57's signal-only ruling guards the
  *demand* side too, not just supply.  The token-free channel
  is identity: give the *peer* the same var rather than making
  the demanded var more visible.
- **Removing a membership is locked while eq-referenced.**
  The revert needed the E_eta dance: rewrite the referencing
  equation's rhs to drop the var (incidence regenerates →
  unlocks), edit the var, restore verbatim.  Legal, preserves
  the equation's IRI/canonical form, but churn.
- **Env instantiations emit unconditionally per env node** —
  adding `mu_el` to the shared env assignment made
  charge_01/test_01 require `par["V_139"]` at run time
  (consistent with the `V_34`/`V_133` pattern, but a real
  param-contract change for those callers).
- Backend reloads on *any* `backend/` write including tests —
  API calls 500 during the reload window; retry after
  `built_at` advances.

## Design questions parked for review

- **Demand-surface scoping**: should a multi-membered port var
  restrict its demand to one carrier kind (the arc families its
  port actually rides), or is the warn-and-pad behaviour the
  intended contract for "demandable but unsupplied" contacts?
- Should the identity bridge (`Ue := inv(Cel)*qel` on dl_metal)
  be the *pattern* for phase-boundary effort handoff, or does
  §57 want phi-style shared interface vars with a different
  port-read mechanism?

## Next (in order)

1. `Pel` transport-side bound-scope — `X ↔ A_el` join gap,
   §32/§45 family (authored, unwired).
2. `G = κ·(Ae/L)` geometry leg for ionic conductivity.
3. `unfilled-cells` ×2 on test_01 (pre-existing, unrelated).
4. Electrode etype — first real §32 pairing consumer.

## Machine notes

`data/*.trig` is tracked — `git pull` on the other machine,
restart backend, **no wipe-restart**.  `./dev.sh sync` builds
apps.  Authoring scripts: `scripts/author_dl_port_closures.py`
(env pin; phi step annotated superseded),
`scripts/author_dl_ue_bridge.py` (the identity bridge).
