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

## State

- **576 backend tests pass**; consistency report 0 errors /
  63 consistent / 4 bound-scope on the library.
- `./dev.sh save` persisted — `data/library.trig` and
  `data/ontology.trig` carry the fold (git-diff ~1.7k lines,
  mostly serializer churn).
- `design-principles.md` open-gaps bullet realigned (fold landed);
  header bumped to 2026-11-24.

## Open for next session

- **Momentum `P[C]`** — the natural §41 follow-on (§41 ruled:
  momentum is `[C]`-indexed, per-component conservation).  No
  momentum balance is authored yet; `fmom = fmc·v` elementwise
  over `C` is now spellable, and the X↔C seam below supplies the
  component landing for forces.
- ~~**`X↔C` placement metadata**~~ — **landed same day**:
  `promo:alignedComponent` literal on `ModelNode` (element name,
  e.g. `"x"`), seeded `e_align [X,C]` binding `alignment` (the
  σ/`direction` pattern), `node_alignments` surfaced on
  `/api/instantiate/model`, problems `alignment-undeclared`/
  `-invalid`/`-ambiguous`, modeller doc round-trips the field.
  The pressure-drop force `reduceSum(σ·p_mech, X)` can now land
  on a `C` component — remaining gap is the modeller UI affordance
  for declaring placement (field persists via `PUT /model`).
- **Dialog UX** — working per user, pending confirmation.
- **Standing queue** — §32 stage-2 pairing resolver +
  `promo:Mechanism` layer; §33 submodel reuse; §21 closure-moves;
  friction `fl` constitutive law (λ·(L/d)·ṁ·v²/2 now folds v² =
  `reduceSum(v*v,C)`); radiation `fRx`/`ahr`; cross-artefact
  consistency review; tensors `r:r'`/stress stay §42.
