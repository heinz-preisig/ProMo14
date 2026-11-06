---
description: periodic audit of the repo against docs/design-principles.md, plus refinement of the principles doc itself
---

# Design review — repo vs design-principles.md

**Cadence:** run when the newest `docs/design-review-*.md` is older
than ~7 days, or after ~10 commits touching `backend/`, `data/`,
`packages/semantic/`, or the ontology — whichever first.  The dated
report is the cadence record; no external state needed.

**Output:** `docs/design-review-YYYY-MM-DD.md` + mechanical
refinements applied to `docs/design-principles.md` (ruling-level
changes are *proposed* to the user, never applied — see step 6).

## 1. Re-ground

// turbo
1. Establish the audit range:

   ```
   git log --oneline -30 && git status --short
   ls docs/design-review-*.md 2>/dev/null | tail -1
   ```

2. Read `AGENTS.md`, `docs/design-principles.md`, the latest
   `docs/session-handoff-*.md`, and the latest
   `docs/design-review-*.md` if one exists — its header records the
   previous HEAD; the audit range is that..HEAD (first run: last
   ~50 commits).

## 2. Green baseline

// turbo
3. `uv run pytest backend/ -x -q`

   Record pass/fail counts.  Known-environment noise, not drift:
   the two snap-Octave `tmp_path` execution failures and any
   julia-binary-absent skips.  Confirm failures are exactly those
   before dismissing; anything else is a finding.

## 3. Per-principle audit

Check each principle of `docs/design-principles.md`; verdict per
item: **conforms / drift / gap-status-changed**, with evidence.

- **§1 semantics-in-ontology** — grep backend for hardcoded
  mechanism/token/domain names (e.g. `convection`, `token_mass`)
  in `*.py`: hits may only live in `core/seed.py`,
  `core/capabilities.py`, tests, or strings read from the store.
- **§2 symbolic-only** — in `data/*.trig`: `promo:rhs` literals and
  `rhsExpression` argument lists contain no numeric literals.
  Digits are legal only in `promo:value`, value-cell literals, and
  `const_*` records.
- **§3 token model** — token tests green; every `carriesToken` IRI
  appears in its var's `tokenVector`; `promo:token` only on
  grouping entity types; no token predicates on arcs.
- **§4 neutrality** — `F_*` incidence matrices, coefficients
  (`kConv*`/`kDiff*`/`kQ*`), geometry (`Axy`/`Axz`/`Ayz`),
  `const_*`, and direction flags carry no `carriesToken`/
  `tokenVector`.
- **§6 named graphs** — all artefact graph IRIs slash-free; the pin
  predicates (`usesOntology`, `usesLibrary`, `usesSpecies`,
  `usesAssignment`, `usesModel`) form a DAG — no cycles.
- **§7 .trig hygiene** — load the real store, save to a scratch
  dir, compare per named graph.  Method (proven): `rdflib.Dataset`
  with `default_union=True` for the files; the store applies floor
  migrations at `RdfStore.load()`, so "isomorphic" means the files
  already carry them (good) — drift means un-serialized edits or
  stale files.  `compare.isomorphic` handles bnodes; do NOT use
  `graph_diff` (misreports).  Never hand-edit `*.trig`.
- **§8 algebraic indices** — checker/plan tests green; confirm the
  `E_29` sibling sub-index gap status (still avoided in data, or
  now implemented — then move it out of the gap list).
- **§9 species fixpoint** — distribute tests green; no hand-declared
  `S`/`Q` membership anywhere in model artefacts.
- **§10 RDFS only** — `grep -n 'owl:' data/*.trig` returns nothing.
- **§11 suite emits, user runs** — no code path executes emitted
  code beyond the `POST /initial` t=0 verification;
  `code/export` + `code/bundle` still emit the full self-contained
  set per target.
- **§12 two-tier submodels** — `refersTo` still renders read-only
  in-place; nothing merges referenced graphs; record occurrence-path
  namespacing gap status (open / landed).

## 4. Drift hunt over the audit range

// turbo
4. `git log --oneline <range> -- backend/ apps/ packages/ data/ docs/`

   Read the diffs for: new hardcoded semantics in code, numeric
   literals inside equations, token declarations on neutral vars,
   model-executing endpoints, `data/*.trig` edits that bypass the
   API rule.

## 5. Write the report

5. Create `docs/design-review-YYYY-MM-DD.md` containing:
   - header: date, HEAD commit, audit range;
   - per-principle verdict table + evidence (command, key output);
   - drift list — file, what, which principle, severity;
   - gap-status changes;
   - proposed `design-principles.md` edits, split into
     **mechanical** (applied) vs **ruling-level** (proposed only).

## 6. Refine the principles doc

- **Apply:** stale file/symbol references, statements contradicted
  by landed code (cite evidence), resolved gaps moved out of the
  open list, and rulings settled since last review — pulled in from
  `behaviour-linker-design-discussion.md` §N or session handoffs
  (this doc is the curated surface; the discussion file accretes).
- **Propose only:** anything that alters a recorded ruling or adds
  a new principle — those are user decisions by design.
- Sync the `AGENTS.md` hard-rules digest if principles moved
  materially.

## 7. Report back

Present: the verdict table, drift items needing user decisions,
applied doc edits, proposed rulings.  Commit docs only:
`docs: design review YYYY-MM-DD`.
