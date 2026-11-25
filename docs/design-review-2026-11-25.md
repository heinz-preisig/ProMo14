# Design review — 2026-11-25

Fourth run of `.devin/workflows/design-review.md`.
HEAD: `c133862`.  Range: `a0b914b..c133862` (previous review
2026-11-22 at `a0b914b`; 43 commits).

## Baseline

`uv run pytest backend/ -x -q` → **588 passed** (574 at last
review; +14 — qss assignment, energy wiring, document/table and
emit tests).  No environment noise observed.

## Verdicts

| § | Principle | Verdict |
|---|-----------|---------|
| 1 | Semantics in ontology | **conforms** — hardcoded-mechanism grep clean; `core/seed.py` changes in range are the §17 seed audit (vocabulary layer); modeller `X↔C` uses the ontology-declared `component_alignment` capability |
| 2 | Symbolic-only equations | **conforms** — zero numeric literals in `promo:rhs` values across all `data/*.trig` (proper value extraction; the range's new equations use `inv(half)`, not `2`) |
| 3 | Three-layer token model | **conforms** — `promo:token` only on grouping etypes; `carriesToken` on vars (efforts/flows/extensives); zero token predicates on arcs |
| 4 | Token neutrality | **conforms** — no token decls on `F_*`/`kConv*`/`A*`/`const_*`; `V_10`'s `{"energy":1}` is an effort (sanctioned); `fWs` unchanged |
| 5 | Mass granularity | **conforms** — untouched in range |
| 6 | Named graphs + pins | **conforms** — 6 artefact files; pin DAG acyclic — all edges flow toward `ontology` (assignments→ontology+library; library/species→ontology; model→assignments+library+ontology; model-2 adds species) |
| 7 | `.trig` via APIs | **conforms** — all six graphs byte-identical file↔live after save→re-save; every range mutation went through author scripts + `POST /save` |
| 8 | Algebraic indices | **conforms** — `E_29` still same-index `F_conv*fmc` (gap open, avoided); in-range machinery: `promo:alignedComponent` + `e_align[X,C]` (§41), `idx_component` elements, named extractions (`x`/`y`/`z`) |
| 9 | Computed species | **conforms** — `promo:member` only in `species.trig` |
| 10 | RDFS only | **conforms** — zero `owl:` |
| 11 | Suite emits, user runs | **conforms** — `exec` only `/initial` (`service.py:1787`); `subprocess` only pdflatex (`document.py`) |
| 12 | Two-tier submodels | **conforms** — unchanged; occurrence-path residual items unchanged |
| 13 | Leaf-bound arcs | **conforms** — untouched in range |
| 14 | Transport-mediated flows | **conforms** — `requiresMechanism` unchanged |
| 15 | Construction rules | **conforms** — audit endpoint unchanged; author scripts consume `/consistency` as designed |
| 16 | Signals | **conforms** — untouched in range |
| 17 | Seed floor = machinery | **conforms** — §52 audit *landed in range*: `g` moved to authored `V_126` (constant-class, 9.81); `F_mass`/`F_energy` + `A_mass`/`A_energy` union arc indices removed (`fce580f`) |
| 18 | Named extractions | **conforms** — landed in range: `x`/`y`/`z` (`V_127`–`V_129`), `E_fPot`→`fmc·g·z`, areas→component products |

## Drift

None found.  Range content is sanctioned work: §41/§42 component
machinery, §47–§55 lumped/qss/energy authoring, dialect-permute
completion, document-layout fixes, BL alternatives affordance.

*Stale-narrative (minor):* the principles doc's landed-notes block
describes the §50-era wiring (`E_P_int`/`E_v_fromP` feeding `fKin`
via `v`) — superseded by §55 same day (`fKin`→`v_str`, aliases
dropped).  Record kept; §55 addendum appended (see refinements).

## Living-docs realignment

Checked `behaviour-linker-status.md`, `equation-editor-overview.md`,
`suite-status.md`, `what-am-i-authoring.md`, `worked-example.md`,
`modeller-gestures.md`, `concepts-and-architecture.md`,
`problem-catalogue.md` (kind coverage via
`test_problem_catalogue_coverage`).  **No stale claims requiring
realignment** — references to imposed-`fl`, seeded-`g`, bulk-`v`
live in append-only records or the principles doc's own ruling
narrative.

## Gap-status changes

- **`ΣF(v)=0 → v` (the §47 upgrade) — resolved differently** (§54/§55).
  Velocity is determined pressure-driven *on the arc* — quadratic
  `E_v_str_darcy`/`E_fmc_darcy` alternatives beside the linear
  `kConvX` law; the lump receives contact velocity via the `v_str`
  port (its only `v` consumer, `fKin`, fixed to stream physics).
  No algebraic loop needed — `sqrt`/`sign`/`abs` make the inverted
  law explicit.  `etype_lumped_qss` energy wiring landed.
- **BL alternatives surface** — `pick`/exchange existed only through
  the unresolved-inputs panel; sequence rows now carry a `⇄N`
  alternatives chip (`a6d9fd3`) — verified live (exchange
  `E_4`→`E_fmc_darcy`, `closed=True`).
- **New open item** — `kConvX` could *derive* from `lam`/`Lp`/`dp`
  for the linear regime (parked: needs a physics decision — which
  linear resistance model — plus a viscosity parameter); per-arc
  regime mixing would need a sibling etype.

## Proposed `design-principles.md` edits

- **Applied (mechanical):** appended the §54/§55 addendum to the
  landed-notes block — `fKin`→`v_str` (v's sole consumer fixed),
  `E_P_int`/`E_v_fromP` dropped from `etype_lumped`, qss energy
  wiring landed, Darcy-alternatives pattern recorded.
- **Proposed only (ruling-level):** none — §54's
  alternatives-on-one-lhs pattern is an instance of the existing
  regime-is-assignment-level ruling, not a new principle.
