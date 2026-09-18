# ADR-007: Modeller persistence — RDF topology, hierarchy, layout boundaries

Status: accepted (2026-09-18)
Builds on: ADR-004 §1 (flat topology), §2 (hierarchy), §7 (persistent vs transient)

## Decision

The artefact graph (`?graph=`) **is** one model document.  All three
layers the frontend keeps in `AppState` map to `promo:` triples in that
graph; nothing else is persisted.

### Persisted (artefact graph)

| Frontend state | RDF |
|---|---|
| `modelNodes` | `promo:ModelNode` — `promo:entityType` → entity-type IRI, `rdfs:label`, `promo:internalID` |
| `modelArcs` | `promo:ModelArc` — `promo:source`/`promo:target` → ModelNode IRI, `promo:arcType` → arc-type IRI, `promo:internalID` |
| `tree` composites | `promo:Composite` — `promo:internalID` = tree node id, `rdfs:label`, `promo:parent` → parent Composite IRI (absent on root), `promo:children` JSON `[{id, iri?}]` (ordered; `iri` present → leaf referencing a ModelNode, absent → composite child by tree id) |
| `layoutStore` | `promo:layout` JSON literal on each Composite: `{childTreeId: {x, y}}` — the frontend's exact per-view keying |
| `knotStore` | `promo:knots` JSON literal on each Composite: `{arcIri: [{x, y}]}` — **per (view, arc)**, not per arc: the same model arc renders differently on each GraphView (connection vs projected leftArc/rightArc/open) |
| `openArcs` | `promo:openArcs` JSON literal on each Composite: `[{iri, externalIri, arcType, isSource}]` |
| counters | one `promo:Model` resource per graph — `promo:rootComposite` → root Composite, `promo:nextTreeId`, `promo:arcCounter` |

### Not persisted

- **GraphViews** — recomputed by `computeGraphView` on load.
- **Resolved graphical attributes** — come from the catalogue at render
  time (ADR-004 §4: the modeller stores references, not graphics).
- **Session state** — selection, hover, pan/zoom, pending connections,
  resolver caches.
- **Entity/arc-type definitions** — live in the ontology, referenced by
  IRI only.

### Boundary rationale

- Only the flat topology gets first-class resources (ModelNode,
  ModelArc) — ADR-004's "flat topology is authoritative" rule.  The
  hierarchy is organizational (Layer 2), so composites carry their
  view-scoped data as structured JSON literals (`children`, `layout`,
  `openArcs`) rather than sub-resources — same pattern as
  `incidenceList`/`knots` elsewhere in the vocabulary.
- Layout is annotation on the hierarchy (positions are per-parent-view),
  so it hangs off `promo:Composite`, not the semantic nodes — a model
  node has no intrinsic position.
- Open arcs are semantic (a real arc with a temporarily missing
  endpoint), so they persist rather than being recomputed.
- Knots are view data, not topology — they hang off the Composite
  alongside `layout`, keyed by arc IRI within each view.
- Tree integer IDs persist via `internalID` because layout keys are
  tree-id strings — they are session-local identifiers, not semantics.
- Composite IRIs are derived deterministically
  (`<graph>/Composite_<treeId>`) so save/load round-trips without
  minting.

## Endpoint contract (`backend/modeller/service.py`)

- `GET /api/modeller/model?graph=` → `ModelDocument`
  `{nodes, arcs, composites, rootTreeId, nextTreeId, arcCounter}`
  (each composite carries its `children`/`layout`/`openArcs`)
- `PUT /api/modeller/model?graph=` → replaces the graph's model content
  (delete existing `promo:Model*`/`promo:Composite`/`promo:OpenArc`
  triples, write the document).  Document-style save/load matches the
  reducer's whole-state model; granular CRUD can come later.

The frontend serializes `AppState` Maps to arrays on save and rebuilds
them on load; the dirty-tracking middleware + `useStoreDirty` already
cover the save UX.
