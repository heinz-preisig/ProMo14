# Value cells — the §20 ν channel

Normative statement of the coordinate-enumeration convention for
multi-indexed value tables: ν parameter tables and initial-condition
pins stored on a variable as `promo:ValueCell` resources.  Last updated
2026-09-28.

## Contract

**The authoritative data is the coordinate→value map, not a flat list.**
Every cell carries its own coordinate; flat enumerations are derived
projections, never stored meaning in themselves.

```turtle
<var>  promo:valueCell  <cell> .
<cell> a                promo:ValueCell ;
       promo:coordinate "[\"el_r1\", \"el_A\"]" ;   # JSON list, ordered
       promo:atIndexElement <el_r1>, <el_A> ;        # unordered nav
       promo:value        -1.0 .                     # literal scalar
```

- **`promo:coordinate`** — a JSON list of index-element IRIs, ordered
  in the variable's `indexStructure` order.  This is *the* cell
  coordinate: a reader that walks cells via `coordinate` needs no
  further convention.
- **`promo:atIndexElement`** — one link per element, for graph
  navigation only; unordered.  Never reconstruct order from it (the
  read path falls back to *sorted* element IRIs, which is not the axis
  order — kept only for legacy cells).
- **`promo:value`** — a literal scalar.  Never an expression: computed
  values are `promo:Expression` trees behind `promo:rhsExpression` or
  `initialise`-class equations.  Cells are leaf data.
- **Self-containment** — cell IRIs are deterministic
  (`cell_<sha1(var|key)[:12]>` under the artefact's IRI space); all
  information is in-graph.  No external schema, no imported tables.
- **Replace semantics** — `set_value_cells` wipes the variable's
  existing cells first; a PUT sends the whole intended table.

## Coordinate keys

API payloads (`PUT /api/instantiate/values`, `VarBindingOut.values`,
`par` on `/initial`) use string keys, not the JSON coordinate:

    key = element-IRIs joined with "|", in indexStructure order

A scalar variable has the single empty key `""`.  Element IRIs never
contain `|`.  The key is the coordinate with its ordering baked in —
`value_cells` rebuilds it from `promo:coordinate`, so key and cell can
never disagree.

## Flat enumeration (C order)

When a table must be flattened — emitted literals, `par` payloads,
`_value_table` — the enumeration is:

    cartesian product of the bound element sets,
    indexStructure order, LAST INDEX FASTEST (C order)

Example — `ν[I, J]` with `I = {i1, i2}`, `J = {j1, j2, j3}`:

```
ν:       j1  j2  j3
    i1    1   2   3
    i2    4   5   6

flat: [1, 2, 3, 4, 5, 6]
      (i1,j1) (i1,j2) (i1,j3) (i2,j1) (i2,j2) (i2,j3)
```

Everything that produces or consumes a flat list implements this one
convention: the UI editor (`coordKeys`), `plan._value_table`, `par`
values on `POST /api/instantiate/initial` (flat index-ordered lists),
and every emitter's `_array_lit`.

## Per-target rendering

The emitters translate the canonical C-order list into native layout —
this is the *only* place language memory order enters, and each emitter
owns it in `_array_lit`:

| target | shape | emitted form |
|--------|-------|--------------|
| python | n-D `np.array` | `np.array([...]).reshape((d1, …, dn))` — native C order |
| julia  | n-D array | `permutedims(reshape([…], dn, …, d1), (n,…,1))` — column-major compensation |
| matlab | n-D array | `permute(reshape([…], dn … d1), [n … 1])` — column-major compensation |
| 1-D    | all | vector literal; julia `[…]`, matlab column `[v1; v2]` |
| scalar | all | bare numeral |

Column-major languages reshape to the *reversed* dims (which fills
first-index-fastest) then permute back — so the same flat list lands
each value on the same coordinate in every target.  A missing cell
emits as `NaN`.

Inside generated code there is no layout issue: MATLAB wraps values in
`MultiDimVar` (label-indexed); julia/python slice `y` and look up `par`
flat.

### Caller contract: `par`

Runtime parameters (non-cell params and `ic0_<name>` IC pins) read
`par["name"]` / `par.name`.  The `/initial` endpoint accepts scalars or
flat C-order lists; MATLAB/Julia callers supply natively-shaped arrays
matching the bound index sizes.  `par_needed` in the `/initial`
response echoes the emitted names (`V_5`, `ic0_V_1`) — display labels
are not valid keys.

## Failure mode this prevents

A renderer that reshapes the flat list naively in a column-major
language assigns every value to the wrong coordinate — **silently**, no
error.  The tripwires: (a) every cell self-describes its coordinate,
(b) `test_value_cell_layout_convention` goldens each emitter's literal
and simulates the target fill order on a non-square table (square dims
cannot detect a transpose bug).

## Pointers

- `backend/core/graph_store.py` — `set_value_cells` / `value_cells`
  (RDF shape, key grammar).
- `backend/instantiate/plan.py` — `_value_table` (map → flat list).
- `backend/instantiate/emit_{python,julia,matlab}.py` — `_array_lit`
  (per-target literals); `ic_source` in `initial` emitters.
- `apps/instantiation/src/App.tsx` — `coordKeys` (same enumeration on
  the editor side).
- `docs/species-status.md` — §20 context: what the tables are *for*.
