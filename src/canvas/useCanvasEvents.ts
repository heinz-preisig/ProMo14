import { useRef, useEffect } from 'react'
import type { KonvaEventObject } from 'konva/lib/Node'
import type { AppState, Command } from '../state/ModelState'
import type { GraphView, NodeType, ArcType } from '../types'
import type { SceneObject, SceneInteractionHandlers } from '../scene/types'
import { placeholderCatalogue, placeholderRuleResolver } from '../semantic/placeholderCatalogue'
import { resolveConnection, pickArcType } from '../semantic/connectionService'

export interface CanvasEventHandlers {
  handleStageClick: (e: KonvaEventObject<MouseEvent>) => void
  handleStageRightClick: (e: KonvaEventObject<MouseEvent>) => void
  handleStageMouseDown: (e: KonvaEventObject<MouseEvent>) => void
  handleStageMouseMove: (e: KonvaEventObject<MouseEvent>) => void
  handleStageMouseUp: (e: KonvaEventObject<MouseEvent>) => void
  handleStageWheel: (e: KonvaEventObject<WheelEvent>) => void
  zoomInto: (treeNodeId: number) => void
  groupSelectedNodes: () => void
  handleDelete: () => void
  sceneHandlers: SceneInteractionHandlers
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
  setScale: (scale: number) => void,
  setDraggingOpenArc: (v: { openArcIri: string; fixedX: number; fixedY: number; currentX: number; currentY: number } | null) => void,
  setHoveredNodeId: (id: string | null) => void,
  setHoveredObject: (obj: SceneObject | null) => void,
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

  const onSceneClick = (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => {
    e.cancelBubble = true
    if (wasDragged.current) return

    if (obj.kind === 'node') {
      if (obj.nodeType === 'leaf') {
        dispatch({ type: 'selectNode', id: obj.selectionId! })
      } else if (obj.treeNodeId !== undefined) {
        dispatch({ type: 'setView', viewNodeId: obj.treeNodeId })
      }
    } else if (obj.kind === 'arc') {
      dispatch({ type: 'selectArc', iri: obj.arcIri! })
    } else if (obj.kind === 'knot') {
      dispatch({ type: 'selectArc', iri: obj.arcIri })
    }
  }

  const onSceneRightClick = (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => {
    e.evt.preventDefault()
    e.cancelBubble = true
    if (wasDragged.current) return

    if (obj.kind === 'knot') {
      dispatch({ type: 'removeKnot', arcIri: obj.arcIri, knotIndex: obj.knotIndex })
      return
    }

    if (obj.kind !== 'node') return

    const nodeId = obj.selectionId!
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
        targetNode.modelNodeIri &&
        sourceNode.entityType &&
        targetNode.entityType
      ) {
        const result = resolveConnection(
          sourceNode.entityType,
          targetNode.entityType,
          placeholderCatalogue,
          placeholderRuleResolver,
        )
        const arcType = pickArcType(result, activeArcType)
        if (arcType) {
          const arcIri = `promo:Arc/Arc_${state.arcCounter}`
          dispatch({
            type: 'insertArc',
            iri: arcIri,
            sourceIri: sourceNode.modelNodeIri,
            targetIri: targetNode.modelNodeIri,
            arcType,
          })
        }
      }
      dispatch({ type: 'selectNode', id: null })
      return
    }

    dispatch({ type: 'selectNode', id: nodeId })
  }

  const onSceneDoubleClick = (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => {
    e.cancelBubble = true
    if (wasDragged.current) return
    if (obj.kind === 'knot') {
      dispatch({ type: 'addKnot', arcIri: obj.arcIri, x: obj.x, y: obj.y })
      return
    }
    if (obj.kind === 'node' && obj.treeNodeId !== undefined) {
      dispatch({ type: 'setView', viewNodeId: obj.treeNodeId })
    }
  }

  const onSceneMouseEnter = (obj: SceneObject, _e: KonvaEventObject<MouseEvent>) => {
    setHoveredObject(obj)
    if (obj.kind === 'node' && obj.selectionId) {
      setHoveredNodeId(obj.selectionId)
    }
  }

  const onSceneMouseLeave = (_obj: SceneObject, _e: KonvaEventObject<MouseEvent>) => {
    setHoveredNodeId(null)
    setHoveredObject(null)
  }

  const onSceneDragStart = (_obj: SceneObject, _e: KonvaEventObject<DragEvent>) => {
    wasDragged.current = false
  }

  const onSceneDragMove = (obj: SceneObject, e: KonvaEventObject<DragEvent>) => {
    wasDragged.current = true

    if (obj.kind === 'node') {
      const pos = e.target.position()
      let { x, y } = pos
      if (obj.nodeType === 'leaf' || obj.nodeType === 'composite') {
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
        nodeId: obj.id,
        x,
        y,
      })
    } else if (obj.kind === 'knot') {
      const pos = e.target.position()
      dispatch({
        type: 'moveKnot',
        arcIri: obj.arcIri,
        knotIndex: obj.knotIndex,
        x: pos.x,
        y: pos.y,
      })
    } else if (obj.kind === 'openArcHandle') {
      const pos = e.target.position()
      setDraggingOpenArc({
        openArcIri: obj.openArcIri,
        fixedX: obj.fixedX,
        fixedY: obj.fixedY,
        currentX: pos.x,
        currentY: pos.y,
      })
    }
  }

  const onSceneDragEnd = (obj: SceneObject, e: KonvaEventObject<DragEvent>) => {
    setTimeout(() => { wasDragged.current = false }, 50)

    if (obj.kind === 'openArcHandle') {
      const pos = e.target.position()
      const fixedId =
        graphView.openArcs.find((a) => a.modelArcIri === obj.openArcIri)?.sourceId ===
        graphView.openArcs.find((a) => a.modelArcIri === obj.openArcIri)?.openEndId
          ? graphView.openArcs.find((a) => a.modelArcIri === obj.openArcIri)?.targetId
          : graphView.openArcs.find((a) => a.modelArcIri === obj.openArcIri)?.sourceId

      const targetNode = graphView.nodes.find((n) => {
        if (n.type !== 'leaf' || !n.modelNodeIri) return false
        if (n.id === fixedId) return false
        const dx = n.x - pos.x
        const dy = n.y - pos.y
        return Math.hypot(dx, dy) <= 34
      })
      if (targetNode?.modelNodeIri && targetNode.entityType) {
        const openArc = graphView.openArcs.find((a) => a.modelArcIri === obj.openArcIri)
        if (openArc) {
          for (const [, list] of state.openArcs) {
            const oa = list.find((a) => a.iri === obj.openArcIri)
            if (!oa) continue
            const externalNode = state.modelNodes.get(oa.externalIri)
            const externalEntityType = externalNode?.entityType
            if (!externalEntityType) break

            const sourceEntityType = oa.isSource ? targetNode.entityType : externalEntityType
            const targetEntityType = oa.isSource ? externalEntityType : targetNode.entityType

            const result = resolveConnection(
              sourceEntityType,
              targetEntityType,
              placeholderCatalogue,
              placeholderRuleResolver,
            )
            const arcType = pickArcType(result, oa.arcType)
            if (arcType) {
              dispatch({
                type: 'reconnectOpenArc',
                openArcIri: obj.openArcIri,
                newModelNodeIri: targetNode.modelNodeIri,
              })
            }
            break
          }
        }
      }
      setDraggingOpenArc(null)
    }
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

  const sceneHandlers: SceneInteractionHandlers = {
    onClick: onSceneClick,
    onRightClick: onSceneRightClick,
    onDoubleClick: onSceneDoubleClick,
    onDragStart: onSceneDragStart,
    onDragMove: onSceneDragMove,
    onDragEnd: onSceneDragEnd,
    onMouseEnter: onSceneMouseEnter,
    onMouseLeave: onSceneMouseLeave,
  }

  return {
    handleStageClick,
    handleStageRightClick,
    handleStageMouseDown,
    handleStageMouseMove,
    handleStageMouseUp,
    handleStageWheel,
    zoomInto,
    groupSelectedNodes,
    handleDelete,
    sceneHandlers,
  }
}
