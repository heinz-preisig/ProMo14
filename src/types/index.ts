export type NodeType = 'capacity' | 'branch' | 'intraface' | 'interface'

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
}

export interface Arc {
  id: string;
  sourceId: string;
  targetId: string;
}
