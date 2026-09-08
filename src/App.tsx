import { useState, useEffect, useMemo, useReducer } from 'react'
import { Stage, Layer, Circle, Line, Text, Group, Rect } from 'react-konva'
import type { NodeType, NodeTypeDef, ArcType, ArcTypeDef } from './types'
import { computeGraphView } from './tree/computeGraphView'
import { AppState, initialState, applyCommand, Command } from './state/ModelState'
import { useCanvasEvents } from './canvas/useCanvasEvents'

const NODE_RADIUS = 24
const STROKE_WIDTH = 2
const TOOLBAR_HEIGHT = 40
const BOTTOM_BAR_HEIGHT = 24
const PALETTE_WIDTH = 140
const ARROW_SIZE = 10
const COMPOSITE_WIDTH = 80
const COMPOSITE_HEIGHT = 60

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

const NODE_TYPES: NodeTypeDef[] = [
  { id: 'TypeA', label: 'Type A', fill: '#e8f4fd', stroke: '#2980b9', ontologyUri: 'promo:TypeA' },
  { id: 'TypeB', label: 'Type B', fill: '#d4edda', stroke: '#155724', ontologyUri: 'promo:TypeB' },
  { id: 'TypeC', label: 'Type C', fill: '#fff3cd', stroke: '#856404', ontologyUri: 'promo:TypeC' },
]

const ARC_TYPES: ArcTypeDef[] = [
  { id: 'ArcType1', label: 'Arc Type 1', stroke: '#333' },
  { id: 'ArcType2', label: 'Arc Type 2', stroke: '#888', dash: [6, 4] },
]

const getArcTypeDef = (id: string) => ARC_TYPES.find((t) => t.id === id)

function reducer(state: AppState, cmd: Command): AppState {
  // console.log('Command:', cmd)
  return applyCommand(state, cmd)
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState)

  const [draggingOpenArc, setDraggingOpenArc] = useState<{
    openArcIri: string
    fixedX: number
    fixedY: number
    currentX: number
    currentY: number
  } | null>(null)

  // --- Palette state (UI only, not part of model) ---
  const [activeNodeType, setActiveNodeType] = useState<NodeType>('TypeA')
  const [activeArcType, setActiveArcType] = useState<ArcType>('ArcType1')

  const [stageSize, setStageSize] = useState({
    width: window.innerWidth - PALETTE_WIDTH * 2,
    height: window.innerHeight - TOOLBAR_HEIGHT - BOTTOM_BAR_HEIGHT,
  })

  // --- View transform (pan / zoom) ---
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [scale, setScale] = useState(1)

  useEffect(() => {
    const handleResize = () => {
      setStageSize({
        width: window.innerWidth - PALETTE_WIDTH * 2,
        height: window.innerHeight - TOOLBAR_HEIGHT - BOTTOM_BAR_HEIGHT,
      })
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // --- Compute current GraphView on demand ---
  const graphView = useMemo(
    () => computeGraphView(state.currentViewNodeId, state.tree, state.modelNodes, state.modelArcs, state.layoutStore, state.openArcs, stageSize.width, stageSize.height),
    [state.currentViewNodeId, state.tree, state.modelNodes, state.modelArcs, state.layoutStore, state.openArcs, stageSize.width, stageSize.height]
  )

  // --- Three-panel zone boundaries ---
  const leftZoneX = -stageSize.width / 2 + 80
  const rightZoneX = stageSize.width / 2 - 80
  const zoneTop = -stageSize.height / 2
  const zoneBottom = stageSize.height / 2

  // --- Canvas event handlers (isolated from rendering) ---
  const {
    handleStageClick,
    handleStageRightClick,
    handleStageMouseDown,
    handleStageMouseMove,
    handleStageMouseUp,
    handleStageWheel,
    handleVisibleNodeClick,
    handleVisibleNodeRightClick,
    handleNodeDragStart,
    handleVisibleNodeDragMove,
    handleNodeDragEnd,
    handleArcClick,
    zoomInto,
    groupSelectedNodes,
  } = useCanvasEvents(state, graphView, stageSize, activeNodeType, activeArcType, dispatch, pan, setPan, scale, setScale)

  const getArcGeometry = (arc: { sourceId: string; targetId: string; knots: { x: number; y: number }[] }) => {
    const src = graphView.nodes.find((n) => n.id === arc.sourceId)
    const tgt = graphView.nodes.find((n) => n.id === arc.targetId)
    if (!src || !tgt) return null

    const pts: number[] = []
    const k0 = arc.knots.length > 0 ? arc.knots[0] : tgt
    const pStart = rimPoint(src.x, src.y, k0.x, k0.y, NODE_RADIUS)
    pts.push(pStart.x, pStart.y)

    for (const k of arc.knots) {
      pts.push(k.x, k.y)
    }

    const kLast = arc.knots.length > 0 ? arc.knots[arc.knots.length - 1] : src
    const pEnd = rimPoint(tgt.x, tgt.y, kLast.x, kLast.y, NODE_RADIUS)
    pts.push(pEnd.x, pEnd.y)

    const prevX = arc.knots.length > 0 ? arc.knots[arc.knots.length - 1].x : src.x
    const prevY = arc.knots.length > 0 ? arc.knots[arc.knots.length - 1].y : src.y
    const angle = Math.atan2(pEnd.y - prevY, pEnd.x - prevX)

    return { points: pts, arrowAngle: angle, arrowX: pEnd.x, arrowY: pEnd.y }
  }

  const selectedVisibleNode = graphView.nodes.find((n) => n.id === state.selectedVisibleNodeId)
  const selectedArc = graphView.arcs.find((a) => a.modelArcIri === state.selectedModelArcIri)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%' }}>
      {/* Top bar */}
      <div
        style={{
          height: TOOLBAR_HEIGHT,
          padding: '0 16px',
          background: '#e0e0e0',
          display: 'flex',
          gap: 16,
          alignItems: 'center',
          boxSizing: 'border-box',
        }}
      >
        <strong>ProMo14</strong>
        <span style={{ fontSize: 13, color: '#555' }}>Model: untitled</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, fontSize: 13 }}>
          <span style={{ color: '#555' }}>View: {state.tree.nodes.get(state.currentViewNodeId)?.label ?? 'Root'}</span>
          <button style={{ fontSize: 12 }}>Save</button>
          <button style={{ fontSize: 12 }}>Screenshot</button>
        </div>
      </div>

      {/* Middle area: palette + canvas + properties */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left palette */}
        <div
          style={{
            width: PALETTE_WIDTH,
            background: '#f0f0f0',
            borderRight: '1px solid #ccc',
            padding: 8,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            boxSizing: 'border-box',
          }}
        >
          <strong style={{ fontSize: 12 }}>Palette</strong>
          <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Select type, then click canvas</div>
          {NODE_TYPES.map((t) => {
            const isActive = activeNodeType === t.id
            return (
              <button
                key={t.id}
                onClick={() => setActiveNodeType(t.id)}
                style={{
                  fontSize: 12,
                  padding: '6px 8px',
                  textAlign: 'left',
                  cursor: 'pointer',
                  background: isActive ? '#fff' : '#e8e8e8',
                  border: isActive ? `2px solid ${t.stroke}` : '1px solid #bbb',
                  borderRadius: 4,
                }}
              >
                <span
                  style={{
                    display: 'inline-block',
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: t.fill,
                    border: `1.5px solid ${t.stroke}`,
                    marginRight: 6,
                    verticalAlign: 'middle',
                  }}
                />
                {t.label}
              </button>
            )
          })}

          <div style={{ marginTop: 8, borderTop: '1px solid #ccc', paddingTop: 8 }}>
            <strong style={{ fontSize: 12 }}>Arc type</strong>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Select type, then connect nodes</div>
            {ARC_TYPES.map((t) => {
              const isActive = activeArcType === t.id
              return (
                <button
                  key={t.id}
                  onClick={() => setActiveArcType(t.id)}
                  style={{
                    fontSize: 12,
                    padding: '6px 8px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    background: isActive ? '#fff' : '#e8e8e8',
                    border: isActive ? `2px solid #333` : '1px solid #bbb',
                    borderRadius: 4,
                    width: '100%',
                  }}
                >
                  <span
                    style={{
                      display: 'inline-block',
                      width: 24,
                      height: 0,
                      borderTop: `2px ${t.dash ? 'dashed' : 'solid'} ${t.stroke}`,
                      marginRight: 6,
                      verticalAlign: 'middle',
                    }}
                  />
                  {t.label}
                </button>
              )
            })}
          </div>

          <div style={{ marginTop: 8, borderTop: '1px solid #ccc', paddingTop: 8 }}>
            <strong style={{ fontSize: 12 }}>Actions</strong>
            <button
              onClick={groupSelectedNodes}
              disabled={!state.selectedVisibleNodeId}
              style={{
                fontSize: 12,
                padding: '6px 8px',
                width: '100%',
                cursor: state.selectedVisibleNodeId ? 'pointer' : 'not-allowed',
                background: state.selectedVisibleNodeId ? '#e8f4fd' : '#eee',
                border: '1px solid #bbb',
                borderRadius: 4,
                marginTop: 4,
              }}
            >
              Group selected
            </button>
            <button
              onClick={() => dispatch({ type: 'reset' })}
              style={{
                fontSize: 12,
                padding: '6px 8px',
                width: '100%',
                cursor: 'pointer',
                background: '#ffebee',
                border: '1px solid #ef9a9a',
                borderRadius: 4,
                marginTop: 8,
                color: '#c62828',
              }}
            >
              Reset all
            </button>
          </div>
        </div>

        {/* Canvas */}
        <Stage
          width={stageSize.width}
          height={stageSize.height}
          onClick={handleStageClick}
          onContextMenu={handleStageRightClick}
          onMouseDown={handleStageMouseDown}
          onMouseMove={handleStageMouseMove}
          onMouseUp={handleStageMouseUp}
          onWheel={handleStageWheel}
          style={{ flex: 1, background: '#fafafa' }}
        >
          {/* Center the coordinate system: (0,0) is at canvas center */}
          <Layer>
            <Group x={stageSize.width / 2 + pan.x} y={stageSize.height / 2 + pan.y} scaleX={scale} scaleY={scale}>
              {/* Three-panel separators */}
              <Line
                points={[leftZoneX, zoneTop, leftZoneX, zoneBottom]}
                stroke="#ccc"
                strokeWidth={1}
                dash={[4, 4]}
                listening={false}
              />
              <Line
                points={[rightZoneX, zoneTop, rightZoneX, zoneBottom]}
                stroke="#ccc"
                strokeWidth={1}
                dash={[4, 4]}
                listening={false}
              />

              {graphView.arcs.map((arc) => {
              const geom = getArcGeometry(arc)
              if (!geom) return null
              const isSelected = arc.modelArcIri === state.selectedModelArcIri
              const arcStyle = getArcTypeDef(arc.modelArcType)
              const colour = isSelected ? '#e74c3c' : (arcStyle?.stroke ?? '#333')
              const dash = arcStyle?.dash
              const strokeWidth = isSelected ? 3 : 2
              const aPoints = arrowPoints(geom.arrowX, geom.arrowY, geom.arrowAngle)
              return (
                <Group key={arc.modelArcIri} onClick={handleArcClick(arc.modelArcIri)}>
                  <Line
                    points={geom.points}
                    stroke="transparent"
                    strokeWidth={12}
                    listening
                  />
                  <Line
                    points={geom.points}
                    stroke={colour}
                    strokeWidth={strokeWidth}
                    dash={dash}
                  />
                  <Line
                    points={aPoints}
                    closed
                    fill={colour}
                    stroke={colour}
                    strokeWidth={strokeWidth}
                  />
                </Group>
              )
              })}

              {graphView.openArcs.map((arc) => {
              const geom = getArcGeometry(arc)
              if (!geom) return null
              const aPoints = arrowPoints(geom.arrowX, geom.arrowY, geom.arrowAngle)
              const midX = (geom.points[0] + geom.points[geom.points.length - 2]) / 2
              const midY = (geom.points[1] + geom.points[geom.points.length - 1]) / 2
              const openStyle = getArcTypeDef(arc.modelArcType)
              const openStroke = openStyle?.stroke ?? '#333'
              const openDash = openStyle?.dash
              return (
                <Group key={`open-${arc.modelArcIri}`}>
                  <Line
                    points={geom.points}
                    stroke="transparent"
                    strokeWidth={12}
                    listening
                  />
                  <Line
                    points={geom.points}
                    stroke="#c0392b"
                    strokeWidth={12}
                    opacity={0.35}
                  />
                  <Line
                    points={geom.points}
                    stroke={openStroke}
                    strokeWidth={2}
                    dash={openDash}
                  />
                  <Line
                    points={aPoints}
                    closed
                    fill={openStroke}
                    stroke={openStroke}
                    strokeWidth={2}
                  />
                  <Text
                    text="OPEN"
                    x={midX - 16}
                    y={midY - 7}
                    fontSize={11}
                    fill="#c0392b"
                  />
                </Group>
              )
              })}
            </Group>
          </Layer>
          <Layer>
            <Group x={stageSize.width / 2 + pan.x} y={stageSize.height / 2 + pan.y} scaleX={scale} scaleY={scale}>
              {graphView.nodes.map((node) => {
              const isSelected = node.id === state.selectedVisibleNodeId
              const isLeaf = node.type === 'leaf'
              const isComposite = node.type === 'composite'
              const isAncestor = node.type === 'ancestor'
              const isSibling = node.type === 'sibling'

              if (isComposite) {
                return (
                  <Group
                    key={node.id}
                    x={node.x}
                    y={node.y}
                    draggable
                    dragDistance={10}
                    onDragStart={handleNodeDragStart}
                    onDragMove={handleVisibleNodeDragMove(node.id)}
                    onDragEnd={handleNodeDragEnd}
                    onClick={handleVisibleNodeClick(node.id)}
                    onContextMenu={handleVisibleNodeRightClick(node.id)}
                  >
                    <Rect
                      width={COMPOSITE_WIDTH}
                      height={COMPOSITE_HEIGHT}
                      x={-COMPOSITE_WIDTH / 2}
                      y={-COMPOSITE_HEIGHT / 2}
                      fill={isSelected ? '#3498db' : '#e8f4fd'}
                      stroke={isSelected ? '#2980b9' : '#2980b9'}
                      strokeWidth={STROKE_WIDTH}
                      cornerRadius={4}
                    />
                    <Text
                      text={node.label}
                      fontSize={12}
                      fill={isSelected ? '#fff' : '#333'}
                      align="center"
                      width={COMPOSITE_WIDTH}
                      x={-COMPOSITE_WIDTH / 2}
                      y={-6}
                    />
                  </Group>
                )
              }

              // Look up node type colors for leaves
              const nodeTypeDef = isLeaf && node.entityType
                ? NODE_TYPES.find((t) => t.id === node.entityType)
                : undefined

              // Leaf, ancestor, sibling, connector — all rendered as circles
              const fill = isSelected
                ? '#3498db'
                : isAncestor
                  ? '#f0e68c'
                  : isSibling
                    ? '#dda0dd'
                    : nodeTypeDef
                      ? nodeTypeDef.fill
                      : '#e8f4fd'
              const stroke = isSelected ? '#2980b9' : (nodeTypeDef ? nodeTypeDef.stroke : '#666')

              return (
                <Group
                  key={node.id}
                  x={node.x}
                  y={node.y}
                  draggable={isLeaf || isComposite}
                  dragDistance={10}
                  onDragStart={handleNodeDragStart}
                  onDragMove={handleVisibleNodeDragMove(node.id)}
                  onDragEnd={handleNodeDragEnd}
                  onClick={handleVisibleNodeClick(node.id)}
                  onContextMenu={handleVisibleNodeRightClick(node.id)}
                  onDblClick={() => node.treeNodeId && zoomInto(node.treeNodeId)}
                >
                  <Circle
                    radius={NODE_RADIUS}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={STROKE_WIDTH}
                  />
                  <Text
                    text={node.label}
                    fontSize={12}
                    fill={isSelected ? '#fff' : '#333'}
                    align="center"
                    width={NODE_RADIUS * 2}
                    x={-NODE_RADIUS}
                    y={-6}
                  />
                </Group>
              )
            })}
            {graphView.openArcs.map((arc) => {
              const geom = getArcGeometry(arc)
              if (!geom) return null
              const isOpenEndSource = arc.sourceId === arc.openEndId
              const openX = isOpenEndSource ? geom.points[0] : geom.points[geom.points.length - 2]
              const openY = isOpenEndSource ? geom.points[1] : geom.points[geom.points.length - 1]
              const fixedX = isOpenEndSource ? geom.points[geom.points.length - 2] : geom.points[0]
              const fixedY = isOpenEndSource ? geom.points[geom.points.length - 1] : geom.points[1]
              const fixedId = isOpenEndSource ? arc.targetId : arc.sourceId
              const isDraggingThis = draggingOpenArc?.openArcIri === arc.modelArcIri
              const handleX = isDraggingThis ? draggingOpenArc.currentX : openX
              const handleY = isDraggingThis ? draggingOpenArc.currentY : openY
              return (
                <Circle
                  key={`open-handle-${arc.modelArcIri}`}
                  x={handleX}
                  y={handleY}
                  radius={10}
                  fill="#c0392b"
                  stroke="#fff"
                  strokeWidth={3}
                  shadowColor="#000"
                  shadowBlur={4}
                  shadowOpacity={0.35}
                  draggable
                  dragDistance={5}
                  onDragStart={() => {
                    setDraggingOpenArc({
                      openArcIri: arc.modelArcIri,
                      fixedX,
                      fixedY,
                      currentX: openX,
                      currentY: openY,
                    })
                  }}
                  onDragMove={(e) => {
                    const pos = e.target.position()
                    setDraggingOpenArc((prev) =>
                      prev && prev.openArcIri === arc.modelArcIri
                        ? { ...prev, currentX: pos.x, currentY: pos.y }
                        : prev
                    )
                  }}
                  onDragEnd={(e) => {
                    const pos = e.target.position()
                    const targetNode = graphView.nodes.find((n) => {
                      if (n.type !== 'leaf' || !n.modelNodeIri) return false
                      if (n.id === fixedId) return false
                      const dx = n.x - pos.x
                      const dy = n.y - pos.y
                      return Math.hypot(dx, dy) <= NODE_RADIUS + 10
                    })
                    if (targetNode?.modelNodeIri) {
                      dispatch({
                        type: 'reconnectOpenArc',
                        openArcIri: arc.modelArcIri,
                        newModelNodeIri: targetNode.modelNodeIri,
                      })
                    }
                    setDraggingOpenArc(null)
                  }}
                  onClick={(e) => {
                    e.cancelBubble = true
                  }}
                />
              )
            })}
            {draggingOpenArc && (
              <Line
                key="open-arc-drag-line"
                points={[
                  draggingOpenArc.fixedX,
                  draggingOpenArc.fixedY,
                  draggingOpenArc.currentX,
                  draggingOpenArc.currentY,
                ]}
                stroke="#c0392b"
                strokeWidth={2}
                dash={[4, 4]}
                listening={false}
              />
            )}
            </Group>
          </Layer>
        </Stage>

        {/* Right properties panel */}
        <div
          style={{
            width: 140,
            background: '#f0f0f0',
            borderLeft: '1px solid #ccc',
            padding: 8,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            boxSizing: 'border-box',
          }}
        >
          <strong style={{ fontSize: 12 }}>Properties</strong>
          {selectedVisibleNode && (
            <div style={{ fontSize: 11 }}>
              <div>ID: {selectedVisibleNode.id}</div>
              <div>Type: {selectedVisibleNode.type}</div>
              {selectedVisibleNode.modelNodeIri && (
                <div>IRI: {selectedVisibleNode.modelNodeIri}</div>
              )}
              {selectedVisibleNode.treeNodeId !== undefined && (
                <div>Tree: {selectedVisibleNode.treeNodeId}</div>
              )}
              <div>x: {selectedVisibleNode.x.toFixed(1)}</div>
              <div>y: {selectedVisibleNode.y.toFixed(1)}</div>
            </div>
          )}
          {selectedArc && (
            <div style={{ fontSize: 11 }}>
              <div>Arc: {selectedArc.modelArcIri}</div>
              <div>Type: {selectedArc.arcType}</div>
              <div>From: {selectedArc.sourceId}</div>
              <div>To: {selectedArc.targetId}</div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom status bar */}
      <div
        style={{
          height: 24,
          padding: '0 16px',
          background: '#e8e8e8',
          display: 'flex',
          alignItems: 'center',
          fontSize: 12,
          borderTop: '1px solid #ccc',
          boxSizing: 'border-box',
        }}
      >
        <span style={{ color: '#555' }}>
          {state.selectedVisibleNodeId
            ? `Node ${state.selectedVisibleNodeId} selected`
            : state.selectedModelArcIri
              ? `Arc ${state.selectedModelArcIri} selected`
              : 'Click canvas to add node — click composite to zoom — Delete to remove'}
        </span>
        <span style={{ marginLeft: 'auto', color: '#555' }}>
          {state.modelNodes.size} model nodes, {state.modelArcs.size} arcs (next node: {state.tree.nextId + 1})
        </span>
      </div>
    </div>
  )
}
