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

## State

- **581 backend tests pass**; consistency report 0 errors /
  63 consistent / 4 bound-scope on the library.
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
