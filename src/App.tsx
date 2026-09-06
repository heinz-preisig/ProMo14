import { useState, useRef, useCallback, useEffect } from 'react'
import { Stage, Layer, Circle, Line, Text, Group } from 'react-konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import type { GraphNode, Arc, NodeType, NodeTypeDef, ArcType, ArcTypeDef, ConnectionRule } from './types'

const NODE_RADIUS = 24
const STROKE_WIDTH = 2
const TOOLBAR_HEIGHT = 40
const BOTTOM_BAR_HEIGHT = 24
const PALETTE_WIDTH = 140
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

const NODE_TYPES: NodeTypeDef[] = [
  { id: 'TypeA', label: 'Type A', fill: '#e8f4fd', stroke: '#2980b9', ontologyUri: 'promo:TypeA' },
  { id: 'TypeB', label: 'Type B', fill: '#d4edda', stroke: '#155724', ontologyUri: 'promo:TypeB' },
  { id: 'TypeC', label: 'Type C', fill: '#fff3cd', stroke: '#856404', ontologyUri: 'promo:TypeC' },
]

const ARC_TYPES: ArcTypeDef[] = [
  { id: 'ArcType1', label: 'Arc Type 1', stroke: '#333' },
  { id: 'ArcType2', label: 'Arc Type 2', stroke: '#888', dash: [6, 4] },
]

const CONNECTION_RULES: ConnectionRule[] = [
  { sourceType: 'TypeA', targetType: 'TypeA', arcType: 'ArcType1' },
  { sourceType: 'TypeA', targetType: 'TypeA', arcType: 'ArcType2' },
  { sourceType: 'TypeA', targetType: 'TypeB', arcType: 'ArcType1' },
  { sourceType: 'TypeB', targetType: 'TypeC', arcType: 'ArcType1' },
  { sourceType: 'TypeC', targetType: 'TypeA', arcType: 'ArcType2' },
]

export default function App() {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [arcs, setArcs] = useState<Arc[]>([])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedArcId, setSelectedArcId] = useState<string | null>(null)
  const [activeNodeType, setActiveNodeType] = useState<NodeType>('TypeA')
  const [nextId, setNextId] = useState(1)
  const [stageSize, setStageSize] = useState({
    width: window.innerWidth - PALETTE_WIDTH * 2,
    height: window.innerHeight - TOOLBAR_HEIGHT - BOTTOM_BAR_HEIGHT,
  })

  const wasDragged = useRef(false)

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

  const createNode = useCallback(
    (x: number, y: number) => {
      const id = `n${nextId}`
      setNextId((prev) => prev + 1)
      setNodes((prev) => [...prev, { id, x, y, label: id, nodeType: activeNodeType }])
      setSelectedNodeId(id)
      setSelectedArcId(null)
    },
    [nextId, activeNodeType]
  )

  const handleStageClick = useCallback(
    (e: KonvaEventObject<MouseEvent>) => {
      if (wasDragged.current) return
      if (e.target !== e.target.getStage()) return

      const pos = e.target.getStage()?.getPointerPosition()
      if (!pos) return

      createNode(pos.x, pos.y)
    },
    [createNode]
  )

  function getValidArcTypes(sourceType: NodeType, targetType: NodeType): ArcType[] {
    return CONNECTION_RULES
      .filter((r) => r.sourceType === sourceType && r.targetType === targetType)
      .map((r) => r.arcType)
  }

  const handleNodeClick = useCallback(
    (nodeId: string) => (e: KonvaEventObject<MouseEvent>) => {
      e.cancelBubble = true
      if (wasDragged.current) return

      if (selectedNodeId === nodeId) {
        setSelectedNodeId(null)
      } else if (selectedNodeId && selectedNodeId !== nodeId) {
        const sourceNode = nodes.find((n) => n.id === selectedNodeId)
        const targetNode = nodes.find((n) => n.id === nodeId)
        if (!sourceNode || !targetNode) {
          setSelectedNodeId(null)
          return
        }

        const validArcTypes = getValidArcTypes(sourceNode.nodeType, targetNode.nodeType)
        const exists = arcs.some(
          (a) => a.sourceId === selectedNodeId && a.targetId === nodeId
        )

        if (!exists && validArcTypes.length > 0) {
          const arcType = validArcTypes[0]
          const arcId = `a${nextId}`
          setNextId((prev) => prev + 1)
          setArcs((prev) => [
            ...prev,
            { id: arcId, sourceId: selectedNodeId, targetId: nodeId, arcType, knots: [] },
          ])
        }
        setSelectedNodeId(null)
      } else {
        setSelectedNodeId(nodeId)
        setSelectedArcId(null)
      }
    },
    [selectedNodeId, arcs, nextId, nodes]
  )

  const handleNodeDragMove = useCallback(
    (nodeId: string) => (e: KonvaEventObject<DragEvent>) => {
      const pos = e.target.position()
      setNodes((prev) =>
        prev.map((n) => (n.id === nodeId ? { ...n, x: pos.x, y: pos.y } : n))
      )
    },
    []
  )

  const handleArcClick = useCallback(
    (arcId: string) => (e: KonvaEventObject<MouseEvent>) => {
      e.cancelBubble = true
      if (wasDragged.current) return
      setSelectedArcId(arcId)
      setSelectedNodeId(null)
    },
    []
  )

  const handleDelete = useCallback(() => {
    if (selectedNodeId) {
      setArcs((prev) =>
        prev.filter((a) => a.sourceId !== selectedNodeId && a.targetId !== selectedNodeId)
      )
      setNodes((prev) => prev.filter((n) => n.id !== selectedNodeId))
      setSelectedNodeId(null)
    } else if (selectedArcId) {
      setArcs((prev) => prev.filter((a) => a.id !== selectedArcId))
      setSelectedArcId(null)
    }
  }, [selectedNodeId, selectedArcId])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        handleDelete()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleDelete])

  const getArcGeometry = (arc: Arc) => {
    const src = nodes.find((n) => n.id === arc.sourceId)
    const tgt = nodes.find((n) => n.id === arc.targetId)
    if (!src || !tgt) return null

    // Build polyline: source rim -> knots -> target rim
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

    // Arrow angle derived from last segment
    const prevX = arc.knots.length > 0 ? arc.knots[arc.knots.length - 1].x : src.x
    const prevY = arc.knots.length > 0 ? arc.knots[arc.knots.length - 1].y : src.y
    const angle = Math.atan2(pEnd.y - prevY, pEnd.x - prevX)

    return { points: pts, arrowAngle: angle, arrowX: pEnd.x, arrowY: pEnd.y }
  }

  const selectedNode = nodes.find((n) => n.id === selectedNodeId)
  const selectedArc = arcs.find((a) => a.id === selectedArcId)

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
          <button style={{ fontSize: 12 }}>Save</button>
          <button style={{ fontSize: 12 }}>Screenshot</button>
          <select style={{ fontSize: 12 }}>
            <option>topology</option>
            <option>token topology</option>
            <option>equation topology</option>
          </select>
          <select style={{ fontSize: 12 }}>
            <option>energy</option>
            <option>mass</option>
            <option>control</option>
          </select>
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
        </div>

        {/* Canvas */}
        <Stage
          width={stageSize.width}
          height={stageSize.height}
          onClick={handleStageClick}
          style={{ flex: 1, background: '#fafafa' }}
        >
          <Layer>
            {arcs.map((arc) => {
              const geom = getArcGeometry(arc)
              if (!geom) return null
              const isSelected = arc.id === selectedArcId
              const arcTypeDef = ARC_TYPES.find((t) => t.id === arc.arcType) ?? ARC_TYPES[0]
              const colour = isSelected ? '#e74c3c' : arcTypeDef.stroke
              const aPoints = arrowPoints(geom.arrowX, geom.arrowY, geom.arrowAngle)
              return (
                <Group key={arc.id} onClick={handleArcClick(arc.id)}>
                  <Line
                    points={geom.points}
                    stroke="transparent"
                    strokeWidth={12}
                    listening
                  />
                  <Line
                    points={geom.points}
                    stroke={colour}
                    strokeWidth={isSelected ? 3 : 2}
                    dash={arcTypeDef.dash}
                  />
                  <Line
                    points={aPoints}
                    closed
                    fill={colour}
                    stroke={colour}
                    strokeWidth={isSelected ? 3 : 2}
                  />
                </Group>
              )
            })}
          </Layer>
          <Layer>
            {nodes.map((node) => {
              const isSelected = node.id === selectedNodeId
              const typeDef = NODE_TYPES.find((t) => t.id === node.nodeType) ?? NODE_TYPES[0]
              const fill = isSelected ? '#3498db' : typeDef.fill
              const stroke = isSelected ? '#2980b9' : typeDef.stroke
              return (
                <Group
                  key={node.id}
                  x={node.x}
                  y={node.y}
                  draggable
                  onDragStart={() => {
                    wasDragged.current = false
                  }}
                  onDragMove={(e) => {
                    wasDragged.current = true
                    handleNodeDragMove(node.id)(e)
                  }}
                  onDragEnd={() => {
                    setTimeout(() => {
                      wasDragged.current = false
                    }, 50)
                  }}
                  onClick={handleNodeClick(node.id)}
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
          {selectedNode && (
            <div style={{ fontSize: 11 }}>
              <div>ID: {selectedNode.id}</div>
              <div>Type: {selectedNode.nodeType}</div>
              <div>x: {selectedNode.x.toFixed(1)}</div>
              <div>y: {selectedNode.y.toFixed(1)}</div>
            </div>
          )}
          {selectedArc && (
            <div style={{ fontSize: 11 }}>
              <div>ID: {selectedArc.id}</div>
              <div>Type: {selectedArc.arcType}</div>
              <div>From: {selectedArc.sourceId}</div>
              <div>To: {selectedArc.targetId}</div>
              <div>Knots: {selectedArc.knots.length}</div>
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
          {selectedNodeId
            ? `Node ${selectedNodeId} selected — click target to connect (rules enforced)`
            : selectedArcId
              ? `Arc ${selectedArcId} selected`
              : 'Click canvas to add node — click node to select — Delete to remove'}
        </span>
        <span style={{ marginLeft: 'auto', color: '#555' }}>
          {nodes.length} nodes, {arcs.length} arcs
        </span>
      </div>
    </div>
  )
}
