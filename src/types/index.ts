export interface GraphNode {
  id: string;
  x: number;
  y: number;
  label: string;
}

export interface Arc {
  id: string;
  sourceId: string;
  targetId: string;
}
