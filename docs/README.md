# ProMo14 documentation map

How this directory is organised, and the edit rules for each class of
document.  Ruled 2026-11-10 (doc-governance discussion); applies to
everything added since.

## Three tiers

| Tier | Contents | Edit rule |
|------|----------|-----------|
| **A — Records** | `session-handoff-*`, `*-design-discussion-*`, `ADR-*`, `*-review-*`, `*-ticket.md`, dated status snapshots | **Append-only, never rewritten.** When superseded, add *one* banner line at the top (`> **Superseded:** §N of design-principles.md (ruled YYYY-MM-DD)`) and stop. The old phrasing *is* the history. |
| **B — Living truth** | `design-principles.md`, `concepts-and-architecture.md`, `*-overview.md`, `*-status.md`, normative contracts (`value-cells`, `value-fill`, `versioning-and-session-design`, `equation-context-contract`, `modeller-gestures`) | **Body reads as current truth.** A superseded claim is rewritten, not stacked with corrections; traceability moves to a paragraph-level `(amended YYYY-MM-DD)` marker. Each carries a header line `Living — realigned to rulings through YYYY-MM-DD`. |
| **C — User guidance** | `problem-catalogue.md`, `what-am-i-authoring.md`, `worked-example.md` | **Derives from Tier B, may never contradict it.** Guarded mechanically (`test_problem_catalogue_coverage`). |

## Stepping back

The chain is always: **ruling → record → commit.**

- `design-principles.md` carries each ruling with its date and a pointer
  to the discussion record (`behaviour-linker-design-discussion.md §N`,
  an ADR, a handoff) where the reasoning lives.
- Tier A records hold *what was decided when* — search them for the old
  phrasing when reconstructing why something changed.
- Tier B docs answer *what is true now*; they should never need a diff
  to be readable.

## Standing rules

1. **Rulings land twice.** Recording a ruling in
   `design-principles.md` obliges realigning the Tier B/C docs it
   touches *in the same commit*. Drift between principles and the
   living docs is the failure mode this map exists to prevent.
2. **Problem-catalogue charter.** Add a `### \`kind\`` section whenever
   an engine starts emitting a new problem kind — enforced by
   `test_problem_catalogue_coverage`, which fails on an uncatalogued
   `kind="…"` literal in `backend/`.
3. **Status headers stay honest.** A `Last updated:` or
   `Living — realigned through:` line is a claim; refresh it when the
   body changes materially, or it becomes the next lie.

## Where things are

- Concepts, artefact model, pipeline, worked example →
  `concepts-and-architecture.md`, `worked-example.md`
- Rulings and open gaps → `design-principles.md` (+ `## Open
  deviations / known gaps` at its foot)
- Per-tool state → `docs/<tool>-overview.md` + `docs/<tool>-status.md`
- Problem causes/remedies → `problem-catalogue.md`
- Contracts → `equation-context-contract.md`, `value-cells.md`,
  `value-fill.md`, `versioning-and-session-design.md`
- The full index by category → `suite-overview.md` §9
