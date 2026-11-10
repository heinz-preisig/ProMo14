# Session handoff — 2026-11-10

## Done — token membership + leaf neutrality (checker/editor)

Two linked changes landed; the second makes the first actually fire on
real equations.

- **Forced-membership auto-set** (`DependentVariableEditor`).  When the
  checked equation's derived signature has a *unique most-specific
  token* (`specificMember` — `promo:parent` ancestry drops strict
  ancestors, `component_mass` beats `mass`), membership isn't a choice,
  it's forced — `carriesTokens` auto-unions it via an effect keyed on
  the survivor IRI (once per distinct survivor; a manual uncheck
  doesn't retrigger).  `applyTokenSuggestion` reduced to adopting the
  signature vector only.  `TokenSection`'s "Suggested membership" Apply
  row stays as the fallback for `VariableDetailDialog` and manual
  vectors — deliberately no auto there (would silently mutate a
  variable on dialog open).
- **§4 leaf-neutrality ruling** (`checker.py::_leaf_tokens`).  An
  absent `tokenVector` no longer always means untracked:
  `promo:value`-bound vars (literal numbers — `half`/`one`/`zero` hold
  no classifications, kind projection can't see them) and bound-value
  kinds (`constant`/`parameter`, the `BOUND_KINDS` projection) resolve
  **verified-empty**.  Bearing kinds stay untracked — missing
  declarations remain loud (absorb rule preserved).  Effect: the cfV
  pattern `half·(F − d·|F|)·c` now derives `{component_mass: −1}` →
  auto membership.  User-ruled in-session ("0.5, 1, value etc would
  behave neutral — or not?").
- **`{}` persists** (`graph_store.add_variable`): `if tv:` dropped an
  explicitly-empty signature — now `is not None`, so *verified-neutral
  by declaration* is a storable third state (guard already tolerated
  it).  No editor UI produces `{}` yet — see residual gap.
- **`TokenSection` hint**: "token-neutral — no membership expected"
  suppressed when the signature (suggested ∪ manual) carries tokens —
  signature outranks the classification heuristic.
- **Docs**: `design-principles.md` §4 amended (untracked vs
  verified-empty vs explicit `{}`); this handoff.

## Status

- 535 backend tests pass (`uv run pytest backend/ -x -q`), incl. two
  new regressions: `test_check_token_neutral_operands_derive_signature`
  (cfV pattern → `component_mass^-1`) and
  `test_check_unclassified_operand_stays_untracked` (absorb still
  loud).  `@promo/equation-editor` dist rebuilt.
- Earlier today (same commit): signature-constrained membership +
  ancestry suggestion + write-path containment guard (af627d8).
- Data: `model-2`/`model-3` artefacts deleted in-app (store clean,
  `test_01` is the live model).  No unsaved state at handoff.

## Residual gaps / next up

- **`d` (`V_26`) untracked?** — cfV derives `component_mass^-1` only if
  every operand resolves.  `half` (value) and `F_conv` (seeded
  constant+parameter) are covered; `d` needs a `constant`/`parameter`
  classification or `promo:value`.  If the check still shows no Tokens
  line, classify `d`.
- **No UI for explicit `{}`** — an unclassified authored var that is
  genuinely token-neutral can't declare verified-empty from the
  editors (backend persists it).  Small affordance needed if it comes
  up again.
- **Advisory asymmetry** — an un-declared LHS var gets no
  signature-mismatch warning (guard is `lhs_var.token_vector`
  truthy) — by design; the auto-set + Apply covers the flow.
- Still queued from before: §33 submodel-reuse implementation, §21
  closure-moves rewrite, cross-artefact consistency review.
