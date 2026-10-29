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
2. **Pressure split** — `promo:P` is two pressures: thermodynamic
   (`−∂U/∂V`, mass token — current tag) vs momentum-flux effort
   (momentum token).  User leans to splitting into two vars;
   **notation undecided** — recommended: keep `promo:P`/`p`/`p` as
   thermo, add `promo:p_mech` (`p_mech`, `p_{\mathrm{m}}`) on
   `token_momentum`.
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
