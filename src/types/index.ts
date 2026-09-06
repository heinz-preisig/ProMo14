export type NodeType = 'capacity' | 'reservoir' | 'constant'

export interface GraphNode {
  id: string;
  x: number;
  y: number;
  label: string;
  nodeType: NodeType
}

export interface NodeTypeDef {
  id: NodeType
  label: string
  fill: string
  stroke: string
  ontologyUri: string
}

export type ArcType = 'flow' | 'state'

export interface Arc {
  id: string;
  sourceId: string;
  targetId: string;
  arcType: ArcType
}

export interface ArcTypeDef {
  id: ArcType
  label: string
  stroke: string
}

export interface ConnectionRule {
  sourceType: NodeType
  targetType: NodeType
  arcType: ArcType
}
