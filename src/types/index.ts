// ---------------------------------------------------------------------------
// Generic leaf-node and arc types — IRI-based, open-ended.
// The placeholder catalogue provides temporary definitions; a real ontology
// backend can later supply the same interfaces without code changes.
// ---------------------------------------------------------------------------
export type NodeType = string
export type ArcType = string

export interface GraphNode {
  id: string
  x: number
  y: number
  label: string
  nodeType: NodeType
}

export interface Arc {
  id: string
  sourceId: string
  targetId: string
  arcType: ArcType
  knots: Knot[]         // waypoints the user can add to route the arc
}

export interface Knot {
  x: number
  y: number
}

// ---------------------------------------------------------------------------
// Re-export hierarchical types (three-layer architecture).
// See docs/ADR-001-hierarchy.md for design rationale.
// ---------------------------------------------------------------------------
export type {
  ModelNode,
  ModelArc,
  TreeNode,
  Tree,
  VisibleNode,
  VisibleArc,
  VisibleArcType,
  VisibleEntityType,
  GraphView,
  ModelState,
  OpenArc,
} from './hierarchy'
