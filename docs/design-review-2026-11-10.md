# Design review — 2026-11-10

Second run of `.devin/workflows/design-review.md`.
HEAD: `a67f03f`.  Range: `4f0619e..a67f03f` (previous review
2026-11-06 at `4f0619e`; ~25 commits).

## Baseline

`uv run pytest backend/ -x -q` → **524 passed** (517 at last review;
+7 — incl. the two-occurrences regression test, phantom-overlay
tests, and the restored token-consistency data test).  No
environment noise observed.

## Verdicts

| § | Principle | Verdict |
|---|-----------|---------|
| 1 | Semantics in ontology | **conforms** — single docstring hit (`builder.py:427` "convection"); all token/domain knowledge read via `_token_taxonomy`/store |
| 2 | Symbolic-only equations | **conforms** — 0 numeric literals in `promo:rhs` across `data/*.trig` |
| 3 | Three-layer token model | **conforms** — token tests 11/11 green; `carriesToken ⊆ tokenVector` now holds on all persisted data after same-day backfill (`a67f03f`); `promo:token` on grouping etypes only (reaction, species, Work/Mass/Energy Transport); no token predicates on arcs |
| 4 | Token neutrality | **conforms** — zero token decls on `F_*`, `kConv*`/`kDiff*`/`kQ*`, `Axy`/`Axz`/`Ayz`, `const_*`; §4 seed-strip migration holding |
| 5 | Mass granularity | conforms — untouched in range; `token_mass` + `token_component_mass` coexist as designed |
| 6 | Named graphs + pins | **conforms** — 8 graphs, canonical IRIs; pin DAG acyclic (12 edges: models→library+assignments+ontology[+species]) |
| 7 | `.trig` via APIs | **conforms** — all graphs isomorphic file↔live except `model-2` (+17) / `model-3` (+1), whose deltas are live-only vocabulary self-declarations (`a rdf:Property`/`rdfs:Class` stamps); self-heals on next save |
| 8 | Algebraic indices | conforms — `E_29` still same-index `reduceSum((physical!F_conv . fmc), A_conv)`; sibling-contraction gap remains open |
| 9 | Computed species | **conforms** — no hand-declared S/Q membership in model artefacts |
| 10 | RDFS only | **conforms** — zero `owl:` usage |
| 11 | Suite emits, user runs | **conforms** — `exec` only in `/initial` verification (`service.py:1760`); `subprocess` only pdflatex (`document.py`) |
| 12 | Two-tier submodels | **gap-status-changed** — occurrence-path namespacing landed (`28b0b2a`); `refersTo` still `usesModel`-derived + read-only in-place; nothing merges referenced graphs |

## Drift found & fixed (this range, same-day)

- **`data/library.trig` token drift** — six control-domain vars
  (`e`/`obs`/`pGain`/`setPoint`/`y` missing `tokenVector`; `V_60
  value` missing `carriesToken` entirely) — pre-dated the
  tokenVector enforcement; repaired via store+save in `a67f03f`
  with the natural single-token signature `{t:1}`; `V_60` took
  `token_signal` (generic numeric port).  This is the
  seed-derived-vs-ruled drift class already on the gap list —
  these vars were authored by the equation editor before the
  vector predicate was enforced.
- **`_pinned_plan` undefined** — `?instantiation=` replay on
  `/code`, `/initial`, `/code/export` called a missing helper
  (latent `NameError`).  Implemented in `28b0b2a`: peels
  `#`-fragments until `promo:plan` resolves (artefact IRIs carry
  `#`; sub-plan subjects extend it), so `…#occ_N` sub-plan replay
  works standalone.  Verified end-to-end incl. `#occ_0`.

## Benign deltas (no action)

- `model-2`/`model-3` file↔live deltas are vocabulary
  self-declaration stamps only — flush on next app save.

## Drift hunt (range diffs)

- `14d6aff` phantom terminals + `2929a68` variable-creation unify:
  token knowledge via `_token_taxonomy`/store reads — no
  hardcoding.
- `data/*.trig` commits in range are all API-mediated saves
  (persist model-2, §4 ontology save, tokenVector backfill).
- No numeric literals, no arc tokens, no model-executing paths
  introduced.

## Gap-status changes

- **Occurrence-path namespacing: open → landed** (`28b0b2a`,
  recorded §12/§22 Option A).  New regression test
  `test_two_occurrences_of_one_submodel` covers disjoint identity,
  qualified inner arcs, bound ports, emitted-name distinction, and
  two populated sub-plans.  Remaining caveats already recorded:
  shared-`var_class` constant dedup; conservative aggregated port
  edges can tag a spurious shared loop on an acyclic occurrence.
- All other open gaps unchanged: `E_29` sibling contraction,
  `V_34@ct` double-bound port (still listed under §32 stage 2
  vocabulary), overdetermination DOF check, cross-artefact
  consistency review, §33 machinery, `_Matlab.permute`.

## design-principles.md edits

**Applied (mechanical):**

- §12 gap item: corrected the emitted-name example — the tag is
  the composite-IRI fragment chain (`c_2_V_5`-style), not a
  "Composite_N" label; noted `#occ_N` sub-plan replay via
  `?instantiation=` is live (`_pinned_plan`).
- §3 rules: recorded that `carriesToken ⊆ tokenVector` is also
  enforced on persisted data by `test_data_variable_token_consistency`.
- §7: noted the benign live-only vocabulary-stamp delta class
  (self-heals on save).

**Proposed only (ruling-level — user decision):**

- **Write-path token guard** — default `tokenVector` to
  `{carriesToken: 1}` when a var declares membership without a
  signature, and 400 `portVariable` writes lacking `carriesToken`.
  Would make today's drift class impossible rather than caught;
  it is an enforcement behaviour change, so it needs your ruling.
