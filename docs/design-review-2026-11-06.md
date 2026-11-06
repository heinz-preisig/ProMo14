# Design review — 2026-11-06

First run of `.devin/workflows/design-review.md`.
HEAD: `4f0619e`.  Range: inception → HEAD (first audit).

## Baseline

`uv run pytest backend/ -x -q` → **517 passed** (incl. the new §4
regression test; the two snap-Octave env failures recorded on
2026-11-04 no longer appear).

## Verdicts

| § | Principle | Verdict |
|---|-----------|---------|
| 1 | Semantics in ontology | **conforms** — mechanism/token names in backend appear only in docstrings/comments (`builder.py`, `resolver.py`, emit docstrings); no special-casing |
| 2 | Symbolic-only equations | **conforms** — 0 numeric literals in `promo:rhs` strings, 0 numeric leaf args in `rhsExpression`/`hasArguments` chains |
| 3 | Three-layer token model | **conforms** — 28 vars carry decls; `carriesToken ⊆ tokenVector` holds on all real data (0 violations); `promo:token` only on grouping types |
| 4 | Token neutrality | **DRIFT FOUND → fixed** — see below |
| 5 | Mass granularity | conforms — both `token_mass` and `token_component_mass` decls coexist as designed |
| 6 | Named graphs + pins | **conforms** — 8 graphs, all canonical IRIs; pin DAG acyclic (10 edges) |
| 7 | `.trig` via APIs | **conforms** — every named graph isomorphic to live store; `ontology` differs only by the expected §4 migration delta (self-heals on next save) |
| 8 | Algebraic indices | conforms — `E_29` rhs confirmed same-index form `reduceSum( ( physical!F_conv . fmc ), A_conv )`; sibling-contraction gap still open |
| 9 | Computed species | **conforms** — `species.trig` holds only scheme records (Component/Allocation/Reaction/Species); no hand-declared S/Q membership anywhere |
| 10 | RDFS only | **conforms** — zero `owl:` usage |
| 11 | Suite emits, user runs | **conforms** — `exec` only in `/initial` verification path (`service.py:1535`); `subprocess` only for pdflatex (`document.py`); `@spawn` refs are emitted Julia |
| 12 | Two-tier submodels | conforms — occurrence helpers exist (`emit_common`) but no occurrence-path var namespacing yet; gap remains open as recorded |

## Drift found & fixed

**`F_*` token declarations resurrected by floor seed** (§4).

- `df5c80d` (11-05) stripped `carriesToken`/`tokenVector` from all
  seven `F_*` records in `ontology.trig` — but
  `_seed_incidence_factors` (`backend/core/seed.py`) still *derived*
  the token from the selector's transport-system ancestor and wrote
  both predicates at every `load()`.  Floor seeds resurrect by
  design, so the strip was un-strippable; `4f0619e`'s save
  re-persisted them.
- **Fix applied:** token derivation removed; the exact-set pass now
  strips `carriesToken`/`tokenVector` outright — so pre-neutrality
  records self-migrate on next load+save (verified: live store drops
  exactly the 14 decls, everything else isomorphic).
- **Regression test:** `test_seed_incidence_factors` rewritten to
  assert neutrality; `test_seed_incidence_factors_strips_legacy_token_decls`
  added.
- **Lesson encoded in the principles doc** (new gap-list entry):
  floor migrations can silently re-implement superseded semantics —
  audits must cover the seed layer, not only data files.

## Gap-status changes

- All previously recorded gaps remain open: `E_29` sibling
  sub-index contraction, overdetermination check, occurrence-path
  namespacing, cross-artefact consistency review.
- Added to the list: `promo:Mechanism` vocabulary (§32 stage 2);
  seed-vs-ruled drift class.

## Doc refinements applied (mechanical)

- `docs/value-expression.md` was a **0-byte file** referenced by §2
  as "records the rejection" — the revert commit `e1ca09e` deleted
  its 123 lines and never wrote the record.  Repopulated as a
  rejection record (spec `faf9f73` → impl `5c02e28` → revert
  `e1ca09e` + rationale).
- §4 gained its *Encoded* line (seed enforcement + test).
- Open-gaps list extended with §32 stage-2 and the seed-drift class.

## Proposed (ruling-level) — none required

## Observations (not drift)

- No model currently pins `usesSpecies` — the §20 machinery is
  implemented but has no live consumer in data.
- Two pre-existing frontend test issues unchanged (buildScene dash
  assertion; ModelState `window` env).
- New token decls on authored vars (`token_entropy`,
  `token_component_mass` — V_35/V_47/V_48/…) are the intended §3
  content from the energy authoring, not drift.
