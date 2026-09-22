# Modeller — Implementation Status

**Last updated:** 2026-09-10

## Current state

Phases 1–3 complete.  Phase 4 partially done (interactive knots
implemented; persistence not yet).  35 unit tests passing.  TypeScript
compiles clean.

## Feature checklist

| Feature | Status |
|---------|--------|
| Click canvas to add node (centered coords) | ✅ Done |
| Click leaf to select | ✅ Done |
| Right-click leaf to start/finish connection | ✅ Done |
| Drag nodes to move (arcs follow) | ✅ Done |
| Select arc/knot and press Delete to remove | ✅ Done |
| Directed arcs with arrowheads | ✅ Done |
| Node types from palette (IRI-based catalogue) | ✅ Done |
| Arc types (solid / dashed, IRI-based catalogue) | ✅ Done |
| Connection rules enforced (shared resolver) | ✅ Done — placeholder allows all; ready for ontology rules |
| Valid/invalid hover feedback (green/red ring) | ✅ Done |
| Arc type selector in properties panel | ✅ Done |
| Status bar with connection feedback | ✅ Done |
| Knot structure in arcs | ✅ Done |
| Interactive knots: drag, double-click add, right-click remove | ✅ Done |
| Open-arc reconnection via red drag handle | ✅ Done |
| §15 arc reference direction: through-path default on insert | ✅ Done |
| §15 reverse reference direction (right-click arc / `r` key) | ✅ Done |
| §15 arrowhead follows reference direction, not draw order | ✅ Done |
| §15 orientation preserved across composite boundary (open arcs) | ✅ Done |
| Declarative SceneObject[] rendering layer | ✅ Done |
| Uniform scene interaction dispatch | ✅ Done |
| Three-panel layout (ancestors / children / siblings) | ✅ Done |
| Double-click composite → zoom into | ✅ Done |
| Double-click leaf → zoom into leaf view | ✅ Done |
| Click empty canvas in leaf view → add child, convert to composite | ✅ Done |
| Group selected leaves into composite | ✅ Done |
| Pan (middle-drag) and zoom (scroll wheel) | ✅ Done |
| Reset all button | ✅ Done |
| Catalogue-resolved graphical definitions | ✅ Done |
| 35 unit tests passing | ✅ Done |
| Save/load persistence | ❌ Not yet |
| Multiple GraphView panels (ADR-003) | ❌ Not yet |
| Ontology integration (real backend) | ❌ Not yet |
| Direct arc endpoint reconnection (regular arcs) | ❌ Not yet |
| Drag-to-create-arc | ❌ Not yet |

## Completed phases

### Phase 1 — Stabilize the scene layer ✅

- Focused tests for `buildScene` covering nodes, arcs, open arcs,
  handles, selection state, and interaction descriptors.
- Verified scene interaction dispatch for selection, dragging,
  navigation, deletion, and open-arc reconnection.

### Phase 2 — Generic semantic contracts ✅

- Stable IRI-based contracts for base entities, domains, open-ended
  classifications, tokens, interfaces, graphical definitions, and
  connection-rule results.
- In-memory placeholder catalogue replacing closed `TypeA/B/C` and
  `ArcType1/2` unions.

### Phase 3 — Rules and graphical resolution ✅

- Connection decisions behind a generic rule resolver shared by arc
  creation and reconnection.
- Valid/invalid target feedback and arc-type selector.
- `buildScene` styles replaced by externally assigned graphical
  definitions.

### Phase 4 — Graph editing (partially)

- ✅ Interactive knot scene objects and waypoint commands.
- ✅ Serialization boundaries for flat RDF topology, hierarchy/layout
  data (ADR-007, `GET`/`PUT /api/modeller/model`).  Graphical
  assignments still pending.

## Pending items

- ~~Define RDF topology and separate hierarchy/layout persistence
  boundaries~~ **Done (2026-09-18):** ADR-007 — artefact graph = one
  model document; `promo:ModelNode`/`promo:ModelArc` resources for the
  flat topology, `promo:Composite` with `children`/`layout`/`openArcs`
  JSON literals for hierarchy + view data, `promo:Model` root with
  counters.  `GET`/`PUT /api/modeller/model` (document save/load);
  frontend `modelPersistence.ts` serializes `AppState`, `loadState`
  command rebuilds it, Save button writes model + TriG.  3 tests.
- Design reusable composite and instantiated-model insertion,
  provenance, parameter preservation/overrides, and graphical port
  mapping.
- Plan on-demand graph access for models too large to load fully into
  browser memory.
- Direct arc endpoint reconnection for regular arcs.
- Drag-to-create-arc interaction.
- ~~Real ontology backend integration (placeholder catalogue and resolver
  are in place).~~ **Done (2026-09-18):** `RemoteCatalogue` loads
  entity-types/domains/tokens/connection-rules; entity `branch` → domain
  IRI feeds `domainTypeIris` into `buildConnectionQuery`; arc types from
  rule carriers; placeholder fallback when the backend is down.  Caveat:
  entity types carry only top-level branch — subdomain-scoped rules
  won't match until entities get finer domain assignment.

## Known issues

- Knot insertion: `addKnot` appends to end of array regardless of click
  position; knots render in array order, not geometric order.
- Arc rendering may clip at canvas edges.
- `reconnectOpenArc` only handles dangling ends from leaf-to-composite
  conversion, not regular arc reconnection.

## How to run

```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
npm install
npm run dev      # development server on :3004
npm run build    # production build
npm test         # all workspace tests
```

Or via the orchestrator: `./dev.sh start modeller` (ensures backend too)

## Mouse / pointer mapping

| Input | Action |
|-------|--------|
| Left click on leaf | Select leaf (and set as connection source) |
| Left click on composite / ancestor / sibling | Zoom to that view |
| Left double-click on leaf | Zoom into leaf view |
| Left double-click on composite | Zoom into composite view |
| Left click on empty canvas | Add node of active palette type |
| Left click on empty canvas in leaf view | Add child and convert leaf into composite |
| Right click on leaf (after selecting source) | Create arc to that leaf |
| Right click on leaf (no source selected) | Select as connection source |
| Right click on empty canvas | Cancel pending connection / clear selection |
| Middle press + drag | Pan the canvas |
| Scroll wheel | Zoom in / out |
| Drag red handle on open arc | Reconnect dangling end to nearby leaf |
| Double-click on arc | Add a knot at cursor position |
| Drag knot | Move knot position |
| Double-click on knot | Add a new knot at that position |
| Right-click on knot | Remove knot |
| Right-click on token-flow arc | Reverse reference direction (§15) |
| `r` with arc selected | Reverse reference direction (§15) |
| Delete / Backspace | Remove selected node, arc, or knot |

## Constants

- Default dev server port: 3000
- `NODE_RADIUS = 24`, `STROKE_WIDTH = 2`, `ARROW_SIZE = 10`
- Palette width: 140px
