# ProMo14 — Browser-based Model Composer Prototype

**Date:** 2026-09-09
**Version:** 0.0.1

## What is this?

A prototype for a new browser-based graphical modeller ("ModelComposer") for the ProMo project. It runs entirely in the browser using React + Konva for canvas rendering.

## Architecture concepts

- **GraphView** — the main editing surface containing nodes, arcs, and knots.
- **Tree hierarchy** — each GraphView is a node in a tree. Internal nodes = composite systems (branches). Leaf nodes = primitive graphs whose node types are ontology-defined.
- **One panel for now** — the flat model graph editor. Parent/sibling panels (hierarchy navigation) are planned for later.
- **Nodes** — typed leaf nodes from the ontology (currently generic placeholders: TypeA, TypeB, TypeC).
- **Arcs** — directed, typed connections between nodes (currently generic placeholders: ArcType1, ArcType2).
- **Knots** — graphical waypoints on arcs to route them around objects.
- **Open arcs** — arcs with one end left dangling when a leaf is converted into a composite. The open end is shown with a red handle and can be dragged onto another leaf to reconnect.
- **Connection rules** — which node types may connect to which via which arc type, enforced at runtime.
- **Scene objects** — computed graphical objects (`node`, `arc`, `openArc`, and `openArcHandle`) form one declarative rendering and interaction layer between `GraphView` and Konva.
- **Model architecture direction** — the final model is a flat RDF topology whose nodes reference separately defined base entities, with a separate hierarchy and layout mapping.

## Current features

| Feature | Status |
|---------|--------|
| Click canvas to add node | 
| Click node to select | 
| Click second node to create directed arc | 
| Drag nodes to move (arcs follow) | 
| Select arc and press Delete to remove | 
| Directed arcs with arrowheads | 
| Node types from palette | 
| Arc types (solid / dashed) | 
| Connection rules enforced |  Placeholder types only; ontology-backed resolver pending |
| Knot structure in arcs (geometry supports them) | 
| Open-arc reconnection via red drag handle | 
| Declarative `SceneObject[]` rendering layer | 
| Uniform scene interaction dispatch | 
| Interactive knot creation | 
| Visual feedback for invalid connections | 
| Parent/sibling projection | 
| Multiple GraphView panels | 
| Ontology integration | 

## Tech stack

- React 18 + TypeScript
- Vite (build tool)
- Konva + React-Konva (canvas rendering)

## File structure

```
ProMo14/
├── src/
│   ├── App.tsx                   # Main component (canvas, palette, properties, rules)
│   ├── main.tsx                  # React entry point
│   ├── state/
│   │   ├── ModelState.ts         # AppState, Command union, applyCommand reducer
│   │   └── ModelState.test.ts    # Reducer tests
│   ├── model/
│   │   └── ModelGraph.ts         # Flat model graph operations
│   ├── tree/
│   │   ├── Tree.ts               # Hierarchy tree operations
│   │   └── computeGraphView.ts   # Compute visible nodes/arcs/openArcs
│   ├── canvas/
│   │   └── useCanvasEvents.ts    # Stage events + uniform SceneObject interactions
│   ├── scene/
│   │   ├── types.ts              # SceneObject union and interaction contracts
│   │   ├── buildScene.ts         # GraphView → declarative SceneObject[]
│   │   └── SceneRenderer.tsx     # Generic Konva scene renderer
│   ├── types/
│   │   ├── index.ts              # Generic graph types
│   │   └── hierarchy.ts          # Model / tree / view type system
│   └── vite-env.d.ts             # Vite env types
├── docs/
│   ├── ADR-001-hierarchy.md
│   ├── ADR-002-state-management.md
│   ├── ADR-003-multiple-views.md
│   └── ADR-004-model-and-graphical-architecture.md
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── progress.txt
└── STATUS.md                     # This file
```

## How to run

```bash
cd /home/heinz/1_Gits/CAM14/ProMo14
npm install
npm run dev      # development server
npm run build    # production build
```

## Next planned steps

### Phase 1 — Stabilize the scene layer

1. Add focused tests for `buildScene` covering nodes, arcs, open arcs, handles, selection state, and interaction descriptors.
2. Verify scene interaction dispatch for selection, dragging, navigation, deletion, and open-arc reconnection.

### Phase 2 — Generic semantic contracts

3. Define stable IRI-based contracts for base entities, domains, open-ended classifications, tokens, interfaces, graphical definitions, and connection-rule results.
4. Add an in-memory placeholder catalogue and replace the closed `TypeA/B/C` and `ArcType1/2` unions without requiring ontology infrastructure yet.

### Phase 3 — Rules and graphical resolution

5. Move connection decisions behind a generic rule resolver shared by arc creation and reconnection.
6. Add valid/invalid target feedback and an arc-type selector when several rules match.
7. Replace hard-coded `buildScene` styles with externally assigned graphical definitions.

### Phase 4 — Graph editing and persistence

8. Add interactive knot scene objects and waypoint commands.
9. Define serialization boundaries for flat RDF topology, hierarchy/layout data, and graphical assignments.

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
- **Generic placeholders** — `TypeA/B/C` and `ArcType1/2` remain temporary until ontology-backed catalogues are integrated.
- **No branch in palette** — branch/composite nodes are generated by the hierarchy rather than directly placed as primitive model nodes.
- **Open-arc reconnection** — the prototype stores dangling connections during leaf-to-composite conversion and reconnects them through draggable handles. Its final RDF/interface semantics remain to be refined.
- **Three-panel layout** — parent/current/sibling navigation remains the planned projection, with broader multiple-view work described by ADR-003.

## Notes

- Default dev server port: 3000
- `NODE_RADIUS = 24`, `STROKE_WIDTH = 2`, `ARROW_SIZE = 10`
- Palette width: 140px
- Arc geometry already supports knots in the polyline calculation.
- Model lifecycle: composition → parameter/constant instantiation → validation → numerical code generation.
- See `docs/ADR-004-model-and-graphical-architecture.md` for the agreed long-term architecture and open design questions.

## Mouse / pointer mapping (as of 2026-09-08)

| Input | Action |
|-------|--------|
| Left click on leaf | Select leaf |
| Left click on composite / ancestor / sibling | Zoom to that view |
| Left double-click on leaf | Convert leaf to composite and zoom in |
| Left click on empty canvas | Add node of active palette type |
| Right click on node | Start / finish connection (or cancel) |
| Right click on empty canvas | Cancel pending connection |
| Middle press + drag | Pan the canvas |
| Scroll wheel | Zoom in / out |
| Drag red handle on open arc | Reconnect dangling end to another leaf |
| Delete / Backspace | Remove selected node or arc |

## Future idea — user-configurable input editor

The command-oriented architecture (event handlers → `Command` → `applyCommand`) keeps input mechanics separate from model and view logic. This means the binding between gestures (left/right/middle click, scroll, keys) and commands can later be exposed to users through a small preferences/editor panel without touching the model or rendering code.
