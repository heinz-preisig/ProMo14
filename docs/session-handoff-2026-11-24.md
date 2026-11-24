# Session handoff — 2026-11-24

## Delivered

### §41 component fold — `v[C]`/`r[C]` consumer rewrites COMPLETE

The remaining item from the 2026-11-23 ruling is done: the scalar
component variables are folded into `[C]`-indexed vectors and every
consumer rewritten via the equation API (editor path, not data
migration — §41 ruling 6).

- **New variables** — `r` = `ontology#V_115` (network `physical`,
  `[N,C]`, `function:frame`, m) — *had* to live in the ontology:
  `E_3`/`Axy` is an ontology equation and the ontology has no pins,
  so a library `r` would be invisible to it.  `v` =
  `library#V_116` (network `macroscopic`, `[N,C]`, frame, m·s⁻¹,
  `carriesToken` mass+momentum — mirrors folded `vx`).
- **Definition** — new `E_v`: `v := ParDiff(physical!r,
  universe!t)` replaces `E_6`/`E_9`/`E_10` (deleted).
- **Rewrites** (14 total, all canonicalised):
  - `E_12`–`E_14` (`kConv{X,Y,Z}`), `E_15`–`E_17` (`kDiff{X,Y,Z}`),
    `E_23`–`E_25` (`kQ{X,Y,Z}`): scalar `v_i` →
    `reduceSum((physical!e_i * v), C)`.
  - `E_26`/`E_27` (`Axz`/`Ayz`) and ontology `E_3` (`Axy`):
    `r_i*r_j` → `reduceSum(e_i*r,C) * reduceSum(e_j*r,C)`.
    `E_3` was a consumer the 11-23 handoff didn't list.
  - `E_fKin`: `vx²+vy²+vz²` → `reduceSum(v*v, C)` — another
    unlisted consumer.
  - `E_fPot`: `fmc*g*r_z` → `fmc*g*reduceSum(e_z*r, C)`.
- **Deletions** — `E_6`/`E_9`/`E_10`, then `vx`/`vy`/`vz`
  (`V_36`–`V_38`), then `r_x`/`r_y`/`r_z` (ontology `V_14`–`V_16`).
  `/variables/{iri}/references` confirmed only the folded
  equations held them; `assignments.trig`/`model.trig` never
  referenced them (sequences carry only `E_4`/`E_29`).

### Mechanical notes for future API-driven rewrites

- Path IRIs must be URL-encoded — an unencoded `#` swallows the
  `?graph=` and yields the misleading "graph= is required" 400.
- `record.equations` is keyed by the equation's dict key, not its
  IRI fragment — match equations by `iri.endswith("#E_x")`.
- `PUT /variables/{iri}` is full replace: fetch the record from
  `/context`, mutate, resend.

### §47 quasi-steady lumped capacity — sibling etype + assignment LANDED

Both momentum regimes now live side by side (user ruling: stiff
integration is too costly on large models).  `etype_lumped_qss`
(`promo:parent etype_lumped` → `reaction_host` inherits) keeps the
same scale composition — mass/energy still integrate — but its
assignment drops `V_121` from `state_variables`.  `E_dPdt` stays in
the sequence and emits as an algebraic net-force block (support
reaction) with the §21 output tap.  Sequence/ports/instantiated
identical to the dynamic assignment; `closed=true`.  Author record:
`scripts/author_lumped_qss.py`.  Regression:
`test_qss_assignment_emits_balance_algebraically`.  Ruling: BL §47 +
design-principles §14 amendment.  Per-node mixing is free — type a
node `etype_lumped_qss` where the fast mechanical mode doesn't
matter.  Upgrade path once `fl` lands: `ΣF(v)=0` can determine `v`
(algebraic-loop solver exists).

### §48 content-of-state alias — `m := Integral(dmdt :: t in [to, t])` LANDED

The consistency report's lone error (`E_75: m := dmdt`, kg ≠ kg·s⁻¹)
was a deliberate-but-false record: the rate-named state slot carries
the content, so the runtime alias was right and the equation was not.
Fixed root-cause: `E_75` now records the running integral
(`eqclass_generic`; canonical is a `promolg:DefiniteIntegral`), and
`plan()` marks `DefInt(state :: t in [to, t])` blocks `alias_of` →
`render_rhs` emits the slot name instead of `quad_vec`.  Horizon
forms (`[to, te]`, archival `E_30`) keep quadrature.  Side effect:
`ic_targets` now surfaces `m` as an IC need — physically right
(`m(t0)` = the slot's `y0`), mild report noise until the t0 UI learns
the alias.  Consistency now **0 errors / 69 consistent /
6 bound-scope** (75 equations — the user authored ~8 since morning).
Regression: `test_integral_of_state_emits_slot_alias`.  Ruling:
BL §48 + design-principles §2 corollary.

## State

- **582 backend tests pass**; consistency report 0 errors /
  69 consistent / 6 bound-scope on the library.
- `./dev.sh save` persisted — `data/library.trig` and
  `data/ontology.trig` carry the fold (git-diff ~1.7k lines,
  mostly serializer churn).
- `design-principles.md` open-gaps bullet realigned (fold landed);
  header bumped to 2026-11-24.

## Open for next session

- ~~**Momentum `P[C]`**~~ — **landed same day**, two subjects per
  ruling.  Fluid mechanics (transport scope): `fP`/`v_str`/`fmom`
  `[A_conv,C,N]` port exports (`fP := e_align·σ·p·Ayz`,
  `v_str := e_align·kConvX·inv(ρ)·Σσp,X`, `fmom := fmc·v_str`).
  Mechanics (lump scope): `P`/`F_g`/`dPdt` + `v := P·inv(m)`,
  `P := m·v`.  `test_01` transport wired (5-eq sequence), `Node_2`
  declares `x`, python emit verified.  **Lumped balance landed:**
  `etype_lumped` carries `state_variables=[dmdt, dPdt]` (the slot
  is set-valued now), ports `fmc`/`fP`/`fmom`, sequence
  `E_m_def → E_F_g → E_dPdt → E_29`, `dPdt` marked output.
  Author record: `scripts/author_momentum_slice.py`.
  Lessons logged in §41's "Momentum slice" section: emit pairs
  axes by index **name** (X↔A_conv outer-product trap — `e_align`
  consumers stay X-typed), `v` can't go port (§18 lock → `v_str`),
  export `carriesToken` scopes port candidacy (`v_str` is
  momentum-only — mass-tokened it collided with the `fmc` port).
  Structural work that landed with it (§41 record): multi-state
  `state_variables`, identity-pairing at ports, vector port
  gathers as axis-takes (`Gather.map_index`/`peer_indices`).
- **`uvicorn --reload` footgun** — the backend watches the tree;
  `pytest`'s `.pyc` writes triggered a reload mid-session and wiped
  all unsaved authoring.  `./dev.sh save` after each meaningful
  store mutation, before running the suite.
- ~~**`X↔C` placement metadata**~~ — **landed same day**:
  `promo:alignedComponent` literal on `ModelNode` (element name,
  e.g. `"x"`), seeded `e_align [X,C]` binding `alignment` (the
  σ/`direction` pattern), `node_alignments` surfaced on
  `/api/instantiate/model`, problems `alignment-undeclared`/
  `-invalid`/`-ambiguous`, modeller doc round-trips the field.
  The pressure-drop force `reduceSum(σ·p_mech, X)` can now land
  on a `C` component.  Modeller affordance added same session:
  a `component_alignment` capability on `transport_system`
  (inherited by all transport types) gates a "Placement (X↔C)"
  selector in the Properties panel — `X ∥ x/y/z` or undeclared.
- **Dialog UX** — working per user, pending confirmation.
- **Standing queue** — §32 stage-2 pairing resolver +
  `promo:Mechanism` layer; §33 submodel reuse; §21 closure-moves;
  friction `fl` constitutive law (λ·(L/d)·ṁ·v²/2 now folds v² =
  `reduceSum(v*v,C)`); radiation `fRx`/`ahr`; cross-artefact
  consistency review; tensors `r:r'`/stress stay §42.

## PM addendum (2026-11-24)

### Landed

- **§49 Darcy friction law** — `fl` (V_109) keeps `port_variable`
  but computes: `E_fl = (half·lam)·((Lp·inv(dp))·(fmc·
  reduceSum(v_str·v_str, C)))`.  New `[A_conv]` instantiation
  params `V_123 lam` / `V_124 Lp` / `V_125 dp`; `E_fl` sequenced
  on the convection-transport assignment, `fl` joined `outputs`,
  params joined `instantiated`; `closed=True`.  Record:
  BL §49, `scripts/author_friction_law.py`.  Consistency
  0 err / 70 ok / 6 bound-scope (76 eqs).  The lump-side
  consumption (`al`/`dEmdt`/`dHdt` into an assignment) and the
  QSS `ΣF(v)=0` upgrade remain open.
- **`_Matlab.permute`** — last dialect gap closed; emits
  `permute((…).value, [p])` re-wrapped in the lhs's MultiDimVar
  labels.  `Dialect.permute(src, perm, indices, space)` — the
  new args feed the label re-wrap.  Regression:
  `test_emit_matlab_lhs_index_conformity`.  584 tests.
- **§50 mechanical balance wired** — `etype_lumped` gathers `fl`
  (+ `fWs`) and reads `dEmdt := amech + aw − al` as a diagnostic
  output (balances are readings, no new state).  New `E_P_int`
  on V_119 (`P := Integral(dPdt :: t in [to, t])` — §48 slot
  alias for P, needed by `v := P·inv(m)` for `fKin`); `r`
  (V_115) joined `instantiated` for `fPot`.  `closed=True`,
  77 eqs consistent.  Author: `scripts/author_energy_wiring.py`.
  `etype_lumped_qss` untouched — no P slot without the dPdt
  state; the QSS energy path waits on `ΣF(v)=0`.

- **§51 thermal/total balances wired** — `dHdt`/`dEtotdt` joined
  `etype_lumped` as diagnostic outputs (§50 pattern).  The feared
  "species layer" dependency dissolves at the port boundary:
  `fnc`/`fnd`/`fQx` are all `port_variable`, so the lump computes
  only `fhc`/`fhd`, the `F`-gathers `ahc`/`ahd`/`ahq`/`akp`, and the
  two readings — the species layer needed is the S-index *extent*
  (§20 distribution), not the species equations.  `h` (V_96) is
  `instantiated` property data — the EOS closure stays out.  Root-
  cause fix: `E_53` was `h := H·inv(n)` (dimensionally clean,
  physically wrong — `[N]` lump total ÷ per-species moles); now
  `h := ParDiff(H, n)`, matching `mu`/`Cp`.  `closed=True`,
  0 err / 71 ok / 6 bound-scope (77 eqs).  Author:
  `scripts/author_thermal_wiring.py`.  Regression:
  `test_thermal_balance_wires_species_legs_as_readings`
  (585 tests).  `etype_lumped_qss` untouched — `dEtotdt → akp →
  fKin → v → P` needs the absent P slot.
- **`ambiguous-port` on `fnc`/`fnd`** — the convection peer exports
  five flow-typed port vars, none declared as the species-flow
  pair: the §32 var↔mechanism pairing gap surfacing as designed.
  Resolution needs transport-side `fnc` export (`cac`'s upwind-`c`
  gather — §32 territory) or the pairing resolver itself.
- **Sequence IRIs ≠ dict keys** — assignment `sequence` matches
  equation *IRIs*: `E_61`→`#E_dHdt`, `E_62`→`#E_akp`,
  `E_66`→`#E_dEtotdt`.  Unknown IRIs silently drop the whole
  sequence field while ports/outputs/instantiated still apply —
  always verify `closed` after an assignment PUT.

### Repairs

- **§47 records had never persisted.**  The `e46d98f` data diff
  carries no `lumped_qss` triples — authored in memory, wiped by
  a `uvicorn --reload` before the first save.  Re-ran
  `scripts/author_lumped_qss.py` and saved; verified in
  `data/ontology.trig`/`assignments.trig`.
- **Sharper reload lesson:** `scripts/` is *inside* the watched
  tree — editing an author script itself reloads and drops
  unsaved store mutations (burned again this session, self-
  inflicted).  Batch mutations + save in one step, no source
  edits in between.
- **§48 fallout:** `E_m_def`'s integral binds `universe!t`
  (`V_11`), which no assignment instantiated — *both* lumped
  assignments evaluated unclosed (stored `closed` flags predated
  §48).  `t` is the solver's runtime integration variable →
  joined `instantiated` on `etype_lumped` and
  `etype_lumped_qss`; both `closed=True` now.

### Queue (revised)

§32 pairing resolver + `promo:Mechanism` (now blocking `fnc`/`fnd`
port resolution — see §51 note); **transport-side species-flow
export** (`fnc := cac·fV` on `etype_convection_transport` —
`cac`'s upwind-`c` gather is §32 territory); §33 submodel reuse;
§21 closure-moves; radiation `fRx`/`ahr`; QSS `ΣF(v)=0` upgrade
(v determined algebraically — now that `fl`/`v_str` exist);
cross-artefact consistency review; §42 tensors.
