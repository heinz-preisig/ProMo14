import type { GraphView, VisibleNode } from '../types'
import type {
  SceneObject,
  SceneNode,
  SceneArc,
  SceneOpenArc,
  SceneHandle,
  SceneKnot,
} from './types'
import type {
  SemanticCatalogue,
  NodeGraphicalDefinition,
  ArcGraphicalDefinition,
} from '../semantic/contracts'

const NODE_RADIUS = 24
const COMPOSITE_WIDTH = 80
const COMPOSITE_HEIGHT = 60
const ARROW_SIZE = 10

function rimPoint(x1: number, y1: number, x2: number, y2: number, radius: number) {
  const dx = x2 - x1
  const dy = y2 - y1
  const len = Math.hypot(dx, dy)
  if (len === 0) return { x: x1, y: y1 }
  return { x: x1 + (dx / len) * radius, y: y1 + (dy / len) * radius }
}

function arrowPoints(x: number, y: number, angleRad: number) {
  const cos = Math.cos(angleRad)
  const sin = Math.sin(angleRad)
  const ax = x - cos * ARROW_SIZE
  const ay = y - sin * ARROW_SIZE
  const lx = ax + sin * (ARROW_SIZE * 0.6)
  const ly = ay - cos * (ARROW_SIZE * 0.6)
  const rx = ax - sin * (ARROW_SIZE * 0.6)
  const ry = ay + cos * (ARROW_SIZE * 0.6)
  return [lx, ly, x, y, rx, ry]
}

function rimPointForNode(node: VisibleNode, towardX: number, towardY: number) {
  if (node.type === 'composite') {
    return rimPointRect(node.x, node.y, towardX, towardY, COMPOSITE_WIDTH, COMPOSITE_HEIGHT)
  }
  return rimPoint(node.x, node.y, towardX, towardY, NODE_RADIUS)
}

function rimPointRect(
  cx: number, cy: number, tx: number, ty: number,
  width: number, height: number,
) {
  const dx = tx - cx
  const dy = ty - cy
  if (dx === 0 && dy === 0) return { x: cx, y: cy }
  const halfW = width / 2
  const halfH = height / 2
  const scale = Math.min(halfW / Math.abs(dx || 1), halfH / Math.abs(dy || 1))
  return { x: cx + dx * scale, y: cy + dy * scale }
}

function getArcGeometry(
  arc: { sourceId: string; targetId: string; knots: { x: number; y: number }[] },
  nodeMap: Map<string, VisibleNode>
) {
  const src = nodeMap.get(arc.sourceId)
  const tgt = nodeMap.get(arc.targetId)
  if (!src || !tgt) return null

  const pts: number[] = []
  const k0 = arc.knots.length > 0 ? arc.knots[0] : tgt
  const pStart = rimPointForNode(src, k0.x, k0.y)
  pts.push(pStart.x, pStart.y)

  for (const k of arc.knots) {
    pts.push(k.x, k.y)
  }

  const kLast = arc.knots.length > 0 ? arc.knots[arc.knots.length - 1] : src
  const pEnd = rimPointForNode(tgt, kLast.x, kLast.y)
  pts.push(pEnd.x, pEnd.y)

  const prevX = arc.knots.length > 0 ? arc.knots[arc.knots.length - 1].x : src.x
  const prevY = arc.knots.length > 0 ? arc.knots[arc.knots.length - 1].y : src.y
  const angle = Math.atan2(pEnd.y - prevY, pEnd.x - prevX)

  return { points: pts, arrowAngle: angle, arrowX: pEnd.x, arrowY: pEnd.y }
}

function resolveNodeGraphical(
  entityType: string | undefined,
  catalogue: SemanticCatalogue,
): NodeGraphicalDefinition | undefined {
  if (!entityType) return undefined
  const entity = catalogue.getBaseEntity(entityType)
  if (!entity?.graphicalDefinitionIri) return undefined
  const g = catalogue.getGraphicalDefinition(entity.graphicalDefinitionIri)
  if (g?.kind === 'node') return g
  return undefined
}

function resolveArcGraphical(
  arcTypeIri: string,
  catalogue: SemanticCatalogue,
): ArcGraphicalDefinition | undefined {
  const arcType = catalogue.getArcType(arcTypeIri)
  if (!arcType?.graphicalDefinitionIri) return undefined
  const g = catalogue.getGraphicalDefinition(arcType.graphicalDefinitionIri)
  if (g?.kind === 'arc') return g
  return undefined
}

function buildNodeSceneObject(
  node: VisibleNode,
  isSelected: boolean,
  highlight: 'valid' | 'invalid' | undefined,
  catalogue: SemanticCatalogue,
): SceneNode {
  const isComposite = node.type === 'composite'
  const isLeaf = node.type === 'leaf'
  const isAncestor = node.type === 'ancestor'
  const isSibling = node.type === 'sibling'

  const g = resolveNodeGraphical(node.entityType, catalogue)

  let fill: string
  let stroke: string
  let radius = g?.radius ?? NODE_RADIUS
  let width = isComposite ? COMPOSITE_WIDTH : undefined
  let height = isComposite ? COMPOSITE_HEIGHT : undefined

  if (isSelected) {
    fill = '#3498db'
    stroke = '#2980b9'
  } else if (isComposite) {
    fill = '#e8f4fd'
    stroke = '#2980b9'
  } else if (isAncestor) {
    fill = '#f0e68c'
    stroke = '#666'
  } else if (isSibling) {
    fill = '#dda0dd'
    stroke = '#666'
  } else {
    fill = g?.fill ?? '#e8f4fd'
    stroke = g?.stroke ?? '#666'
  }

  return {
    id: node.id,
    kind: 'node',
    x: node.x,
    y: node.y,
    nodeType: node.type,
    label: node.label,
    fill,
    stroke,
    radius,
    width,
    height,
    entityType: node.entityType,
    treeNodeId: node.treeNodeId,
    modelNodeIri: node.modelNodeIri,
    selectionId: node.id,
    highlight,
    interactions: {
      clickable: true,
      draggable: isLeaf || isComposite,
      doubleClickable: node.treeNodeId !== undefined,
      rightClickable: true,
    },
  }
}

export interface BuildSceneOptions {
  graphView: GraphView
  selectedNodeId: string | null
  selectedArcIri: string | null
  draggingOpenArc: {
    openArcIri: string
    fixedX: number
    fixedY: number
    currentX: number
    currentY: number
  } | null
  hoveredNodeId?: string | null
  hoveredHighlight?: 'valid' | 'invalid' | null
  catalogue: SemanticCatalogue
}

export function buildScene(options: BuildSceneOptions): SceneObject[] {
  const { graphView, selectedNodeId, selectedArcIri, draggingOpenArc, hoveredNodeId, hoveredHighlight, catalogue } = options
  const objects: SceneObject[] = []
  const nodeMap = new Map<string, VisibleNode>()

  for (const node of graphView.nodes) {
    nodeMap.set(node.id, node)
  }

  // --- Arcs (bottom layer) ---
  for (const arc of graphView.arcs) {
    const geom = getArcGeometry(arc, nodeMap)
    if (!geom) continue
    const isSelected = arc.modelArcIri === selectedArcIri
    const g = resolveArcGraphical(arc.modelArcType, catalogue)
    const obj: SceneArc = {
      id: `arc-${arc.modelArcIri}`,
      kind: 'arc',
      points: geom.points,
      arrowX: geom.arrowX,
      arrowY: geom.arrowY,
      arrowAngle: geom.arrowAngle,
      stroke: isSelected ? '#e74c3c' : (g?.stroke ?? '#333'),
      strokeWidth: isSelected ? 3 : (g?.strokeWidth ?? 2),
      dash: g?.dash,
      hitStrokeWidth: 12,
      arcIri: arc.modelArcIri,
      interactions: {
        clickable: true,
        draggable: false,
        doubleClickable: true,
        rightClickable: false,
      },
    }
    objects.push(obj)
  }

  // --- Open arcs ---
  for (const arc of graphView.openArcs) {
    const geom = getArcGeometry(arc, nodeMap)
    if (!geom) continue
    const g = resolveArcGraphical(arc.modelArcType, catalogue)
    const obj: SceneOpenArc = {
      id: `open-arc-${arc.modelArcIri}`,
      kind: 'openArc',
      points: geom.points,
      arrowX: geom.arrowX,
      arrowY: geom.arrowY,
      arrowAngle: geom.arrowAngle,
      stroke: g?.stroke ?? '#333',
      strokeWidth: g?.strokeWidth ?? 2,
      dash: g?.dash,
      hitStrokeWidth: 12,
      openEndId: arc.openEndId ?? '',
      openEndTreeNodeId: arc.openEndTreeNodeId ?? 0,
      interactions: {
        clickable: false,
        draggable: false,
        doubleClickable: false,
        rightClickable: false,
      },
    }
    objects.push(obj)
  }

  // --- Knots (between arcs and nodes, above arcs) ---
  for (const arc of graphView.arcs) {
    for (let i = 0; i < arc.knots.length; i++) {
      const knot = arc.knots[i]
      const obj: SceneKnot = {
        id: `knot-${arc.modelArcIri}-${i}`,
        kind: 'knot',
        x: knot.x,
        y: knot.y,
        radius: 6,
        fill: '#fff',
        stroke: '#333',
        strokeWidth: 2,
        arcIri: arc.modelArcIri,
        knotIndex: i,
        interactions: {
          clickable: true,
          draggable: true,
          doubleClickable: true,
          rightClickable: true,
        },
      }
      objects.push(obj)
    }
  }

  // --- Nodes ---
  for (const node of graphView.nodes) {
    const isSelected = node.id === selectedNodeId
    const isHovered = node.id === hoveredNodeId
    const nodeHighlight = isHovered ? hoveredHighlight ?? undefined : undefined
    objects.push(buildNodeSceneObject(node, isSelected, nodeHighlight, catalogue))
  }

  // --- Open arc handles (top layer) ---
  for (const arc of graphView.openArcs) {
    const geom = getArcGeometry(arc, nodeMap)
    if (!geom) continue
    const isOpenEndSource = arc.sourceId === arc.openEndId
    const openX = isOpenEndSource ? geom.points[0] : geom.points[geom.points.length - 2]
    const openY = isOpenEndSource ? geom.points[1] : geom.points[geom.points.length - 1]
    const fixedX = isOpenEndSource ? geom.points[geom.points.length - 2] : geom.points[0]
    const fixedY = isOpenEndSource ? geom.points[geom.points.length - 1] : geom.points[1]

    const isDraggingThis = draggingOpenArc?.openArcIri === arc.modelArcIri
    const handleX = isDraggingThis ? draggingOpenArc.currentX : openX
    const handleY = isDraggingThis ? draggingOpenArc.currentY : openY

    const obj: SceneHandle = {
      id: `handle-${arc.modelArcIri}`,
      kind: 'openArcHandle',
      x: handleX,
      y: handleY,
      radius: 10,
      fill: '#c0392b',
      stroke: '#fff',
      strokeWidth: 3,
      openArcIri: arc.modelArcIri,
      fixedX,
      fixedY,
      openX,
      openY,
      interactions: {
        clickable: true,
        draggable: true,
        doubleClickable: false,
        rightClickable: false,
      },
    }
    objects.push(obj)
  }

  return objects
}

export { arrowPoints, rimPoint }
