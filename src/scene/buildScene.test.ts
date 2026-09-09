import { describe, expect, it } from 'vitest'
import type { GraphView, VisibleNode } from '../types'
import { buildScene } from './buildScene'
import type { SceneArc, SceneHandle, SceneKnot, SceneNode, SceneOpenArc } from './types'
import { placeholderCatalogue } from '../semantic/placeholderCatalogue'

const leafA: VisibleNode = {
  id: 'node-a',
  type: 'leaf',
  x: 0,
  y: 0,
  label: 'A',
  modelNodeIri: 'model:A',
  entityType: 'promo:TypeA',
}

const leafB: VisibleNode = {
  id: 'node-b',
  type: 'leaf',
  x: 100,
  y: 0,
  label: 'B',
  modelNodeIri: 'model:B',
  entityType: 'promo:TypeB',
}

function graphView(overrides: Partial<GraphView> = {}): GraphView {
  return {
    treeNodeId: 0,
    nodes: [leafA, leafB],
    arcs: [],
    openArcs: [],
    ...overrides,
  }
}

function build(view: GraphView, overrides: Partial<Parameters<typeof buildScene>[0]> = {}) {
  return buildScene({
    graphView: view,
    selectedNodeId: null,
    selectedArcIri: null,
    draggingOpenArc: null,
    catalogue: placeholderCatalogue,
    ...overrides,
  })
}

describe('buildScene', () => {
  it('builds styled nodes with interaction descriptors and selection state', () => {
    const composite: VisibleNode = {
      id: 'tree-3',
      type: 'composite',
      x: 40,
      y: 50,
      label: 'Composite',
      treeNodeId: 3,
    }

    const objects = build(graphView({ nodes: [leafA, composite] }), {
      selectedNodeId: leafA.id,
    })
    const nodes = objects.filter((object): object is SceneNode => object.kind === 'node')

    expect(nodes).toHaveLength(2)
    expect(nodes[0]).toMatchObject({
      id: 'node-a',
      fill: '#3498db',
      stroke: '#2980b9',
      selectionId: 'node-a',
      modelNodeIri: 'model:A',
      interactions: {
        clickable: true,
        draggable: true,
        doubleClickable: false,
        rightClickable: true,
      },
    })
    expect(nodes[1]).toMatchObject({
      id: 'tree-3',
      width: 80,
      height: 60,
      treeNodeId: 3,
      interactions: {
        clickable: true,
        draggable: true,
        doubleClickable: true,
        rightClickable: true,
      },
    })
  })

  it('applies view-role styles and navigation interactions', () => {
    const nodes: VisibleNode[] = [
      { id: 'ancestor', type: 'ancestor', x: 0, y: 0, label: 'Ancestor', treeNodeId: 1 },
      { id: 'sibling', type: 'sibling', x: 10, y: 0, label: 'Sibling', treeNodeId: 2 },
      { id: 'connector', type: 'connector', x: 20, y: 0, label: 'Connector', treeNodeId: 3 },
    ]

    const sceneNodes = build(graphView({ nodes })).filter(
      (object): object is SceneNode => object.kind === 'node'
    )

    expect(sceneNodes.map(({ fill }) => fill)).toEqual(['#f0e68c', '#dda0dd', '#e8f4fd'])
    expect(sceneNodes.every((node) => !node.interactions.draggable)).toBe(true)
    expect(sceneNodes.every((node) => node.interactions.doubleClickable)).toBe(true)
  })

  it('builds routed arc geometry, styles, hit area, and selection', () => {
    const objects = build(
      graphView({
        arcs: [{
          modelArcIri: 'arc:1',
          sourceId: leafA.id,
          targetId: leafB.id,
          arcType: 'connection',
          modelArcType: 'promo:ArcType2',
          knots: [{ x: 50, y: 30 }],
        }],
      }),
      { selectedArcIri: 'arc:1' }
    )
    const arc = objects.find((object): object is SceneArc => object.kind === 'arc')

    expect(arc).toBeDefined()
    expect(arc).toMatchObject({
      id: 'arc-arc:1',
      arcIri: 'arc:1',
      stroke: '#e74c3c',
      strokeWidth: 3,
      dash: [6, 4],
      hitStrokeWidth: 12,
      interactions: {
        clickable: true,
        draggable: false,
        doubleClickable: false,
        rightClickable: false,
      },
    })
    expect(arc!.points).toHaveLength(6)
    expect(arc!.points.slice(2, 4)).toEqual([50, 30])
    expect(arc!.arrowX).toBeCloseTo(79.42, 1)
    expect(arc!.arrowY).toBeCloseTo(12.35, 1)
  })

  it('skips arcs whose endpoint is absent from the view', () => {
    const objects = build(graphView({
      nodes: [leafA],
      arcs: [{
        modelArcIri: 'arc:missing',
        sourceId: leafA.id,
        targetId: 'missing',
        arcType: 'connection',
        modelArcType: 'promo:ArcType1',
        knots: [],
      }],
    }))

    expect(objects.some((object) => object.kind === 'arc')).toBe(false)
  })

  it('builds an open arc beneath its nodes and a draggable handle above them', () => {
    const view = graphView({
      openArcs: [{
        modelArcIri: 'arc:open',
        sourceId: leafA.id,
        targetId: leafB.id,
        arcType: 'open',
        modelArcType: 'promo:ArcType1',
        knots: [],
        openEndId: leafB.id,
        openEndTreeNodeId: 7,
      }],
    })
    const objects = build(view)
    const openArc = objects.find((object): object is SceneOpenArc => object.kind === 'openArc')
    const handle = objects.find((object): object is SceneHandle => object.kind === 'openArcHandle')

    expect(objects.map(({ kind }) => kind)).toEqual(['openArc', 'node', 'node', 'openArcHandle'])
    expect(openArc).toMatchObject({
      id: 'open-arc-arc:open',
      openEndId: leafB.id,
      openEndTreeNodeId: 7,
      interactions: {
        clickable: false,
        draggable: false,
        doubleClickable: false,
        rightClickable: false,
      },
    })
    expect(handle).toMatchObject({
      id: 'handle-arc:open',
      openArcIri: 'arc:open',
      x: 76,
      y: 0,
      fixedX: 24,
      fixedY: 0,
      interactions: {
        clickable: true,
        draggable: true,
        doubleClickable: false,
        rightClickable: false,
      },
    })
  })

  it('places the active open-arc handle at the current drag position', () => {
    const view = graphView({
      openArcs: [{
        modelArcIri: 'arc:open',
        sourceId: leafA.id,
        targetId: leafB.id,
        arcType: 'open',
        modelArcType: 'promo:ArcType1',
        knots: [],
        openEndId: leafA.id,
        openEndTreeNodeId: 7,
      }],
    })
    const objects = build(view, {
      draggingOpenArc: {
        openArcIri: 'arc:open',
        fixedX: 76,
        fixedY: 0,
        currentX: 30,
        currentY: 40,
      },
    })
    const handle = objects.find((object): object is SceneHandle => object.kind === 'openArcHandle')

    expect(handle).toMatchObject({
      x: 30,
      y: 40,
      openX: 24,
      openY: 0,
      fixedX: 76,
      fixedY: 0,
    })
  })

  it('sets highlight=valid on the hovered node when hoveredHighlight is valid', () => {
    const objects = build(graphView(), {
      hoveredNodeId: leafB.id,
      hoveredHighlight: 'valid',
    })
    const nodes = objects.filter((o): o is SceneNode => o.kind === 'node')
    const hovered = nodes.find((n) => n.id === leafB.id)
    const notHovered = nodes.find((n) => n.id === leafA.id)

    expect(hovered?.highlight).toBe('valid')
    expect(notHovered?.highlight).toBeUndefined()
  })

  it('sets highlight=invalid on the hovered node when hoveredHighlight is invalid', () => {
    const objects = build(graphView(), {
      hoveredNodeId: leafB.id,
      hoveredHighlight: 'invalid',
    })
    const hovered = objects.find(
      (o): o is SceneNode => o.kind === 'node' && o.id === leafB.id
    )
    expect(hovered?.highlight).toBe('invalid')
  })

  it('does not set highlight when hoveredNodeId does not match any node', () => {
    const objects = build(graphView(), {
      hoveredNodeId: 'nonexistent',
      hoveredHighlight: 'valid',
    })
    const nodes = objects.filter((o): o is SceneNode => o.kind === 'node')
    expect(nodes.every((n) => n.highlight === undefined)).toBe(true)
  })

  it('generates draggable knot SceneObjects for arcs with knots', () => {
    const objects = build(
      graphView({
        arcs: [{
          modelArcIri: 'arc:knots',
          sourceId: leafA.id,
          targetId: leafB.id,
          arcType: 'connection',
          modelArcType: 'promo:ArcType1',
          knots: [{ x: 30, y: 10 }, { x: 60, y: -10 }],
        }],
      }),
    )
    const knots = objects.filter((o): o is SceneKnot => o.kind === 'knot')

    expect(knots).toHaveLength(2)
    expect(knots[0]).toMatchObject({
      id: 'knot-arc:knots-0',
      x: 30,
      y: 10,
      arcIri: 'arc:knots',
      knotIndex: 0,
      interactions: {
        clickable: true,
        draggable: true,
        doubleClickable: true,
        rightClickable: true,
      },
    })
    expect(knots[1]).toMatchObject({
      id: 'knot-arc:knots-1',
      knotIndex: 1,
    })
  })

  it('does not generate knot objects when arc has no knots', () => {
    const objects = build(
      graphView({
        arcs: [{
          modelArcIri: 'arc:noknots',
          sourceId: leafA.id,
          targetId: leafB.id,
          arcType: 'connection',
          modelArcType: 'promo:ArcType1',
          knots: [],
        }],
      }),
    )
    expect(objects.some((o) => o.kind === 'knot')).toBe(false)
  })
})
