import { useState, useRef, useCallback, useEffect } from 'react'
import { Stage, Layer, Circle, Line, Text, Group } from 'react-konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import type { GraphNode, Arc } from './types'

const NODE_RADIUS = 24
const STROKE_WIDTH = 2
const TOOLBAR_HEIGHT = 40

export default function App() {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [arcs, setArcs] = useState<Arc[]>([])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedArcId, setSelectedArcId] = useState<string | null>(null)
  const [nextId, setNextId] = useState(1)
  const [stageSize, setStageSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight - TOOLBAR_HEIGHT,
  })

  const wasDragged = useRef(false)

  useEffect(() => {
    const handleResize = () => {
      setStageSize({
        width: window.innerWidth,
        height: window.innerHeight - TOOLBAR_HEIGHT,
      })
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const createNode = useCallback(
    (x: number, y: number) => {
      const id = `n${nextId}`
      setNextId((prev) => prev + 1)
      setNodes((prev) => [...prev, { id, x, y, label: id }])
      setSelectedNodeId(id)
      setSelectedArcId(null)
    },
    [nextId]
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

  const handleNodeClick = useCallback(
    (nodeId: string) => (e: KonvaEventObject<MouseEvent>) => {
      e.cancelBubble = true
      if (wasDragged.current) return

      if (selectedNodeId === nodeId) {
        setSelectedNodeId(null)
      } else if (selectedNodeId && selectedNodeId !== nodeId) {
        const exists = arcs.some(
          (a) =>
            (a.sourceId === selectedNodeId && a.targetId === nodeId) ||
            (a.sourceId === nodeId && a.targetId === selectedNodeId)
        )
        if (!exists) {
          const arcId = `a${nextId}`
          setNextId((prev) => prev + 1)
          setArcs((prev) => [...prev, { id: arcId, sourceId: selectedNodeId, targetId: nodeId }])
        }
        setSelectedNodeId(null)
      } else {
        setSelectedNodeId(nodeId)
        setSelectedArcId(null)
      }
    },
    [selectedNodeId, arcs, nextId]
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

  const getArcPoints = (arc: Arc): number[] => {
    const src = nodes.find((n) => n.id === arc.sourceId)
    const tgt = nodes.find((n) => n.id === arc.targetId)
    if (!src || !tgt) return []
    return [src.x, src.y, tgt.x, tgt.y]
  }

  const selectedLabel = selectedNodeId ?? selectedArcId ?? 'none'

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
      }}
    >
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
        <span style={{ fontSize: 13, color: '#555' }}>
          Click canvas to add node &middot; Click node to select &middot; Click another node to
          connect &middot; Drag to move &middot; Delete to remove
        </span>
        <span style={{ marginLeft: 'auto', fontSize: 13 }}>Selected: {selectedLabel}</span>
      </div>
      <Stage
        width={stageSize.width}
        height={stageSize.height}
        onClick={handleStageClick}
        style={{ flex: 1, background: '#fafafa' }}
      >
        <Layer>
          {arcs.map((arc) => {
            const points = getArcPoints(arc)
            const isSelected = arc.id === selectedArcId
            return (
              <Group key={arc.id} onClick={handleArcClick(arc.id)}>
                <Line
                  points={points}
                  stroke="transparent"
                  strokeWidth={12}
                  listening
                />
                <Line
                  points={points}
                  stroke={isSelected ? '#e74c3c' : '#333'}
                  strokeWidth={isSelected ? 3 : 2}
                />
              </Group>
            )
          })}
        </Layer>
        <Layer>
          {nodes.map((node) => {
            const isSelected = node.id === selectedNodeId
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
                  fill={isSelected ? '#3498db' : '#fff'}
                  stroke={isSelected ? '#2980b9' : '#333'}
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
    </div>
  )
}
