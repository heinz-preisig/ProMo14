// ---------------------------------------------------------------------------
// Three-layer hierarchical type system for ProMo14
//
// Layer 1: Flat Model Graph — semantic, persistent, IRI-based
// Layer 2: Hierarchy Tree — organizational, integer IDs, strict tree
// Layer 3: GraphViews — visual, editable, computed on demand
// ---------------------------------------------------------------------------

import type { Knot } from './index'

// ===========================================================================
// Layer 1: Flat Model Graph (semantic)
// ===========================================================================

/** A model node is a leaf in the tree and has a unique IRI. */
export interface ModelNode {
  iri: string           // Unique IRI — e.g. "promo:Model/Reactor_A1"
  entityType: string   // From ontology (e.g. "promo:Reactor")
  label: string
  // No layout data — purely semantic
}

/** A model arc connects two model nodes in the flat graph. */
export interface ModelArc {
  iri: string
  sourceIri: string    // References ModelNode.iri — draw order, no semantics
  targetIri: string
  arcType: string      // From ontology
  /** §15 semantic reference direction (positive flow) — token-flow arcs
   *  only.  Absent means draw order (sourceIri → targetIri). */
  referenceFrom?: string
  referenceTo?: string
}

// ===========================================================================
// Layer 2: Hierarchy Tree (organizational)
// Adapted from treeid.py — integer IDs, strict tree
// ===========================================================================

export interface TreeNode {
  id: number
  parentId: number | null
  children: number[]   // Direct child tree node IDs
  label: string
  /** For leaves: the canonical model node IRI. For composites: undefined. */
  iri?: string
}

/** The tree structure, similar to treeid.py's Tree class. */
export interface Tree {
  rootId: number
  nodes: Map<number, TreeNode>  // id → TreeNode
  nextId: number                 // for generating new IDs
}

// ===========================================================================
// Layer 3: GraphViews (visual, computed on demand)
// ===========================================================================

/** What type of entity is visible in a GraphView. */
export type VisibleEntityType =
  | 'leaf'       // a model node (leaf in the tree)
  | 'composite'  // a child composite node
  | 'ancestor'   // on the left margin
  | 'sibling'    // on the right margin
  | 'connector'  // top-center, represents the current tree node

/** A node visible in a GraphView — may be internal, ancestor, sibling, or connector. */
export interface VisibleNode {
  /** For leaves: the model node IRI. For composites/ancestors/siblings/connector: the tree node ID as string. */
  id: string
  type: VisibleEntityType
  x: number
  y: number
  label: string
  /** For leaves: the model node IRI. For others: undefined. */
  modelNodeIri?: string
  /** For non-leaves: the tree node ID. For leaves: undefined. */
  treeNodeId?: number
  /** For leaves: the entity type from the model node. For others: undefined. */
  entityType?: string
}

/** Arc type as determined by endpoint classes in the old ProMo __redrawScene. */
export type VisibleArcType = 'connection' | 'leftArc' | 'rightArc' | 'open'

/** An arc visible in a GraphView — computed by projection from flat model arcs. */
export interface VisibleArc {
  /** The original model arc IRI. */
  modelArcIri: string
  sourceId: string   // References VisibleNode.id
  targetId: string   // References VisibleNode.id
  /** Visual category used for rendering (connection, leftArc, rightArc, open). */
  arcType: VisibleArcType
  /** Original ontology arc type string (e.g. ArcType1, ArcType2). */
  modelArcType: string
  knots: Knot[]
  /** For arcType === 'open': the visible node id of the composite/connector that owns the open end. */
  openEndId?: string
  /** For arcType === 'open': the tree node id of the composite that owns the open end. */
  openEndTreeNodeId?: number
  /** §15: true when the reference direction runs target→source in this
   *  view's draw order — the arrowhead renders at the start end. */
  referenceReversed?: boolean
}

/** A computed GraphView for a specific tree node. Regenerated on demand. */
export interface GraphView {
  treeNodeId: number
  nodes: VisibleNode[]
  arcs: VisibleArc[]
  openArcs: VisibleArc[]
}

// ===========================================================================
// Open arcs: dangling connections left when a leaf is converted to a composite
// ===========================================================================

/** An open arc is an arc whose endpoint was removed when its owning leaf became a composite.
 *  The open end attaches to the connector node of the composite view until reconnected. */
export interface OpenArc {
  iri: string           // Original model arc IRI (preserved for reconnection)
  externalIri: string   // Model node IRI that still exists on the other side
  arcType: string       // Ontology arc type
  isSource: boolean     // True if the removed leaf was the source (connector now acts as source)
  /** §15: does the reference direction point toward the external node?
   *  Boundary-relative so it survives leaf→composite→leaf.  Undefined
   *  on non-token-flow arcs (their direction is inherent). */
  refToExternal?: boolean
}

// ===========================================================================
// Application state
// ===========================================================================

/** The complete application state for the hierarchical model. */
export interface ModelState {
  /** Layer 1: flat model graph — the single source of truth. */
  modelNodes: Map<string, ModelNode>   // iri → ModelNode
  modelArcs: Map<string, ModelArc>     // iri → ModelArc

  /** Layer 2: hierarchy tree. */
  tree: Tree

  /** Layer 3: GraphViews — computed, not persisted. */
  currentViewNodeId: number | null     // which tree node is currently being viewed
}
