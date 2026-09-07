# ADR-002: State Management Sketch

## Current state (flat, non-hierarchical)

```typescript
const [nodes, setNodes] = useState<GraphNode[]>([])
const [arcs, setArcs] = useState<Arc[]>([])
const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
const [selectedArcId, setSelectedArcId] = useState<string | null>(null)
```

The canvas renders `nodes` and `arcs` directly.

## Target state (three-layer hierarchical)

### Layer 1 + 2: Persistent state

```typescript
const [modelNodes, setModelNodes] = useState<Map<string, ModelNode>>(new Map())
const [modelArcs, setModelArcs] = useState<Map<string, ModelArc>>(new Map())
const [tree, setTree] = useState<Tree>({
  rootId: 0,
  nodes: new Map([[0, { id: 0, parentId: null, children: [], label: 'Root' }]]),
  nextId: 0,
})
```

### Layer 3: View state (computed, not persisted)

```typescript
const [currentViewNodeId, setCurrentViewNodeId] = useState<number>(0)
```

The `GraphView` is computed on every render (or memoized):

```typescript
const graphView = useMemo(
  () => computeGraphView(currentViewNodeId, tree, modelNodes, modelArcs),
  [currentViewNodeId, tree, modelNodes, modelArcs]
)
```

### Selection state

```typescript
const [selectedVisibleNodeId, setSelectedVisibleNodeId] = useState<string | null>(null)
const [selectedModelArcIri, setSelectedModelArcIri] = useState<string | null>(null)
```

Selection refers to entities in the **current view**:
- Click a leaf in center → select its IRI
- Click a composite in center → navigate into it (`setCurrentViewNodeId`)
- Click an ancestor on left margin → navigate up (`setCurrentViewNodeId`)
- Click a sibling on right margin → navigate into that sibling's view

## Key operations

### Create node (in current composite view)

```typescript
function createNode(x: number, y: number) {
  // 1. Generate new IRI for the leaf
  const iri = generateIri()
  // 2. Create model node
  setModelNodes(prev => new Map(prev).set(iri, { iri, entityType: activeEntityType, label: iri }))
  // 3. Add as child of current view node in tree
  setTree(prev => {
    const next = cloneTree(prev)
    const newId = next.nextId + 1
    next.nextId = newId
    next.nodes.set(newId, { id: newId, parentId: currentViewNodeId, children: [], label: iri })
    next.nodes.get(currentViewNodeId)!.children.push(newId)
    return next
  })
  // 4. Position is stored in GraphView — but GraphView is computed!
  //    Solution: store positions separately, keyed by (viewNodeId, entityId)
}
```

**Problem discovered**: `GraphView` is computed, so positions can't live in it. We need a separate **layout store**.

### Layout store

```typescript
// Map: viewNodeId → entityId → {x, y}
// For leaves: entityId = modelNodeIri
// For composites: entityId = treeNodeId (as string)
const [layoutStore, setLayoutStore] = useState<Map<number, Map<string, { x: number; y: number }>>>(new Map())
```

When computing `GraphView`, node positions come from `layoutStore.get(viewNodeId)?.get(entityId)`.

If no position exists, auto-layout (e.g., grid or force-directed) assigns one and stores it.

### Create arc

```typescript
function createArc(sourceIri: string, targetIri: string) {
  const arcIri = generateIri()
  setModelArcs(prev => new Map(prev).set(arcIri, {
    iri: arcIri, sourceIri, targetIri, arcType: activeArcType
  }))
}
```

### Zoom into composite (double-click)

```typescript
function zoomInto(treeNodeId: number) {
  setCurrentViewNodeId(treeNodeId)
  setSelectedVisibleNodeId(null)
}
```

### Zoom to ancestor (click on left margin)

```typescript
function zoomToAncestor(treeNodeId: number) {
  setCurrentViewNodeId(treeNodeId)
}
```

### Convert leaf to composite (zoom into leaf with new nodes)

When a leaf (model node) is "zoomed into" and the user adds a new node:

```typescript
function expandLeaf(treeNodeId: number, newChildIri: string) {
  // 1. Remove the model node IRI from flat graph
  const leafNode = tree.nodes.get(treeNodeId)!
  const oldIri = leafNode.label // the leaf's IRI
  setModelNodes(prev => {
    const next = new Map(prev)
    next.delete(oldIri)
    return next
  })
  // 2. Convert leaf to composite: it keeps its tree ID but now has children
  // 3. Add new child leaf
  // 4. Arcs connected to oldIri become open ends
  //    (their target/source is now the connector node in the new composite view)
}
```

## Data flow summary

```
User action
    ↓
Update ModelState (modelNodes, modelArcs, tree, layoutStore)
    ↓
Recompute GraphView (on demand)
    ↓
Render visible nodes + arcs
```

## Serialization format

### File 1: Model — RDF/Turtle

The flat model graph (Layer 1) is serialized as RDF/Turtle. This is the semantic layer.

```turtle
@prefix promo: <http://promo.example.org/> .

promo:Model/Reactor_A1 a promo:Reactor ;
    promo:label "Reactor A1" .

promo:Model/Feed_A a promo:Feed ;
    promo:label "Feed A" .

promo:Arc/1 a promo:Arc ;
    promo:source promo:Model/Feed_A ;
    promo:target promo:Model/Reactor_A1 ;
    promo:arcType promo:flow .
```

IRIs are self-contained in this file. The ontology defines the classes and properties.

### File 2: View definition — JSON

The tree hierarchy + layout positions (Layer 2 + 3) are serialized as JSON.

```json
{
  "tree": {
    "rootId": 0,
    "nextId": 5,
    "nodes": [
      { "id": 0, "parentId": null, "children": [1, 2], "label": "Root" },
      { "id": 1, "parentId": 0, "children": [3, 4], "label": "R" },
      { "id": 2, "parentId": 0, "children": [], "label": "S" },
      { "id": 3, "parentId": 1, "children": [], "label": "Reactor A1", "iri": "promo:Model/Reactor_A1" },
      { "id": 4, "parentId": 1, "children": [], "label": "Feed A", "iri": "promo:Model/Feed_A" }
    ]
  },
  "layouts": {
    "0": {
      "1": { "x": 100, "y": 100 },
      "2": { "x": 300, "y": 100 }
    },
    "1": {
      "3": { "x": 150, "y": 200 },
      "4": { "x": 350, "y": 200 }
    }
  }
}
```

### Key design decisions

- **Model and view are separate files** — multiple views can reference the same model
- **GraphView is not persisted** — always computed on demand
- **Turtle for model** — human-readable, standard format, works with RDF tooling
- **JSON for view** — simple, easy to manipulate programmatically
- **Leaf tree nodes carry `iri` field** — explicit link to model node IRI
- **Composites have no `iri`** — purely organizational
