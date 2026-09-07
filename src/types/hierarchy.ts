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
  sourceIri: string    // References ModelNode.iri
  targetIri: string
  arcType: string      // From ontology
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
export type VisibleArcType = 'connection' | 'leftArc' | 'rightArc'

/** An arc visible in a GraphView — computed by projection from flat model arcs. */
export interface VisibleArc {
  /** The original model arc IRI. */
  modelArcIri: string
  sourceId: string   // References VisibleNode.id
  targetId: string   // References VisibleNode.id
  arcType: VisibleArcType
  knots: Knot[]
}

/** A computed GraphView for a specific tree node. Regenerated on demand. */
export interface GraphView {
  treeNodeId: number
  nodes: VisibleNode[]
  arcs: VisibleArc[]
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
