# Session handoff — 2026-11-06

## Design discussion in flight — copy vs reference for submodel reuse

Triggered by today's modeller work on referenced composites.  Every
friction point hit — read-only islands, foreign-endpoint stubs,
cross-occurrence connect, occurrence-path namespacing, Option A
VarBinding splits, empty sub-plan slices — traces to store-level
deduplication: the host stops being a flat graph and becomes a flat
graph with holes resolved from a foreign graph.  Proposal on the
table: **make stamped copies (with provenance) the insertion path;
`refersTo` goes dormant, not deleted.**

Reframe agreed in discussion: the choice is *where deduplication
lives* — in the **store** (one definition, N views = `refersTo`) or
in the **workflow** (N copies + `copiedFrom` + refresh gesture).  The
artefact line stays the shareable versioned definition; the
occurrence becomes a **checkout, not a view** (git working-copy vs
symlink).

### What the live link actually buys — decomposed

- **Synchronous propagation** — the only thing a copy structurally
  cannot do.  But §22's own reproducibility clause says propagation
  was always going to be gated by version pins; opt-in at pin bump is
  a gesture anyway.
- **Provable identity of occurrences** — by construction under
  `refersTo`; under copies only claimed via provenance (drift
  possible but detectable — `copiedFrom` indexes like `usesModel`).
- **Per-occurrence context** — the override map exists *because* the
  definition is shared and untouchable.  Under copies, structural
  adaptation is just editing; per-occurrence pin variation (same
  submodel, different species scheme in one host) is the one
  capability that genuinely dies.  Unexercised so far.
- **Edit-in-context** — `refersTo` is explicitly not an editing
  channel (edit blind in the artefact; hosts receive passively).
  Copy + existing `extract-submodel` edits in host context and
  *publishes back*.  Copies serve "adjust it in the domain it is
  used" better; only automatic fan-out is lost.

### The two real losses, priced

- **Propagation becomes a gesture** — `copiedFrom` (source artefact +
  frozen-version IRI) + `refresh-from-source` + where-used index.
  v1: refuse-to-clobber modified copies; 3-way merge later (recorded
  source version = merge base).  Reproducibility inverts favourably:
  immobility becomes the default; *updating* needs the machinery.
- **Pin context** — a stamped copy re-resolves under *host* pins;
  different-pins = silently different physics for copied entity
  types.  Mitigation = stamp-time coverage check (host scope must
  resolve the copy's symbols; `uncovered-override` repositioned).

### What survives, cheaper

- **Interface** — source open arcs become ordinary host open arcs
  (principle 13 machinery: stub → complete to leaf).  Terminal
  contract (arc type, token, direction, expected external entity
  type) copies *as data* onto the stub; legality check moves from
  insert-time to completion-time.
- **Nesting/cycles** — recursive materialisation; `reference-cycle`
  evaporates as a problem class.
- **Where-used** — derived index re-points at `copiedFrom`.
- **§22 machinery** — dormant, not deleted: `refersTo`, occurrence
  expansion, sub-plans stay in code + tests until a real
  contract-boundary case (curated black-box unit) demands them.
  Option A dies by irrelevance, not deferral.
- Principle 12 amendment: "definition lives in its own graph → edits
  propagate" and "referenced definitions render in-place read-only"
  get rewritten if the copy direction is ruled.

### Decision questions for tomorrow

1. **Per-occurrence pin variation** — real planned use, or machinery
   for a case that won't come?  (Strongest residual argument for
   `refersTo`.)
2. **Automatic propagation** — was silent fan-out ever desirable, or
   was pinning always going to gate it?  Decides whether
   refresh-as-gesture is a downgrade or a correction.
3. **Black-box boundary** — any foreseeable case where the host must
   be *unable* to touch submodel internals?  If yes, `refersTo`
   stays on life support for exactly that case.

Outcome feeds a §33 in `docs/behaviour-linker-design-discussion.md`
+ principle-12 amendment, flagged OPEN until the three rulings land.

## Landed today (committed)

- `59ba642` — cross-branch arcs derive their rendering; stubs only
  for foreign endpoints.
- `73c01b2` — gestures doc: armed survives navigation, ref
  completion exception.
- `e3abee2` — cross-branch connect: begin/finishArc
  branch-independent.
- `0253dc7` — canvas hotkeys ignore keystrokes in form controls.
- `e84a1e8` — extract keeps the occurrence label on the ref shell.
- `docs/design-review-2026-11-06.md` — first design-review report
  (seed-layer drift finding: floor migrations can re-implement
  superseded semantics).
- Principle 13 ruled: arcs bind only leaf entities; open arcs are
  construction, not bookkeeping.

## Store state

`data/` persisted (committed): `model-2` renamed "model2", now
references **`model-2/tripot1`** — a real extracted referenced
composite (`refersTo` + `usesModel` live in the data; the first
genuine §22 case).  `assignments`, `library`, `ontology` resaved
(idempotent migrations / label churn).  New file `tripot1.trig`.

## Next up

- Rule on the three copy-vs-reference questions → §33 + principle-12
  amendment.
- If copy-first is ruled: `copiedFrom` + version, refresh gesture
  (refuse-clobber v1), stamp-time pin-coverage check, derived
  where-used index re-point.
- `tripot1` is the test case either way — it is the first real
  referenced composite in the data.
- Still queued: §21 closure-moves rewrite; occurrence-path
  namespacing (only if `refersTo` survives); §32 stage-2
  `promo:Mechanism`; cross-artefact consistency review.
