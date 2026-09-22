import type { KonvaEventObject } from 'konva/lib/Node'

export type SceneObjectKind = 'node' | 'arc' | 'openArc' | 'openArcHandle' | 'knot'

export interface SceneInteractions {
  clickable: boolean
  draggable: boolean
  doubleClickable: boolean
  rightClickable: boolean
}

export interface SceneObjectBase {
  id: string
  kind: SceneObjectKind
  interactions: SceneInteractions
  /** Which node/arc is selected when this object is clicked. */
  selectionId?: string
  /** For arcs: the model arc IRI. */
  arcIri?: string
  /** For navigation (double-click zoom). */
  treeNodeId?: number
  /** For open-arc reconnection. */
  modelNodeIri?: string
}

export interface SceneNode extends SceneObjectBase {
  kind: 'node'
  x: number
  y: number
  nodeType: 'leaf' | 'composite' | 'ancestor' | 'sibling' | 'connector'
  label: string
  fill: string
  stroke: string
  radius: number
  width?: number
  height?: number
  entityType?: string
  highlight?: 'valid' | 'invalid'
}

export interface SceneArc extends SceneObjectBase {
  kind: 'arc'
  points: number[]
  arrowX: number
  arrowY: number
  arrowAngle: number
  /** §15: draw the arrowhead at the start end (reference direction
   *  runs opposite to draw order). */
  arrowReversed?: boolean
  stroke: string
  strokeWidth: number
  dash?: number[]
  hitStrokeWidth: number
}

export interface SceneOpenArc extends SceneObjectBase {
  kind: 'openArc'
  points: number[]
  arrowX: number
  arrowY: number
  arrowAngle: number
  /** §15: draw the arrowhead at the start end. */
  arrowReversed?: boolean
  stroke: string
  strokeWidth: number
  dash?: number[]
  hitStrokeWidth: number
  openEndId: string
  openEndTreeNodeId: number
}

export interface SceneHandle extends SceneObjectBase {
  kind: 'openArcHandle'
  x: number
  y: number
  radius: number
  fill: string
  stroke: string
  strokeWidth: number
  openArcIri: string
  fixedX: number
  fixedY: number
  openX: number
  openY: number
}

export interface SceneKnot extends SceneObjectBase {
  kind: 'knot'
  x: number
  y: number
  radius: number
  fill: string
  stroke: string
  strokeWidth: number
  arcIri: string
  knotIndex: number
}

export type SceneObject = SceneNode | SceneArc | SceneOpenArc | SceneHandle | SceneKnot

export interface SceneInteractionHandlers {
  onClick: (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => void
  onRightClick: (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => void
  onDoubleClick: (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => void
  onDragStart: (obj: SceneObject, e: KonvaEventObject<DragEvent>) => void
  onDragMove: (obj: SceneObject, e: KonvaEventObject<DragEvent>) => void
  onDragEnd: (obj: SceneObject, e: KonvaEventObject<DragEvent>) => void
  onMouseEnter: (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => void
  onMouseLeave: (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => void
}
