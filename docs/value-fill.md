# Value fills — populating tables without enumerating cells

Design for selector-based value entry on top of the §20 ν channel
(docs/value-cells.md).  Motivation: realistic tables are mostly
uniform — one ν row per reaction, one k per arc — so per-cell entry is
the exception, not the rule.  Implemented 2026-10-28.

## Terms

- **cell** — a `promo:ValueCell`: one value at one concrete
  coordinate.  Unchanged.
- **fill** — a `promo:ValueFill`: one value at a *selector* — a
  coordinate with one or more `*` segments.  Covers every cell the
  selector matches.
- **selector** — a `|`-joined string in `indexStructure` order where
  each segment is either an index-element IRI or `*`.  `*` alone (or
  `*|*`) matches the whole table; `a1|*` matches a slice.

## Contract

**Cells remain the authoritative concrete data.**  Fills are *entry
shortcuts*, resolved to concrete cells at `plan()` time — the
`CodePlan` flat list, `model_data.json`, emitted code, and
`par`/`ic0` payloads never see a selector.  A reader of
`model_data.json` cannot tell a filled table from an enumerated one.

```turtle
<var>  promo:valueFill   <fill> .
<fill> a                 promo:ValueFill ;
       promo:fillPattern "[\"*\", \"el_A\"]" ;  # JSON list, '*' allowed
       promo:value       1.5 .
```

- `promo:fillPattern` mirrors `promo:coordinate` — ordered JSON list —
  so the two resources share the axis-order contract and differ only
  in whether `*` may appear.  `promo:atIndexElement` links only the
  concrete segments (navigation parity with cells).
- Same self-containment and replace semantics as cells: deterministic
  IRIs `fill_<sha1(var|pattern)[:12]>`, all in-graph, whole set
  rewritten per PUT.

## API surface

Unchanged: `PUT/GET /api/instantiate/values` still exchange
`{key: value}` maps.  A key containing `*` is a fill; any other key is
a cell.  `set_value_cells`/`value_cells` partition on that marker —
callers need no new shapes:

```json
{"values": {
    "*|*":        -1.0,      // default: whole ν table is -1 …
    "el_r1|*":     1.0,      // … except reaction r1's row is +1 …
    "el_r1|el_A":  2.0       // … and one cell overrides both
}}
```

## Resolution (at `plan()`)

`_value_table` resolves each concrete coordinate against the var's
cells + fills:

1. A **cell** at that exact coordinate always wins.
2. Otherwise the **highest-scoring matching fill** wins.  Each
   segment of a matching pattern contributes a per-axis weight —
   concrete element **2**, sub-index (element-class) **1**, `*` **0** —
   and the pattern's score is the axis sum.  `a1|*` (2) beats
   `sub_idx|*` (1) beats `*|*` (0).
3. Two matching fills of **equal score** that cover the same
   cell → a `fill-conflict` problem on the report (never a silent
   winner — which value you get must be auditable).
4. No cell and no fill → `None` → `NaN`, as today.

**Element-class selectors**: a segment may name a sub-index IRI
instead of `*` or an element — it matches every member of that
sub-index's element set (the §16 partitioning metadata).  A segment
that is neither `*`, a bound element, nor a known sub-index simply
matches nothing — like a cell key on an unbound element.

Fills on a var whose index is unbound (symbolic extent) resolve like
cells: no table.

## Composition merge

Models combine at the algebraic level (before `plan()`); each
contributing artefact may carry cells/fills for a shared variable.
Rule: **score decides, provenance never does.**

- Any artefact's higher-scoring selector beats any other's
  lower-scoring one.  A parent's `*|*` default does not override a
  child model's `a1|*` slice — the child already said something more
  precise.
- Equal-score overlap across artefacts → `fill-conflict`, same
  as within one artefact.

Why not "parent wins": a sub-model's concrete data is its contract —
the composing model may add defaults *around* it but silently
shadowing it would make composition unsafe.  If the parent genuinely
disagrees, the conflict problem forces an explicit resolution.

## Consequences

- **Coverage is checkable** — a coord with neither cell nor matching
  fill is provably unfilled; the report can count coverage instead of
  the editor inferring it.
- **IC pins get it free** — states read the same cell store; an
  `ic`-flavoured fill follows identical rules.
- **`model_data.json` unchanged** — flat C-order list + dims; fills
  are fully expanded before serialisation.
- **Emitted code unchanged** — `_tab`/`_ictab` see concrete tables.

## Non-goals (deferred)

- **indexClass-level selectors** (`"conversion|*"` — all elements of
  an index class, not a sub-index).  Sub-index membership covers the
  authored case today; index-class selection is a wider net that may
  surprise (it follows whatever the index binds).
- **Expression-valued cells/fills** — `promo:value` stays literal-only
  (separate open item).
- **PATCH semantics** — PUT still replaces the whole cell+fill set.
