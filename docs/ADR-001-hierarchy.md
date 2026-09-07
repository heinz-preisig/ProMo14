# ADR-001: Tree Hierarchy of GraphViews

## Status
Draft — under discussion

## Context

ProMo14 needs to support hierarchical organization of model graphs. The flat graph may contain millions of nodes. A strict tree hierarchy overlays the flat model graph, partitioning it into subgraphs. Each tree node has a corresponding `GraphView` used for visual editing.

This ADR is based on analysis of the old ProMo `modeller_model_data.py` and `modeller_commander.py` code, plus user clarifications.

## Key differences from old ProMo

| Aspect | Old ProMo | ProMo14 |
|--------|-----------|---------|
| Identity | Single integer ID for tree node AND model node | Separate: IRI for model nodes (leaves), integer for tree nodes |
| Flat graph | The tree IS the model graph | Flat graph = all leaves + arcs between them |
| Leaf content | One model node per leaf | Leaves ARE model nodes (one-to-one) |
| Composites | Tree node with children | Internal tree nodes, purely organizational, no IRI |
| Zoom into primitive | Primitive view shows connector node | Primitive IS the model node; zooming converts it to composite |

## Three-layer architecture

### Layer 1: Flat Model Graph (semantic, persistent)

The single source of truth for code generation. Never rendered as a whole.

```typescript
interface ModelNode {
  iri: string           // Unique IRI — the canonical identity
  entityType: string     // From ontology (e.g. "promo:Reactor")
  // No layout data — purely semantic
}

interface ModelArc {
  iri: string
  sourceIri: string      // References ModelNode.iri
  targetIri: string
  arcType: string        // From ontology
}
```

### Layer 2: Hierarchy Tree (organizational, strict tree)

Adapted from `treeid.py`. Integer IDs.

```typescript
interface TreeNode {
  id: number
  parentId: number | null
  children: number[]     // Direct child tree node IDs
  label: string
}
```

**Key rule**: Leaves are model nodes. Internal nodes are composites.
- A **leaf** (`children.length === 0`) has an IRI and is part of the flat model graph
- An **internal node** is purely organizational, no IRI
- The flat model graph consists of all leaves and arcs between them

### Layer 3: GraphViews (visual, editable)

Each tree node (composite or leaf) has a GraphView with layout data.

```typescript
interface GraphView {
  treeNodeId: number
  // Positions of visible entities in this specific view
  // Key: for leaves = modelNodeIri (the leaf itself); for composites = childTreeNodeId
  positions: Map<string, { x: number; y: number }>
  // Arc waypoints (knots) specific to this view
  arcLayouts: Map<string, Knot[]>   // modelArcIri → knots
}
```

## Three-panel layout (from `__putEnvironment`)

Every GraphView has three panels:

| Panel | Content | Old ProMo object type |
|-------|---------|----------------------|
| **Left margin** | Ancestors stacked vertically (parent at bottom, root at top) | `NAMES["parent"]` |
| **Center** | Children of current tree node | `NAMES["node"]` or `NAMES["branch"]` |
| **Right margin** | Siblings of current tree node | `NAMES["sibling"]` |

**For a composite view** (e.g. viewing tree node R):
- Center shows child composites/leaves as boxes (N, O)
- Left shows ancestors (T)
- Right shows siblings (S)

**For a leaf view** (e.g. viewing tree node A, which IS a model node):
- Center shows the leaf itself (A) plus any arcs connecting to it
- Left shows ancestors (N, R, T)
- Right shows siblings (B, C, O, P, Q, etc.)
- If A has external arcs, they connect from A to sibling interface boxes on the right margin

## Arc projection algorithm (adapted from `getArcOnNodeScene`)

Given a flat model arc `sourceIri → targetIri`:

1. Find owner leaves: `sourceLeaf = leafContaining(sourceIri)`, `targetLeaf = leafContaining(targetIri)`
2. If `sourceLeaf == targetLeaf`: arc is **internal**, shown in that leaf's center panel
3. If `sourceLeaf != targetLeaf`:
   - Compute tree paths: `sourcePath = [sourceLeaf] + ancestors(sourceLeaf)`, `targetPath = [targetLeaf] + ancestors(targetLeaf)`
   - Find `commonAncestor = firstCommonNode(sourcePath, targetPath)`
   - For each tree node on the paths between sourceLeaf and commonAncestor (and symmetrically for target):
     - Determine local endpoints by searching: children → siblings → ancestors → self
     - The local endpoint that matches the respective path becomes the visible node on that scene
   - Arc type depends on endpoint classes:
     - `left arc` = connects to an ancestor/intraface (on left margin)
     - `right arc` = connects to a sibling/interface (on right margin)
     - `connection` = both endpoints in center panel

## Arc type rules (from `__redrawScene`)

The old ProMo determined arc type based on the `"class"` of the source and target nodes:

| Source class | Target class | Arc type |
|-------------|-------------|----------|
| interface (sibling) | intraface (ancestor) | right arc |
| interface (sibling) | non-intraface | right arc |
| intraface (ancestor) | interface (sibling) | left arc |
| interface (sibling) | non-intraface | left arc |
| otherwise | interface or intraface | right arc |
| otherwise | otherwise | left arc |

In ProMo14, this maps to:
- **Right arc**: connects from center to right margin (sibling/external node)
- **Left arc**: connects from center to left margin (ancestor) or from left margin to center
- **Connection**: both endpoints in center panel (internal arc)

## Top-down design workflow

This architecture enables a top-down modeling approach:

### Phase 1: High-level design
Create a few leaves (model nodes) with arcs between them. All leaves are children of the root composite. Example: A→B, B→C as children of T.

### Phase 2: Zoom into a leaf (convert leaf → composite)
When the user zooms into leaf A and adds new nodes inside it:
1. A's IRI is **removed** from the flat model graph
2. A becomes a composite (internal node) with new child leaves (new IRIs: A1, A2, ...)
3. External arcs that connected to A become **open ends** inside the composite view
4. The user reconnects these open ends to new child leaves inside the composite

**Example**: Arc B→A in the high-level model. After converting A to composite:
- In A's view: an open end (from B) is shown in the right margin
- User creates A1, A2 inside A and reconnects the open end to A1
- The flat graph now has B→A1 instead of B→A

### Phase 3: Continue refining
The user can recursively zoom into any leaf, converting it to a composite and adding detail. The flat graph always reflects the current leaf set.

**Key invariant**: The flat model graph consists exactly of all current leaves and arcs between them.

## Open questions

### Q1: What do arcs between composites represent?
**Resolved**: Show arcs separately, not bundled. Since arcs have different types (from ontology), bundling would lose type information. Each flat-model arc crossing from R's subtree to S's subtree is drawn as a separate arc in T's view. If needed, arcs of the same type could be visually grouped (e.g., parallel routing), but they remain distinct entities.

### Q2: Selection model
When clicking a node in a GraphView:
- **Leaf view + center**: select the **model node IRI** (the leaf itself)
- **Composite view + center**: select the **child tree node ID**
- **Margin panel**: select the **represented tree node** (ancestor or sibling)

Selection should carry both the semantic identity and the view context.

### Q3: Open ends and reconnection (resolved)
When a leaf is converted to a composite, external arcs become "open ends" connected to the **connector node** at the top center of the view (from old ProMo's `__putEnvironment`).

- The connector node is a visual element representing the current tree node
- External arcs that connected to the converted leaf now connect to the connector node
- To reconnect: drag the arc end from the connector node and drop it onto any valid node visible in the current view (including ancestors/siblings in margins)
- During reconnection, the user can zoom into any visible node to find a valid target
- The model graph is invalid until all open ends are reconnected

### Q4: Creating a new leaf in a composite view (clarified)
When the user creates a new node inside what was leaf A:
1. Generate a new IRI for the new leaf
2. **Convert A from leaf to composite** in the tree (A now has children: the new leaf)
3. Add the new leaf to the flat model graph
4. Position the new leaf in A's GraphView

If A had external arcs, they become open ends connected to A's connector node.

**Resolved**: **Regenerate on demand**. Views are typically <20 nodes (usually ~10), so regeneration is fast enough. This also ensures consistency — the view always reflects the current tree state.

### Q5: Composite views and their "children"
When viewing composite R (children N, O):
- Center shows N and O as boxes
- Label on each box: the tree node's label
- The user can **double-click** any child to zoom into its GraphView (primary navigation)

## Next steps

1. ~~Decide on GraphView regeneration strategy~~ ✅ Done (on-demand)
2. ~~Write definitive TypeScript interfaces for all three layers~~ ✅ Done
3. ~~Sketch state management~~ ✅ Done (ADR-002)
4. ~~Serialization format~~ ✅ Done (RDF/Turtle for model, JSON for tree+layout)
5. Implement
