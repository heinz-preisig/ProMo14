# Session handoff — 2026-11-11

## Start here next session

Read `design-principles.md`, especially §15, then discussion §36 in
`behaviour-linker-design-discussion.md`. The user's next requested design
conversation is **control token semantics**, not another physics rewrite.

The user clarified the distinction: equation definition/deletion rules
maintain consistency during construction, with lower-triangular structure
central; token associations cannot be enforced equally sharply, so explicit
consistency checking is necessary. Membership/signature separation is
settled, not reopened. Global checking belongs in the equation editor,
including feasible fixes with user confirmation.

## Delivered today

Earlier commit `1821f71` contains actionable token advisories, unified
foundation/dependent variable authoring, token key canonicalisation and
foreign-reference-based signature locks. Earlier ontology drives work is
in `4a268fb`.

The final session change adds:

- `backend/equation/consistency.py`: resolved-context audit using the
  existing parser/checker/advisory logic. Compares units, index IRI sets
  and token signatures, including explicit-empty LHS signatures. Reports
  missing LHS signatures and conflicting sum terms with operand details.
- `GET /api/equation/consistency?graph=...`: read-only whole-scope report,
  revision fingerprint, per-equation diagnostics and four summary states:
  error, advisory, untracked, consistent.
- `POST /api/equation/consistency/fix?graph=...`: accepts only a currently
  offered correction and current report revision; changes only tokenVector.
  Membership, units, indices and expressions are untouched. Checks editable
  owning graph, frozen resource/version status, membership availability and
  compatibility of alternative definitions. Never shadow-copies pins.
- `ConsistencyPanel` plus header **Check consistency…**: automatic initial
  run, category filters, variable/equation/owning-artefact navigation,
  operand definitions, conflicting terms and signature comparisons.
- Feasible signature corrections have an impact preview (in-scope
  transitive consumers, cross-artefact direct references), confirmation and
  full recheck. Context edits mark reports stale; backend rejects stale
  corrections independently. No blind bulk adoption or equation rewriting.
- Ruling recorded in discussion §36 and principles §15; equation-editor
  overview/status aligned.

## Current live audit snapshot at shutdown

Scope: `https://w3id.org/promo/library`, including pins. **38 equations**:
**2 errors, 3 advisories, 11 untracked, 22 consistent**. These categories
are exclusive: an advisory may also have an untracked token result.

| Equation | Variable | Finding |
|---|---|---|
| E_11 | d | Declared `[A_conv]`, derived `[A_conv,N]`; tokens untracked |
| E_29 | dmdt | Declared `[A_conv,N]`, derived `[N]`; declared mass/time versus derived energy/momentum |
| E_31 | y | `pGain . e` derives signal² versus declared manipulation |
| E_32 | e | `setPoint - obs` compares signal versus observation; result untracked |
| E_34 | c | Expression tracked, LHS signature absent; newly exposed by global check |

`G`/E_20 and `rhom`/E_37 now check cleanly. `rhom`'s stale inverse-mass
signature was corrected through the API after volume became neutral.
The user corrected `p_term` using the suggested-signature path. No remaining
physics equations or control declarations were rewritten by the assistant.
Do not mistake these diagnostics for authorisation to invent equations.

## Important persistence observation — inspect before cleanup

The final API save contains records for `p_term` and `V` under
`https://w3id.org/promo/library#V_10` and `.../library#V_23` in **both**
ontology and library graphs. The library scope resolves its own records
first (p_term energy signature; V explicitly neutral), while ontology
copies retain older signatures. References have also been rehomed in the
serialized output. This was observed, not repaired at shutdown.

Inspect graph ownership and the IRI migration/write path before deciding
whether these are unintended split records. In particular, compare
ontology-only and library-scoped checks; do not silently merge, delete or
hand-edit serialized TriG. A scoped report is not a cross-graph ownership
integrity audit. Serializer blank-node/order churn also makes raw data diffs
larger than the semantic edits.

## Open discussion / follow-up

1. **Control:** determine the intended algebraic meaning of signal,
   observation and manipulation memberships/signatures before changing them.
   The role-versus-quantity interpretation was raised but is not ruled.
2. **Transport diagnostics:** neutral coefficients propagate effort
   signatures rather than converting to flow signatures. Report the tension;
   do not automatically change dmdt to energy/momentum just to silence it.
   The index mismatches also need coordinated dependent-aware decisions.
3. **UI:** an unchecked token can retain a signature exponent that is not
   manually editable in the current picker. Suggested-signature Apply works,
   but the independent membership/signature editing surface still needs care.
4. Existing broader queues remain: §21 closure moves, §32 pairing consumer,
   and cross-artefact integrity. The global equation report does not implement
   those or certify model-bound port typing/assignment closure.

## Verification and operational state

- Full backend suite: **555 passed** (`uv run pytest backend/ -x -q`).
- Equation-editor frontend: **11 tests passed**.
- TypeScript/Vite production build rebuilt successfully.
- Live consistency endpoint exercised successfully against all 38 equations.
- `git diff --check` clean before final commit.
- Saved the live store using `POST /api/ontology/save`; shutdown status
  `dirty=false`, last saved `2026-11-11T17:33:42Z`. Never hand-edited TriG.
- This machine has system Node/npm under `/usr/bin`, not an nvm install.
  Build/test commands used `PATH=/usr/bin:$PATH /usr/bin/npm ...`.
- Services were left running; no restart or stop was needed. Refresh the
  equation editor to load the rebuilt bundle.
