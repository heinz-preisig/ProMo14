# Design review — 2026-11-22

Third run of `.devin/workflows/design-review.md`.
HEAD: `a0b914b`.  Range: `a67f03f..a0b914b` (previous review
2026-11-10 at `a67f03f`; 58 commits).

## Baseline

`uv run pytest backend/ -x -q` → **574 passed** (524 at last
review; +50 — σ-machinery, flow-port, consistency, checker and
instantiate tests).  No environment noise observed.

## Verdicts

| § | Principle | Verdict |
|---|-----------|---------|
| 1 | Semantics in ontology | **conforms** — all hits docstrings/`emit_matlab` names/seed/tests.  `index_source` literals (`node`/`arc`/`coordinate`) in `checker.py`/`consistency.py` read the ontology-seeded alias — the §45 channel by design |
| 2 | Symbolic-only equations | **conforms** — 0 numeric literals in `promo:rhs` across `data/*.trig` |
| 3 | Three-layer token model | **conforms** — `promo:token` only on grouping etypes + `idx_species`; zero token predicates on arcs; `carriesToken ⊆ tokenVector` holds where vectors exist (inactive metadata since §3's 11-12 amendment); `fWs` authored `{"energy":1}` |
| 4 | Token neutrality | **conforms** — zero token decls on `F_*`/`k*`/`Axy`-`Ayz`/`const_*`/`d` (live-store scan); F_work token-free |
| 5 | Mass granularity | **conforms** — untouched in range |
| 6 | Named graphs + pins | **conforms** — 7 graphs (`model-3.trig` deleted in `2b7ca87` purge); pin DAG acyclic (model-2→ontology+library+species+assignments; model→ontology+library+assignments; library/species/assignments→ontology) |
| 7 | `.trig` via APIs | **conforms** — all graphs isomorphic file↔live except `library` **+3/−1**: the §40 load migration re-canonicalised `E_aw`'s rhs (`F_work` → `physical!F_work`) and minted `internalID` `E_60`/`E_61`.  Semantically equivalent; self-heals on next save |
| 8 | Algebraic indices | **conforms** — `E_29` still same-index (`F_conv * fmc`); gap open.  New machinery in range: `reduceSum`/`Product` explicit contractions (`cb914a2`), `promo:elements` + `idx_component` (`8af3b1f`, `5a306bd`), bound-scope status (`e354ac9`), §45 + narrowing (`ad3124b`, `f6ede7d`) |
| 9 | Computed species | **conforms** — `promo:member` hits only in the `species` artefact (Allocation records — its purpose); nothing in `model*`/`assignments` |
| 10 | RDFS only | **conforms** — zero `owl:` usage |
| 11 | Suite emits, user runs | **conforms** — `exec` only `/initial` (`service.py:1775`); `subprocess` only pdflatex (`document.py`) |
| 12 | Two-tier submodels | **conforms** — `refersTo` read-only in-place; nothing merges referenced graphs; occurrence-path remaining bullets unchanged |
| 13 | Leaf-bound arcs | **conforms** — untouched in range |
| 14 | Transport-mediated flows | **conforms** — `requiresMechanism` constraint landed in range (`b53049a`); compat callers still skip (documented) |
| 15 | Construction + global checks | **conforms** — report gained `bound-scope` status (still read-only, units compared everywhere) |
| 16 | Unidirectional signals | **conforms** — untouched in range |

## Drift / observations

- **`index_source` value set is now load-bearing shared vocabulary**
  between `seed.py` (writes the aliases) and
  `checker.py`/`consistency.py` (compare `== "node"|"arc"|"coordinate"`).
  Legal by the §45 design — declared data, not code constants —
  but the value set is undocumented as an enum.  Candidate for a
  seeded vocabulary note; not a violation.
- **`.trig` live↔file delta on `library`** — the §40 load-time
  migration rewrites `promo:rhs` to canonical network-qualified
  source and mints `internalID`s; authored spelling stays in the
  file until next save.  Same benign class as prior reviews'
  vocabulary self-declarations, now with *content* deltas — worth
  remembering when diff-reviewing a snapshot that followed an
  equation write without a reload.
- **`model-3.trig` deleted** — `2b7ca87` "purge stray variable
  records" cleaned the artefact; intentional, documented in the
  commit.

## Living-docs realignment applied

- `equation-editor-overview.md` — gained the §45 contraction
  restriction + `reduceSum(σ * effort, X)` spelling in the language
  section; realignment date bumped to 2026-11-22.  (Bound-scope was
  already documented there.)
- `concepts-and-architecture.md`, `worked-example.md` — checked, no
  contradiction: no through-drop/contraction spellings shown;
  §4.1 reference-directions text already current.
- `problem-catalogue.md` — coverage test green; `flow-uncovered`
  entry added in range (`6f4f061`).

## Gap-status changes

- **NEW open gap: component-selection convention** (§41/§42) —
  `promo:elements` + `idx_component C={x,y,z}` landed; the language
  still cannot name one element of a `C`-indexed variable, so
  `v_x`-style scalar consumers and `[C,C']` geometry folds stay
  unfolded.  Recorded in `design-principles.md` open gaps.
- `E_29` sibling sub-index contraction — unchanged (still avoided
  in data).

## `design-principles.md` edits

**Applied (mechanical):**
- Header realignment → 2026-11-22.
- §8 gained the §45 ruling (bare-linear incidence-factor node-axis
  ban + upwind exemption + structural detection + bound-scope
  backstop).
- Open gaps: added the component-selection-convention entry.

**Proposed (ruling-level, not applied):**
- **Library modelling conventions from the enthalpy work** —
  `dH/dt` is the open-system energy accumulation (flow work lives
  inside `h`, so `ah` covers it); shaft work is authored as an
  *imposed boundary port* (`fWs [A_work, N]`, no equation) rather
  than a σ-law transport; kinetic/potential energy deferred to a
  future event-dynamic mechanical energy balance.  These are the
  suite's first recorded model-level conventions — decide whether
  they belong in `design-principles.md`, a new library-conventions
  doc, or only `behaviour-linker-design-discussion.md`.
- `index_source` enum note (see observations).
- Minor: `E_dUdt` has no `equation_class` — set `balance` if the
  class vocabulary intends it for accumulation equations.
