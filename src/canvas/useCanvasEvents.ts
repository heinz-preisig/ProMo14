import { useRef, useEffect } from 'react'
import type { KonvaEventObject } from 'konva/lib/Node'
import type { AppState, Command } from '../state/ModelState'
import type { GraphView, NodeType, ArcType } from '../types'

export interface CanvasEventHandlers {
  handleStageClick: (e: KonvaEventObject<MouseEvent>) => void
  handleStageRightClick: (e: KonvaEventObject<MouseEvent>) => void
  handleStageMouseDown: (e: KonvaEventObject<MouseEvent>) => void
  handleStageMouseMove: (e: KonvaEventObject<MouseEvent>) => void
  handleStageMouseUp: (e: KonvaEventObject<MouseEvent>) => void
  handleStageWheel: (e: KonvaEventObject<WheelEvent>) => void
  handleVisibleNodeClick: (nodeId: string) => (e: KonvaEventObject<MouseEvent>) => void
  handleVisibleNodeRightClick: (nodeId: string) => (e: KonvaEventObject<MouseEvent>) => void
  handleNodeDragStart: () => void
  handleVisibleNodeDragMove: (nodeId: string) => (e: KonvaEventObject<DragEvent>) => void
  handleNodeDragEnd: () => void
  handleArcClick: (arcIri: string) => (e: KonvaEventObject<MouseEvent>) => void
  zoomInto: (treeNodeId: number) => void
  groupSelectedNodes: () => void
  handleDelete: () => void
}

export function useCanvasEvents(
  state: AppState,
  graphView: GraphView,
  stageSize: { width: number; height: number },
  activeNodeType: NodeType,
  activeArcType: ArcType,
  dispatch: (cmd: Command) => void,
  pan: { x: number; y: number },
  setPan: (pan: { x: number; y: number }) => void,
  scale: number,
  setScale: (scale: number) => void
): CanvasEventHandlers {
  const wasDragged = useRef(false)
  const lastClickTime = useRef(0)
  const isPanning = useRef(false)
  const lastPanPos = useRef<{ x: number; y: number } | null>(null)

  const insertNodeAt = (x: number, y: number) => {
    const id = state.tree.nextId + 1
    const iri = `promo:Model/Node_${id}`
    dispatch({
      type: 'insertNode',
      id,
      iri,
      label: `Node ${id}`,
      entityType: activeNodeType,
      parentViewNodeId: state.currentViewNodeId,
      x,
      y,
    })
  }

  const handleStageClick = (e: KonvaEventObject<MouseEvent>) => {
    if (wasDragged.current) return
    if (e.target !== e.target.getStage()) return

    const now = Date.now()
    if (now - lastClickTime.current < 300) return
    lastClickTime.current = now

    const pos = e.target.getStage()?.getPointerPosition()
    if (!pos) return

    const sceneX = (pos.x - stageSize.width / 2 - pan.x) / scale
    const sceneY = (pos.y - stageSize.height / 2 - pan.y) / scale
    insertNodeAt(sceneX, sceneY)
  }

  const handleStageRightClick = (e: KonvaEventObject<MouseEvent>) => {
    e.evt.preventDefault()
    if (state.selectedVisibleNodeId) {
      dispatch({ type: 'selectNode', id: null })
    }
  }

  const handleStageMouseDown = (e: KonvaEventObject<MouseEvent>) => {
    if (e.evt.button === 1) {
      e.evt.preventDefault()
      isPanning.current = true
      lastPanPos.current = { x: e.evt.clientX, y: e.evt.clientY }
    }
  }

  const handleStageMouseMove = (e: KonvaEventObject<MouseEvent>) => {
    if (!isPanning.current || !lastPanPos.current) return
    const x = e.evt.clientX
    const y = e.evt.clientY
    const dx = x - lastPanPos.current.x
    const dy = y - lastPanPos.current.y
    setPan({ x: pan.x + dx, y: pan.y + dy })
    lastPanPos.current = { x, y }
  }

  const handleStageMouseUp = () => {
    isPanning.current = false
    lastPanPos.current = null
  }

  const handleStageWheel = (e: KonvaEventObject<WheelEvent>) => {
    e.evt.preventDefault()
    const delta = e.evt.deltaY
    const factor = Math.exp(-delta * 0.001)
    const newScale = Math.min(Math.max(scale * factor, 0.2), 5)
    setScale(newScale)
  }

  const handleVisibleNodeClick =
    (nodeId: string) =>
    (e: KonvaEventObject<MouseEvent>) => {
      e.cancelBubble = true
      if (wasDragged.current) return

      const node = graphView.nodes.find((n) => n.id === nodeId)
      if (node?.type === 'leaf') {
        dispatch({ type: 'selectNode', id: nodeId })
      } else if (node?.treeNodeId !== undefined) {
        dispatch({ type: 'setView', viewNodeId: node.treeNodeId })
      }
    }

  const handleVisibleNodeRightClick =
    (nodeId: string) =>
    (e: KonvaEventObject<MouseEvent>) => {
      e.evt.preventDefault()
      e.cancelBubble = true
      if (wasDragged.current) return

      if (state.selectedVisibleNodeId === nodeId) {
        dispatch({ type: 'selectNode', id: null })
        return
      }

      if (state.selectedVisibleNodeId) {
        const sourceNode = graphView.nodes.find((n) => n.id === state.selectedVisibleNodeId)
        const targetNode = graphView.nodes.find((n) => n.id === nodeId)
        if (
          sourceNode?.type === 'leaf' &&
          targetNode?.type === 'leaf' &&
          sourceNode.modelNodeIri &&
          targetNode.modelNodeIri
        ) {
          const arcIri = `promo:Arc/Arc_${state.arcCounter}`
          dispatch({
            type: 'insertArc',
            iri: arcIri,
            sourceIri: sourceNode.modelNodeIri,
            targetIri: targetNode.modelNodeIri,
            arcType: activeArcType,
          })
        }
        dispatch({ type: 'selectNode', id: null })
        return
      }

      dispatch({ type: 'selectNode', id: nodeId })
    }

  const handleNodeDragStart = () => {
    wasDragged.current = false
  }

  const handleVisibleNodeDragMove =
    (nodeId: string) =>
    (e: KonvaEventObject<DragEvent>) => {
      wasDragged.current = true
      const node = graphView.nodes.find((n) => n.id === nodeId)
      const pos = e.target.position()
      let { x, y } = pos

      if (node && (node.type === 'leaf' || node.type === 'composite')) {
        const halfW = stageSize.width / 2
        const halfH = stageSize.height / 2
        const minX = -halfW + 80
        const maxX = halfW - 80
        const minY = -halfH + 80
        const maxY = halfH - 40
        x = Math.max(minX, Math.min(maxX, x))
        y = Math.max(minY, Math.min(maxY, y))
      }

      e.target.position({ x, y })
      dispatch({
        type: 'moveNode',
        viewNodeId: state.currentViewNodeId,
        nodeId,
        x,
        y,
      })
    }

  const handleNodeDragEnd = () => {
    setTimeout(() => { wasDragged.current = false }, 50)
  }

  const handleArcClick =
    (arcIri: string) =>
    (e: KonvaEventObject<MouseEvent>) => {
      e.cancelBubble = true
      if (wasDragged.current) return
      dispatch({ type: 'selectArc', iri: arcIri })
    }

  const zoomInto = (treeNodeId: number) => {
    dispatch({ type: 'setView', viewNodeId: treeNodeId })
  }

  const groupSelectedNodes = () => {
    const selectedNodes = graphView.nodes.filter(
      (n) => n.id === state.selectedVisibleNodeId && n.type === 'leaf'
    )
    if (selectedNodes.length === 0) return
    const treeNodeIds = selectedNodes.map((n) => n.treeNodeId!).filter((id): id is number => id !== undefined)
    dispatch({
      type: 'groupNodes',
      parentViewNodeId: state.currentViewNodeId,
      treeNodeIds,
    })
  }

  const handleDelete = () => {
    if (state.selectedVisibleNodeId) {
      const node = graphView.nodes.find((n) => n.id === state.selectedVisibleNodeId)
      if (node?.type === 'leaf' && node.treeNodeId !== undefined) {
        dispatch({
          type: 'deleteNode',
          visibleNodeId: node.id,
          treeNodeId: node.treeNodeId,
          modelNodeIri: node.modelNodeIri,
        })
      }
    } else if (state.selectedModelArcIri) {
      dispatch({ type: 'deleteArc', iri: state.selectedModelArcIri })
    }
  }

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        handleDelete()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleDelete])

  return {
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
    handleDelete,
  }
}
