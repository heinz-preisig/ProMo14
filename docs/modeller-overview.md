# Modeller Overview

## Role in the suite

The Modeller is the graphical composition module.  It assembles base
entities (defined upstream by the Ontology Editor, Equation Editor, and
Behaviour Linker) into larger models by placing nodes and drawing
connections.  The resulting model can be published as a reusable entity
and inserted into another model.

See `docs/suite-overview.md` for the full pipeline and cross-cutting
contracts.

## Consumes

- **Base-entity catalogue** — entity types, arc types, domains,
  tokens, interfaces, graphical definitions.  Resolved at runtime
  through `SemanticCatalogue` (`packages/semantic/src/contracts.ts`).
- **Connection rules** — which entity types may connect via which arc
  types.  Resolved through `ConnectionRuleResolver` (same package) →
  `GET /api/ontology/resolve-connection` with the endpoint entity types'
  `domainTypeIris`.  The backend walks domain ancestor chains, filters by
  branch-relative `scope` (same | cross | any), then requires a licensed
  `sharedTokens` entry comparable to a comparable effective-token pair on
  the endpoints — returns matching rules + `matched_tokens`,
  most-specific first.  The rule's `carrier` (token-flow | reference)
  maps to `arcTypeIri = promo:ArcType/<carrier>`; the rule name
  (physical-same, signal, access, sensor, actuation) is the connection
  *kind*, not the arc type.
- **Graphical definitions** — shapes, fills, strokes, port positions.
  Resolved from the catalogue; the Modeller itself is domain-independent.

## Produces

- **Flat RDF topology** — model nodes (referencing base entities) and
  arcs (typed connections).  Every connection exists exactly once.
- **Separate hierarchy** — a tree that partitions and projects the flat
  topology for navigation, grouping, and scalable editing.
- **Layout data** — node positions, arc routing, knot waypoints.

## Key design decisions

| Decision | ADR | Summary |
|----------|-----|---------|
| Flat RDF topology + separate hierarchy | ADR-004 | Authoritative model is a flat graph; hierarchy is organizational, not semantic. |
| Command automaton | ADR-002 | Single `useReducer`; all state changes via `applyCommand(state, cmd) → new State`. |
| Three-layer architecture | ADR-001 | Layer 1: flat model graph. Layer 2: hierarchy tree. Layer 3: GraphViews (computed). |
| Three-panel layout | ADR-001 | Ancestors (left), children (center), siblings (right), connector (top). |
| Multiple GraphView panels | ADR-003 | Planned but not yet implemented. |
| Generic graphical vocabulary | ADR-004 | Modeller implements reusable primitives; ontology data configures them via IRIs. |
| IRI-based semantic contracts | ADR-004 | `SemanticCatalogue` + `ConnectionRuleResolver` replace closed type unions. |
| Scene objects are transient | ADR-004 | `GraphView` → `SceneObject[]` → Konva renderer; semantic data stays outside. |
| Shared Graphic Object Editor | ADR-004 | One editor spawned from Behaviour Linker and Modeller; same vocabulary. |

## Architecture

```
Event → Command → applyCommand(state, cmd) → new State
                                                    │
                         ┌──────────────────────────┤
                         │                          │
                   ModelGraph (flat)          Tree (hierarchy)
                         │                          │
                         └──────────┬───────────────┘
                                    │
                            computeGraphView
                                    │
                              GraphView
                                    │
                         SemanticCatalogue.resolve()
                                    │
                            SceneObject[]
                                    │
                          SceneRenderer (Konva)
```

## Module boundaries

The Modeller must **not** contain:

- Mathematical formalism (equations, Hamiltonians, contact geometry).
- Token-flow laws or effort-variable continuity conditions.
- Event dynamics or transport-system semantics.
- Unit checking or index-structure validation.

These belong to the ontology, equation editor, behaviour, and
validation services.  The Modeller consumes only generic entity
references, resolved graphical definitions, interface descriptions, and
connection-rule results.

## Key files

| File | Purpose |
|------|---------|
| `apps/modeller/src/App.tsx` | Main component, canvas, palette, properties, status bar |
| `apps/modeller/src/state/ModelState.ts` | AppState, Command union, applyCommand reducer |
| `apps/modeller/src/model/ModelGraph.ts` | Flat model graph operations |
| `apps/modeller/src/tree/Tree.ts` | Hierarchy tree operations |
| `apps/modeller/src/tree/computeGraphView.ts` | Compute visible nodes/arcs from tree + model + layout |
| `apps/modeller/src/scene/buildScene.ts` | Resolve GraphView into SceneObject[] |
| `apps/modeller/src/scene/SceneRenderer.tsx` | Generic Konva renderer |
| `apps/modeller/src/canvas/useCanvasEvents.ts` | Stage events and interaction dispatch |
| `packages/semantic/src/contracts.ts` | IRI-based catalogue and rule resolver interfaces |
| `packages/semantic/src/placeholderCatalogue.ts` | In-memory placeholder implementations |
| `packages/semantic/src/connectionService.ts` | Shared connection-rule helpers |

## Interaction with other modules

- **Receives from:** Behaviour Linker (base-entity definitions,
  graphical assignments, connection rules via `SemanticCatalogue`).
- **Sends to:** Model Reuse / Instantiation / Code Generation (flat RDF
  topology + hierarchy + layout).
- **Spawns:** Graphic Object Editor (for composite graphical assignment).
