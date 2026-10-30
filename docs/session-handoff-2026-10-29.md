# Session handoff — 2026-10-29

## What shipped today (commits `7009d67`, `4fb2628`, `a78a975`)

### Port satisfaction at connect time (§13/§14, done)
- `GET /api/modeller/port-satisfaction` — advisory per-side port demands;
  statuses `satisfied` / `ambiguous` / `unbound` / `unlicensed`.  Pure
  adjudicator `backend/instantiate/satisfy.py` shares `readable_vars` +
  `_comparable` with the builder — satisfy never imports builder.
- Modeller connect gesture renders per-port status; carrier narrowed to
  the selected arc type when that type is valid for the pair, else union
  over licensed carriers.  Feedback is **advisory — never gates** the
  connection.
- Same-source and peer-port read explicitly as `unbound`, not
  `unlicensed`.

### §15 direction-aware donors (done)
- Chained donor selection for **carried (token-indexed) ports** donates
  upstream only: same-var downstream candidates excluded, upstream node
  transits or self-supplies, direction from `reference_from` (fallback:
  source).  Contact quantities (flows, efforts — non-token-indexed)
  remain direction-blind.
- Regression: `test_chained_port_follows_reference_direction`
  (builder.py `S_DIR_TOKENS` = tokens whose IRI path contains
  `#token_`).

### Interface contract removed
- §10's `EntityInterfaceDefinition` / `getInterface()` deleted from
  `packages/semantic` — never populated, no callers, and ports are
  assignment-scoped, not ontology catalogue data.  Real interface
  surfaces: `port-satisfaction` (BL ports) + §22 open-arc terminals.

### Token model (§23 — new, canonical doc section)
- Three levels: rule `matched_tokens` (may flow), implicit mechanism
  tokens (what transport moves), `promo:carriesToken` on the variable
  (what it *is*).  Arcs carry no token declaration.
- `carriesToken` is what makes a port licensable — the `promo:c`
  `unlicensed` case surfaced this live.
- **Tagging convention settled**: `U(S,V,n,…)` fundamental relation
  names the networks — `S→entropy`, `V→mass` (space tied to mass,
  `p·V` work pair), `n_i→component_mass`, `U/T→energy`,
  `r_*`/`Axy→momentum`; secondary vars ride their network's token;
  non-token vars (flags, times) carry none.
- Sweep applied to seeded data: 26 vars tagged (`4fb2628`).
  Untagged deliberately: `d`, `t`, `te`, `to`.

### Infrastructure / data
- `dev.sh` backend start polls `/api/health` (≤30 s) instead of a
  fixed 1 s race — no more false "backend failed".
- `data/model.trig`: `test_01` pins `promo:usesAssignment library/assignments`.
- `data/library.trig`: `promo:c carriesToken token_mass`.
- `ValueFill`/`fillPattern` vocab landed in ontology + species via
  floor migration on restart.

## Open threads (priority order)

1. **§22 referenced composites** — main feature; core (persistence,
   extract/dissolve, per-occurrence instantiation, call-style codegen,
   level-parallel emission, cone-blocked loops) committed.  Remaining:
   ordinal-aware Jacobian, sub-plan/Instantiated pins provenance
   (`§22-pending`), interface-summary in library pick, bundle render,
   gas/pipe+regen on real assignments, cross-artefact review.
2. **Pressure split — DONE 2026-10-30** — `promo:P` retired;
   `promo:p_term` (`p`, `token_mass`, `−∂U/∂V`, V_10) vs
   `promo:p_mech` (`p_mech`, `p_{\mathrm{m}}`, `token_momentum`,
   V_34).  Symmetric naming (user decision) — both roles explicit.
   Rewired: ontology `E_4`, library `E_11`/`E_15` rhs+incidence+expr
   args → `p_mech`; `E_2` lhs → `p_term`; assignments: convection
   port + environment → `p_mech`, lumped state → `p_term`.
   **Molecular dual-role noted**: EoS/`−∂A/∂V` → `p_term`;
   virial/stress-tensor-trace → `p_mech`; equality is an explicit
   equilibrium bridge equation, not a definition.
   **Token algebra — IMPLEMENTED 2026-10-30 (§24)**:
   `backend/equation/tokens.py` (`TokenVec` sparse exponent map,
   product/quotient/inverse/sqrt; `None` = untracked, absorbs),
   `promo:tokenVector` JSON literal on variables (read in
   `rdf_context`, persisted in `graph_store`, `VariableIn`/
   `VariableRecord` fields, structural-guard field).  Checker
   propagates alongside units: products add, `ParDiff`/`TotalDiff`
   subtract, sums/`maxmin` require equality (mismatch → warning,
   result untracked).  `CheckResponse.tokens/tokens_pretty/warnings`;
   `/check` compares computed vs LHS-declared signature (warning,
   never a gate) via `_token_advisories`; `{}`-collapse warns
   "basis change, not a relation" (same-information rule);
   `EquationRecord.warnings` carries advisories through the
   `_canonicalise_equations` save path.  New basis token
   `token_time` (`tokenKind "basis"`
   — never in carriesToken).  Port rule settled: `carriesToken`
   stays definitional for licensing; every declared token must have
   a *nonzero* exponent in `tokenVector` (extensive ports +1,
   intensive ports like `c=n/V` −1); effort·flow = energy·time⁻¹
   conjugacy invariant.  **Sweep done 2026-10-30**: all
   `carriesToken`-tagged vars in ontology+library now carry
   `tokenVector` — states `{tok:+1}`; rates `dmdt`/`dndt`/`fm_conv`/
   `fV`/`fn_conv` `{tok:+1,time:−1}`; efforts `T`/`p_term`/`p_mech`
   `{energy:+1,net:−1}`; ratios `c`/`c_conv` `{component_mass:+1,
   mass:−1}`, `Mm` `{mass:+1,component_mass:−1}`.  Deliberately
   untracked: `rho` (m/V → `{}` token-neutral), `k_conv` (derived
   conductance, signature undecided).  Tests: `test_tokens.py`.
   Follow-ups done 2026-10-30: equation-editor token picker
   (VariableDetailDialog — carriesToken checkboxes + per-token
   exponent inputs via `/api/ontology/tokens`; ResultPanel shows
   `tokens_pretty` + warnings).  Flag fixes: `t`, `Mm`, `k_conv`
   → `portVariable false` (`t` was frame-class with no token;
   `Mm`/`k_conv` are parameter/transport — never ports; removes
   the `p`-port `ambiguous ← k_conv, n` supply collision).
   Additive exemption (§18): declaring carriesToken/tokenVector
   on a previously untracked referenced var is no longer a
   structural change; altering existing declarations stays
   locked.  Decision: `EquationRecord.warnings` stays transient
   (editor-time only) — not persisted, not wired to `/model`;
   revisit when `/model` gets a validation pass.
   **Density/fraction rule (user, 2026-10-30)**: normed by volume =
   density → space token at −1 (`c` = `{component_mass:+1,
   mass:−1}`).  Generalised: *any quantity normed by its own
   network's extent collapses to `{}` (token-neutral)* — `ρ=m/V`
   `{mass:+1,mass:−1}`, mole fractions `x_i=n_i/n_tot`
   `{component_mass:+1,component_mass:−1}`.  Mean molar mass
   `M̄=m/n_tot` keeps `{mass:+1,component_mass:−1}` — species
   resolution lives in `idx_species`, not the token.  **Open
   question — `token_space` basis element?** `V→mass` tagging makes
   `ρ` and `p·V` degenerate in token space (`energy·mass⁻¹·mass`);
   a separate space token would restore information (`energy·
   space⁻¹·space`, `ρ={mass:+1,space:−1}`).  Decide when molecular/
   spatial modelling needs it — not now.
   **Same-information rule (user, 2026-10-30)**: density may NOT be
   modelled as `f(concentration)` — `c` and `ρ` are the same degree
   of freedom in two bases (`{component_mass·mass⁻¹}·{mass·
   component_mass⁻¹}={}`); the equation is a representation change,
   not a relation, and creates a spurious causal edge.  Correct:
   `ρ = M̄(x)·c_tot` — composition via fractions is genuinely
   different information.  Checkable corollary (not yet wired):
   warn when an equation's combined token signature collapses to
   `{}` while linking vars of the same network family — a basis
   change masquerading as physics; representation conversions
   belong to the instantiation/binding layer, not equations.
3. **Export-flag review** — post-sweep, `p`'s port reads
   `ambiguous ← k_conv, n`: unflagged token-comparable vars are
   candidate supplies.  Flagging the real exports disambiguates (R3).
   Related oddity: `t` (time) is `portVariable true` — probably wrong.
4. **`carriesToken` required for `port_variable`?** — §23 open policy;
   leaning required at authoring time (equation editor validation).
   Also whether *adding* a token where none existed should be exempt
   from the §18 structural-field guard — today it needs a file edit.
5. **Signal direction check** — §14 pending item 4: observation vs
   manipulation subtoken vs rule direction.
6. **Cross-artefact consistency review** (deferred).

## Verification

- 26 semantic tests, 20 satisfy tests, builder tests pass; modeller
  `tsc` clean.
- Live check (backend running): convection→lumped port-satisfaction
  returns `c` satisfied; `p`/`c` ambiguous on the convection side
  (supply flags pending — thread 3).

## Conventions worth remembering

- `.trig` edits: direct file changes + `./dev.sh restart backend` when
  the §18 structural-guard blocks the API path.
- Test invocation: `uv run --with pytest --with httpx -- pytest
  backend/... -x -q` (see CLAUDE.md).
