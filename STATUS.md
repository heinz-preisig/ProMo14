# ProMo14 — Browser-based Model Composer Prototype

**Date:** 2026-09-09
**Version:** 0.0.1

## What is this?

A prototype for a new browser-based graphical modeller ("ModelComposer") for the ProMo project. It runs entirely in the browser using React + Konva for canvas rendering.

## Architecture concepts

- **Command Automaton** — a single `useReducer` in `App.tsx`. All state changes go through `applyCommand(state, cmd) → new State`. Commands are a discriminated union; new commands are added by extending the `Command` union + reducer switch case.
- **Three-layer architecture** — Layer 1: flat RDF model graph (semantic, persistent). Layer 2: hierarchy tree (organizational, integer IDs). Layer 3: GraphViews (visual, computed on demand).
- **Three-panel layout** — ancestors on the left margin, children in the center, siblings on the right margin, connector at top center.
- **GraphView** — the main editing surface containing nodes, arcs, and knots. Computed on demand from the flat model graph + hierarchy + layout data.
- **Tree hierarchy** — each GraphView is a node in a tree. Internal nodes = composite systems (branches). Leaf nodes = primitive model nodes whose types are ontology-defined.
- **Nodes** — typed leaf nodes from the ontology. Types and graphical definitions are resolved at runtime through IRI-based semantic contracts (currently placeholder entities: TypeA, TypeB, TypeC via `placeholderCatalogue`).
- **Arcs** — directed, typed connections between nodes. Arc types and graphical definitions are resolved through the same IRI-based catalogue (currently placeholder arc types: ArcType1, ArcType2).
- **Knots** — graphical waypoints on arcs to route them around objects. Interactive: drag to move, double-click to add, right-click to remove.
- **Open arcs** — arcs with one end left dangling when a leaf is converted into a composite. The open end is shown with a red handle and can be dragged onto another leaf to reconnect.
- **Connection rules** — which node types may connect to which via which arc type, enforced at runtime through a shared `ConnectionRuleResolver`. Both arc creation and open-arc reconnection go through this resolver.
- **Semantic contracts** — IRI-based interfaces (`SemanticCatalogue`, `ConnectionRuleResolver`) define base entities, arc types, domains, tokens, interfaces, graphical definitions, and connection-rule results. An in-memory placeholder implementation exists; a real ontology backend can later supply the same interfaces.
- **Scene objects** — computed graphical objects (`node`, `arc`, `openArc`, `openArcHandle`, `knot`) form one declarative rendering and interaction layer between `GraphView` and Konva.
- **Model architecture direction** — the final model is a flat RDF topology whose nodes reference separately defined base entities, with a separate hierarchy and layout mapping. See ADR-004 for the agreed long-term architecture.

## Current features

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
| Connection rules enforced (shared resolver) | ✅ Done — placeholder resolver allows all; ready for ontology rules |
| Valid/invalid hover feedback (green/red ring) | ✅ Done |
| Arc type selector in properties panel | ✅ Done |
| Status bar with connection feedback | ✅ Done |
| Knot structure in arcs (geometry supports them) | ✅ Done |
| Interactive knots: drag, double-click add, right-click remove | ✅ Done |
| Open-arc reconnection via red drag handle | ✅ Done |
| Declarative `SceneObject[]` rendering layer | ✅ Done |
| Uniform scene interaction dispatch | ✅ Done |
| Three-panel layout (ancestors / children / siblings) | ✅ Done |
| Double-click composite → zoom into (setView) | ✅ Done |
| Double-click leaf → zoom into leaf view | ✅ Done |
| Click empty canvas in leaf view → add child, convert to composite | ✅ Done |
| Group selected leaves into composite | ✅ Done |
| Pan (middle-drag) and zoom (scroll wheel) | ✅ Done |
| Reset all button | ✅ Done |
| Catalogue-resolved graphical definitions (fill, stroke, radius) | ✅ Done |
| 35 unit tests passing (TreeOps + ModelState + buildScene + connectionService) | ✅ Done |
| TypeScript compiles clean | ✅ Done |
| Save/load persistence | ❌ Not yet |
| Multiple GraphView panels (ADR-003) | ❌ Not yet |
| Ontology integration (real backend) | ❌ Not yet |
| Direct arc endpoint reconnection (regular arcs) | ❌ Not yet |
| Drag-to-create-arc | ❌ Not yet |

## Tech stack

- React 18 + TypeScript
- Vite (build tool)
- Konva + React-Konva (canvas rendering)

## File structure

```
ProMo14/
├── apps/
│   ├── modeller/                    # Browser-based model composer (React + Konva)
│   │   ├── index.html
│   │   ├── package.json             # @promo/modeller
│   │   ├── tsconfig.json
│   │   ├── tsconfig.node.json
│   │   ├── vite.config.ts
│   │   ├── src/
│   │   │   ├── App.tsx              # Main component (canvas, palette, properties, status bar)
│   │   │   ├── main.tsx             # React entry point
│   │   │   ├── state/               # AppState, Command union, applyCommand reducer
│   │   │   ├── model/               # Flat model graph operations
│   │   │   ├── tree/                # Hierarchy tree operations
│   │   │   ├── canvas/              # Stage events + SceneObject interactions
│   │   │   └── scene/               # SceneObject[] building and Konva rendering
│   │   └── src/types/               # Generic graph types + three-layer type system
│   ├── ontology-editor/             # Ontology editor scaffold
│   ├── equation-editor/             # Equation editor scaffold
│   └── behaviour-linker/            # Behaviour linker scaffold
├── packages/
│   └── semantic/                    # Shared IRI contracts, catalogue, connection rules
│       ├── package.json             # @promo/semantic
│       ├── tsconfig.json
│       └── src/
│           ├── contracts.ts
│           ├── placeholderCatalogue.ts
│           ├── connectionService.ts
│           └── connectionService.test.ts
├── backend/                         # Python FastAPI backend (per-tool + shared core)
│   ├── main.py
│   ├── requirements.txt
│   ├── core/                        # Shared services (RDF, IRI, ontology client)
│   ├── ontology/
│   ├── equation/
│   ├── behaviour/
│   └── modeller/
├── docs/
│   ├── ADR-001-hierarchy.md
│   ├── ADR-002-state-management.md
│   ├── ADR-003-multiple-views.md
│   ├── ADR-004-model-and-graphical-architecture.md
│   └── suite-description.md
├── package.json                     # npm workspaces root
├── tsconfig.base.json               # Shared TypeScript config
├── run-dev.sh                       # Modeller dev server launch script
├── progress.txt
└── STATUS.md                        # This file
```

## How to run

```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
npm install
npm run dev      # development server
npm run build    # production build
```

## Completed phases

### Phase 1 — Stabilize the scene layer ✅

1. ✅ Add focused tests for `buildScene` covering nodes, arcs, open arcs, handles, selection state, and interaction descriptors.
2. ✅ Verify scene interaction dispatch for selection, dragging, navigation, deletion, and open-arc reconnection.

### Phase 2 — Generic semantic contracts ✅

3. ✅ Define stable IRI-based contracts for base entities, domains, open-ended classifications, tokens, interfaces, graphical definitions, and connection-rule results.
4. ✅ Add an in-memory placeholder catalogue and replace the closed `TypeA/B/C` and `ArcType1/2` unions without requiring ontology infrastructure yet.

### Phase 3 — Rules and graphical resolution ✅

5. ✅ Move connection decisions behind a generic rule resolver shared by arc creation and reconnection.
6. ✅ Add valid/invalid target feedback and an arc-type selector when several rules match.
7. ✅ Replace hard-coded `buildScene` styles with externally assigned graphical definitions.

### Phase 4 — Graph editing ✅ (partially)

8. ✅ Add interactive knot scene objects and waypoint commands.
9. ❌ Define serialization boundaries for flat RDF topology, hierarchy/layout data, and graphical assignments.

## Next planned steps

### Phase 4 — Persistence (current)

9. Define RDF topology and separate hierarchy/layout persistence boundaries.

### Phase 5 — Composition and scale

10. Design reusable composite and instantiated-model insertion, provenance, parameter preservation/overrides, and graphical port mapping.
11. Introduce repository contracts and on-demand projections for models too large to load fully into browser memory.

## Decisions made

- **Flat RDF topology plus separate hierarchy** — every actual model node and arc belongs to the authoritative flat graph. The attached hierarchy partitions and projects it for navigation and scalable editing; projected composite arcs are not additional semantic arcs.
- **Base-entity references** — model nodes reference separately defined base-entity RDF graphs. Equations and linked behaviour are not embedded in the model topology.
- **One domain per node** — arcs may be domain-internal or cross-domain. All connections are checked through ontology-defined rules.
- **Recursive composition** — an assembled model can become a reusable entity for constructing another model while retaining the common model format.
- **Generic graphical vocabulary** — the Modeller implements reusable graphical primitives and capabilities, while ontology/catalogue data assigns and configures them through stable identifiers.
- **Shared graphical assignment** — the Behaviour Linker launches graphical assignment for completed base entities; the Modeller launches the same capability for completed composites and maps visual ports to exposed semantic inputs/outputs.
- **Scene objects are transient** — `GraphView` is resolved into `SceneObject[]`; semantic and persistent view data remain outside the renderer.
- **IRI-based semantic contracts** — `SemanticCatalogue` and `ConnectionRuleResolver` interfaces replace the former closed `TypeA/B/C` and `ArcType1/2` unions. An in-memory placeholder implementation exists; a real ontology backend can later supply the same interfaces.
- **Command automaton** — a single `useReducer` in `App.tsx` processes a discriminated-union `Command` type. All state changes go through `applyCommand(state, cmd) → new State`.
- **Shared connection-rule service** — both arc creation and open-arc reconnection go through `connectionService.ts` (`resolveConnection` + `pickArcType`), ensuring a single resolver decides validity and arc type.
- **Catalogue-resolved graphics** — `buildScene` resolves node and arc graphical definitions (fill, stroke, radius, dash, arrowhead) from the `SemanticCatalogue` instead of using hard-coded styles.
- **No branch in palette** — branch/composite nodes are generated by the hierarchy rather than directly placed as primitive model nodes.
- **Open-arc reconnection** — the prototype stores dangling connections during leaf-to-composite conversion and reconnects them through draggable handles. Its final RDF/interface semantics remain to be refined.
- **Three-panel layout** — ancestors (left), children (center), siblings (right), connector (top). Broader multiple-view work described by ADR-003.
- **Interactive knots** — knot positions stored in `knotStore` (Map<arcIri, Knot[]>). Drag to move, double-click to add, right-click to remove.

## Notes

- Default dev server port: 3000
- `NODE_RADIUS = 24`, `STROKE_WIDTH = 2`, `ARROW_SIZE = 10`
- Palette width: 140px
- Arc geometry already supports knots in the polyline calculation.
- **Knot insertion order**: `addKnot` appends to the end of the knot array regardless of where along the arc the user double-clicks. Knots are rendered in array order along the polyline, so a knot added near the source may appear "out of order" if other knots already exist closer to the target. Dragging knots after insertion reorders visually. A future improvement could sort knots by their projection along the polyline.
- Model lifecycle: composition → parameter/constant instantiation → validation → numerical code generation.
- See `docs/ADR-004-model-and-graphical-architecture.md` for the agreed long-term architecture and open design questions.

## Mouse / pointer mapping (as of 2026-09-09)

| Input | Action |
|-------|--------|
| Left click on leaf | Select leaf (and set as connection source) |
| Left click on composite / ancestor / sibling | Zoom to that view |
| Left double-click on leaf | Zoom into leaf view |
| Left double-click on composite | Zoom into composite view |
| Left click on empty canvas | Add node of active palette type (centered coords) |
| Left click on empty canvas in leaf view | Add child and convert leaf into composite |
| Right click on leaf (after selecting source) | Create arc to that leaf (via connection-rule resolver) |
| Right click on leaf (no source selected) | Select as connection source |
| Right click on empty canvas | Cancel pending connection / clear selection |
| Middle press + drag | Pan the canvas |
| Scroll wheel | Zoom in / out |
| Drag red handle on open arc | Reconnect dangling end to nearby leaf |
| Double-click on arc | Add a knot at cursor position |
| Drag knot | Move knot position |
| Double-click on knot | Add a new knot at that position |
| Right-click on knot | Remove knot |
| Delete / Backspace | Remove selected node, arc, or knot |

## Future idea — user-configurable input editor

The command-oriented architecture (event handlers → `Command` → `applyCommand`) keeps input mechanics separate from model and view logic. This means the binding between gestures (left/right/middle click, scroll, keys) and commands can later be exposed to users through a small preferences/editor panel without touching the model or rendering code.
