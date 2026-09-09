import type { Tree, ModelNode, ModelArc, GraphView, VisibleNode, VisibleArc, VisibleArcType, OpenArc, Knot } from '../types'
import { TreeOps } from './Tree'

/**
 * Compute a GraphView for the given tree node.
 * This implements the three-panel layout from the old ProMo:
 * - Center: children of current tree node
 * - Left margin: ancestors stacked vertically
 * - Right margin: siblings of current tree node
 */
export function computeGraphView(
  viewNodeId: number,
  tree: Tree,
  modelNodes: Map<string, ModelNode>,
  modelArcs: Map<string, ModelArc>,
  layoutStore: Map<number, Map<string, { x: number; y: number }>>,
  openArcs: Map<number, OpenArc[]>,
  knotStore: Map<string, Knot[]>,
  stageWidth: number,
  stageHeight: number
): GraphView {
  const ops = new TreeOps(tree)
  const viewNode = tree.nodes.get(viewNodeId)
  if (!viewNode) return { treeNodeId: viewNodeId, nodes: [], arcs: [], openArcs: [] }

  const nodes: VisibleNode[] = []
  const arcs: VisibleArc[] = []
  const openArcsOut: VisibleArc[] = []
  const nodeMap = new Map<string, VisibleNode>() // id -> VisibleNode

  const leftEdge = -stageWidth / 2 + 40
  const rightEdge = stageWidth / 2 - 40
  const topEdge = -stageHeight / 2 + 40

  // Helper to get position from layout store or auto-layout
  function getPosition(viewId: number, entityId: string, defaultX: number, defaultY: number) {
    const viewLayouts = layoutStore.get(viewId)
    if (viewLayouts) {
      const pos = viewLayouts.get(entityId)
      if (pos) return pos
    }
    return { x: defaultX, y: defaultY }
  }

  // --- Center panel: children of current tree node ---
  const children = viewNode.children
  const centerStartX = -((children.length - 1) * 100) / 2
  children.forEach((childId: number, i: number) => {
    const child = tree.nodes.get(childId)!
    const isLeaf = child.iri !== undefined
    const id = String(childId)
    const pos = getPosition(viewNodeId, id, centerStartX + i * 100, 0)
    const modelNode = isLeaf ? modelNodes.get(child.iri!) : undefined
    const visibleNode: VisibleNode = {
      id,
      type: isLeaf ? 'leaf' : 'composite',
      x: pos.x,
      y: pos.y,
      label: child.label,
      treeNodeId: childId,
      ...(isLeaf ? { modelNodeIri: child.iri } : {}),
      ...(modelNode ? { entityType: modelNode.entityType } : {}),
    }
    nodes.push(visibleNode)
    nodeMap.set(id, visibleNode)
  })

  // --- Left margin: ancestors ---
  const ancestors = ops.getAncestors(viewNodeId)
  const ancestorSpacing = 50
  const ancestorOffset = 20
  ancestors.forEach((ancestorId: number, i: number) => {
    const ancestor = tree.nodes.get(ancestorId)!
    const id = `ancestor-${ancestorId}`
    const pos = getPosition(viewNodeId, id, leftEdge, topEdge + 40 + ancestorOffset + i * ancestorSpacing)
    const visibleNode: VisibleNode = {
      id,
      type: 'ancestor',
      x: pos.x,
      y: pos.y,
      label: ancestor.label,
      treeNodeId: ancestorId,
    }
    nodes.push(visibleNode)
    nodeMap.set(id, visibleNode)
  })

  // --- Right margin: siblings ---
  const siblings = ops.getSiblings(viewNodeId)
  const siblingSpacing = 50
  const siblingOffset = 20
  siblings.forEach((siblingId: number, i: number) => {
    const sibling = tree.nodes.get(siblingId)!
    const id = `sibling-${siblingId}`
    const pos = getPosition(viewNodeId, id, rightEdge, topEdge + 40 + siblingOffset + i * siblingSpacing)
    const visibleNode: VisibleNode = {
      id,
      type: 'sibling',
      x: pos.x,
      y: pos.y,
      label: sibling.label,
      treeNodeId: siblingId,
    }
    nodes.push(visibleNode)
    nodeMap.set(id, visibleNode)
  })

  // --- Connector node (top center) ---
  if (viewNodeId !== tree.rootId) {
    const id = `connector-${viewNodeId}`
    const pos = getPosition(viewNodeId, id, 0, topEdge)
    const visibleNode: VisibleNode = {
      id,
      type: 'connector',
      x: pos.x,
      y: pos.y,
      label: viewNode.label,
      treeNodeId: viewNodeId,
    }
    nodes.push(visibleNode)
    nodeMap.set(id, visibleNode)
  }

  // --- Arcs: project flat model arcs into this view ---
  // For now, simplified: show arcs between children if both endpoints are in this view
  // Full implementation would use getArcOnNodeScene logic
  for (const [, arc] of modelArcs) {
    // Find owner tree nodes for source and target
    const sourceLeafId = findLeafForModelNode(arc.sourceIri, tree)
    const targetLeafId = findLeafForModelNode(arc.targetIri, tree)

    if (!sourceLeafId || !targetLeafId) continue

    // Check if both endpoints are visible in this view
    const sourceVisibleId = findVisibleId(sourceLeafId, viewNodeId, tree)
    const targetVisibleId = findVisibleId(targetLeafId, viewNodeId, tree)

    if (sourceVisibleId && targetVisibleId && nodeMap.has(sourceVisibleId) && nodeMap.has(targetVisibleId)) {
      const arcType: VisibleArcType = 'connection'
      arcs.push({
        modelArcIri: arc.iri,
        sourceId: sourceVisibleId,
        targetId: targetVisibleId,
        arcType,
        modelArcType: arc.arcType,
        knots: knotStore.get(arc.iri) ?? [],
      })
    }
  }

  // --- Open arcs: dangling ends attached wherever the owning composite is visible ---
  for (const [compositeId, openArcList] of openArcs) {
    const compositeVisibleId = findVisibleId(compositeId, viewNodeId, tree)
    if (!compositeVisibleId || !nodeMap.has(compositeVisibleId)) continue
    for (const openArc of openArcList) {
      const externalLeafId = findLeafForModelNode(openArc.externalIri, tree)
      if (externalLeafId === null) continue
      const externalVisibleId = findVisibleId(externalLeafId, viewNodeId, tree)
      if (externalVisibleId && nodeMap.has(externalVisibleId)) {
        openArcsOut.push({
          modelArcIri: openArc.iri,
          sourceId: openArc.isSource ? compositeVisibleId : externalVisibleId,
          targetId: openArc.isSource ? externalVisibleId : compositeVisibleId,
          arcType: 'open',
          modelArcType: openArc.arcType,
          knots: [],
          openEndId: compositeVisibleId,
          openEndTreeNodeId: compositeId,
        })
      }
    }
  }

  return { treeNodeId: viewNodeId, nodes, arcs, openArcs: openArcsOut }
}

/** Find which leaf tree node owns a given model node IRI. */
function findLeafForModelNode(iri: string, tree: Tree): number | null {
  for (const [id, node] of tree.nodes) {
    if (node.children.length === 0 && node.iri === iri) {
      return id
    }
  }
  return null
}

/**
 * Find the visible ID for a leaf in a given view.
 * If the leaf is a child of the view node, return its tree node ID.
 * If the leaf is an ancestor, return `ancestor-{ancestorId}`.
 * If the leaf is a sibling, return `sibling-{siblingId}`.
 * If the leaf IS the view node, return `connector-{viewNodeId}`.
 */
function findVisibleId(leafId: number, viewNodeId: number, tree: Tree): string | null {
  if (leafId === viewNodeId) return `connector-${viewNodeId}`

  const viewNode = tree.nodes.get(viewNodeId)
  if (!viewNode) return null

  // Is it a direct child?
  if (viewNode.children.includes(leafId)) return String(leafId)

  // Is it an ancestor?
  let current: number | null = viewNodeId
  while (current !== null) {
    const node = tree.nodes.get(current)
    if (!node) break
    if (node.parentId === leafId) return `ancestor-${leafId}`
    current = node.parentId ?? null
  }

  // Is it a sibling?
  if (viewNode.parentId !== null) {
    const parent = tree.nodes.get(viewNode.parentId)
    if (parent && parent.children.includes(leafId)) return `sibling-${leafId}`
  }

  return null
}
