// ---------------------------------------------------------------------------
// Generic leaf-node types — placeholders for ontology-defined objects.
// The ontology will later provide the real labels, colours, and URIs.
// ---------------------------------------------------------------------------
export type NodeType = 'TypeA' | 'TypeB' | 'TypeC'

export interface GraphNode {
  id: string
  x: number
  y: number
  label: string
  nodeType: NodeType
}

export interface NodeTypeDef {
  id: NodeType
  label: string
  fill: string
  stroke: string
  ontologyUri: string   // e.g. "promo:SomeOntologyClass"
}

// ---------------------------------------------------------------------------
// Arc types — also ontology placeholders.
// ---------------------------------------------------------------------------
export type ArcType = 'ArcType1' | 'ArcType2'

export interface Arc {
  id: string
  sourceId: string
  targetId: string
  arcType: ArcType
  knots: Knot[]         // waypoints the user can add to route the arc
}

export interface ArcTypeDef {
  id: ArcType
  label: string
  stroke: string
  dash?: number[]
}

// ---------------------------------------------------------------------------
// Knot — a pure graphical waypoint on an arc.
// The user can add/remove knots to route arcs around other objects.
// ---------------------------------------------------------------------------
export interface Knot {
  x: number
  y: number
}

// ---------------------------------------------------------------------------
// Connection rule: which node types may be connected by which arc type.
// The ontology will later supply the authoritative rule set.
// ---------------------------------------------------------------------------
export interface ConnectionRule {
  sourceType: NodeType
  targetType: NodeType
  arcType: ArcType
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
