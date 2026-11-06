import { useRef, useEffect, useState } from 'react'
import type { KonvaEventObject } from 'konva/lib/Node'
import type { Stage as KonvaStage } from 'konva/lib/Stage'
import type { AppState, Command } from '../state/ModelState'
import type { GraphView, NodeType, ArcType } from '../types'
import type { SceneObject, SceneInteractionHandlers } from '../scene/types'
import { resolveConnectionAsync, pickArcType, modelNodeIri, modelArcIri } from '@promo/semantic'
import type { ConnectionRuleResolver, SemanticCatalogue } from '@promo/semantic'
import { arcCarrier, defaultOrientation } from '../model/ModelGraph'
import { NODE_RADIUS, entityHalfExtent } from '../scene/buildScene'
import { GRAPH_IRI, loadModelDoc } from '../api'
import { refViewState } from '../modelPersistence'

/** Root of the transport-system subtree — seeded entity type
 *  (deterministic IRI, minted under the ontology namespace). */
const TRANSPORT_SYSTEM_IRI = 'https://w3id.org/promo/ontology#etype_transport_system'

/** §15: is this entity type a transport system (or a subtype)?
 *  Walks the promo:parent chain exposed via the catalogue. */
function isTransportEntity(entityType: string | undefined, catalogue: SemanticCatalogue): boolean {
  let cur = entityType
  const seen = new Set<string>()
  while (cur && !seen.has(cur)) {
    if (cur === TRANSPORT_SYSTEM_IRI) return true
    seen.add(cur)
    cur = catalogue.getBaseEntity(cur)?.parentIri
  }
  return false
}

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
  /** Active rubber-band rect in scene coordinates (Shift+drag), or
   *  null — rendered by the canvas layer. */
  marquee: { x: number; y: number; w: number; h: number } | null
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
  pendingConnection: { sourceModelIri: string; sourceEntityType: string } | null,
  setPendingConnection: (v: { sourceModelIri: string; sourceEntityType: string } | null) => void,
  ruleResolver: ConnectionRuleResolver,
  catalogue: SemanticCatalogue,
): CanvasEventHandlers {
  const wasDragged = useRef(false)
  const lastClickTime = useRef(0)
  const isPanning = useRef(false)
  const lastPanPos = useRef<{ x: number; y: number } | null>(null)

  // Multi-select: marquee (Shift+drag on empty stage) and multi-drag.
  const [marquee, setMarquee] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const isMarquee = useRef(false)
  const marqueeOrigin = useRef<{ x: number; y: number } | null>(null)
  /** Members of the selection set at dragStart — multi-drag applies
   *  the dragged node's delta to every member. */
  const dragSet = useRef<{
    originId: string
    members: { id: string; start: { x: number; y: number }; he: { x: number; y: number } }[]
  } | null>(null)

  // §22 reference view — inside a referenced artefact's scope the
  // canvas is read-only: the content belongs to another artefact.
  // Only navigation (descending composites / nested references)
  // stays live; every mutating gesture is gated on `inRef`.
  const inRef = state.viewRefIri !== null
  const scopeRefs = inRef
    ? state.refStates.get(state.viewRefIri!)?.compositeRefs
    : state.compositeRefs

  /** Zoom into a composite — for a referenced composite, into the
   *  referenced artefact's own tree (rendered read-only).  The ref
   *  doc is fetched on demand when the load-time prefetch missed it. */
  const enterComposite = (treeNodeId: number) => {
    const ref = scopeRefs?.get(treeNodeId)?.refersTo
    if (!ref) {
      dispatch({ type: 'setView', viewNodeId: treeNodeId })
      return
    }
    const target = state.refStates.get(ref)
    if (target) {
      dispatch({ type: 'setView', viewNodeId: target.tree.rootId, refIri: ref })
      return
    }
    loadModelDoc(ref).then((doc) => {
      const refs = new Map(state.refStates)
      refs.set(ref, refViewState(doc))
      dispatch({ type: 'setRefStates', states: refs })
      dispatch({ type: 'setView', viewNodeId: doc.rootTreeId, refIri: ref })
    }).catch(() => {
      // Unreachable reference — fall back to the local shell zoom.
      dispatch({ type: 'setView', viewNodeId: treeNodeId })
    })
  }

  const pointerToScene = (stage: KonvaStage | null) => {
    const pos = stage?.getPointerPosition()
    if (!pos) return null
    return {
      x: (pos.x - stageSize.width / 2 - pan.x) / scale,
      y: (pos.y - stageSize.height / 2 - pan.y) / scale,
    }
  }

  /** Margins are render zones (ancestors | siblings) — user nodes live
   *  in the centre panel only.  Applies to placement clicks AND drags.
   *  halfW/halfH = the node's own half-extent so the whole body stays
   *  inside, not just its centre point. */
  const clampToPanel = (x: number, y: number, halfW = NODE_RADIUS, halfH = NODE_RADIUS) => {
    const halfStageW = stageSize.width / 2
    const halfStageH = stageSize.height / 2
    return {
      x: Math.max(-halfStageW + 80 + halfW, Math.min(halfStageW - 80 - halfW, x)),
      y: Math.max(-halfStageH + 80 + halfH, Math.min(halfStageH - 40 - halfH, y)),
    }
  }

  const insertNodeAt = (x: number, y: number) => {
    const id = state.tree.nextId + 1
    // GRAPH_IRI is guaranteed — main.tsx only renders App with ?graph=.
    const iri = modelNodeIri(GRAPH_IRI!, id)
    const e = entityHalfExtent(activeNodeType, catalogue)
    const p = clampToPanel(x, y, e.x, e.y)
    dispatch({
      type: 'insertNode',
      id,
      iri,
      label: `Node ${id}`,
      entityType: activeNodeType,
      parentViewNodeId: state.currentViewNodeId,
      x: p.x,
      y: p.y,
    })
  }

  const handleStageClick = (e: KonvaEventObject<MouseEvent>) => {
    if (wasDragged.current) return
    if (e.evt.button !== 0) return   // Konva fires click for right-button too
    if (inRef) return
    if (e.target !== e.target.getStage()) return
    // Modifier clicks belong to multi-select gestures — never insert.
    if (e.evt.shiftKey || e.evt.ctrlKey || e.evt.metaKey) return

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
    if (inRef) return
    if (state.selectedVisibleNodeId) {
      dispatch({ type: 'selectNode', id: null })
    }
    if (pendingConnection) {
      setPendingConnection(null)
    }
  }

  const handleStageMouseDown = (e: KonvaEventObject<MouseEvent>) => {
    if (e.evt.button === 1) {
      e.evt.preventDefault()
      isPanning.current = true
      lastPanPos.current = { x: e.evt.clientX, y: e.evt.clientY }
      return
    }
    // Shift+drag on empty canvas starts the rubber band.
    if (
      e.evt.button === 0 && e.evt.shiftKey && !inRef &&
      e.target === e.target.getStage()
    ) {
      const p = pointerToScene(e.target.getStage())
      if (!p) return
      isMarquee.current = true
      marqueeOrigin.current = p
      setMarquee({ x: p.x, y: p.y, w: 0, h: 0 })
    }
  }

  const handleStageMouseMove = (e: KonvaEventObject<MouseEvent>) => {
    if (isMarquee.current && marqueeOrigin.current) {
      const p = pointerToScene(e.target.getStage())
      if (!p) return
      const o = marqueeOrigin.current
      setMarquee({
        x: Math.min(o.x, p.x),
        y: Math.min(o.y, p.y),
        w: Math.abs(p.x - o.x),
        h: Math.abs(p.y - o.y),
      })
      return
    }
    if (!isPanning.current || !lastPanPos.current) return
    const x = e.evt.clientX
    const y = e.evt.clientY
    const dx = x - lastPanPos.current.x
    const dy = y - lastPanPos.current.y
    setPan({ x: pan.x + dx, y: pan.y + dy })
    lastPanPos.current = { x, y }
  }

  const handleStageMouseUp = (e: KonvaEventObject<MouseEvent>) => {
    if (isMarquee.current) {
      const m = marquee
      isMarquee.current = false
      marqueeOrigin.current = null
      setMarquee(null)
      if (m && (m.w > 2 || m.h > 2)) {
        // Leaf centres inside the rect (same rule as click-select:
        // only leaves are selectable).
        const boxed = graphView.nodes
          .filter((n) =>
            n.type === 'leaf' &&
            n.x >= m.x && n.x <= m.x + m.w &&
            n.y >= m.y && n.y <= m.y + m.h)
          .map((n) => n.id)
        const additive = e.evt.ctrlKey || e.evt.metaKey
        const ids = additive
          ? [...state.selectedVisibleNodeIds, ...boxed]
          : boxed
        dispatch({ type: 'selectNodes', ids })
        // Swallow the click that follows mouseup — it would insert a node.
        wasDragged.current = true
        setTimeout(() => { wasDragged.current = false }, 50)
      }
      return
    }
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
    if (e.evt.button !== 0) return   // right-button is contextmenu, not select/zoom

    if (obj.kind === 'node') {
      if (obj.nodeType === 'leaf') {
        if (inRef) return
        // Ctrl/Cmd/Shift+click toggles membership — a selection
        // gesture only, it must not arm the connection source.
        if (e.evt.ctrlKey || e.evt.metaKey || e.evt.shiftKey) {
          dispatch({ type: 'toggleSelectNode', id: obj.selectionId! })
          return
        }
        dispatch({ type: 'selectNode', id: obj.selectionId! })
        if (obj.modelNodeIri && obj.entityType) {
          setPendingConnection({ sourceModelIri: obj.modelNodeIri, sourceEntityType: obj.entityType })
        }
      } else if (obj.treeNodeId !== undefined) {
        // Ctrl/Shift+click selects the composite (Properties/actions);
        // a plain click navigates into it.
        if (e.evt.ctrlKey || e.evt.metaKey || e.evt.shiftKey) {
          if (!inRef) dispatch({ type: 'selectNode', id: obj.selectionId! })
          return
        }
        enterComposite(obj.treeNodeId)
      }
    } else if (!inRef && obj.kind === 'arc') {
      dispatch({ type: 'selectArc', iri: obj.arcIri! })
    } else if (!inRef && obj.kind === 'knot') {
      dispatch({ type: 'selectArc', iri: obj.arcIri })
    }
  }

  const onSceneRightClick = async (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => {
    e.evt.preventDefault()
    e.cancelBubble = true
    if (wasDragged.current) return
    if (inRef) return

    if (obj.kind === 'knot') {
      dispatch({ type: 'removeKnot', arcIri: obj.arcIri, knotIndex: obj.knotIndex })
      return
    }

    // §15: right-click on a token-flow arc reverses its reference
    // direction (layout untouched).
    if (obj.kind === 'arc' && obj.arcIri) {
      const modelArc = state.modelArcs.get(obj.arcIri)
      if (modelArc && arcCarrier(modelArc.arcType) === 'token-flow') {
        dispatch({ type: 'reverseArcOrientation', iri: obj.arcIri })
      }
      return
    }

    if (obj.kind !== 'node') return

    const nodeId = obj.selectionId!

    // If we have a pending connection source, try to connect to this node
    if (pendingConnection && obj.nodeType === 'leaf' && obj.modelNodeIri && obj.entityType) {
      // Don't connect to self
      if (obj.modelNodeIri === pendingConnection.sourceModelIri) {
        setPendingConnection(null)
        dispatch({ type: 'selectNode', id: null })
        return
      }
      const result = await resolveConnectionAsync(
        pendingConnection.sourceEntityType,
        obj.entityType,
        catalogue,
        ruleResolver,
      )
      const arcType = pickArcType(result, activeArcType)
      if (arcType) {
        const arcIri = modelArcIri(GRAPH_IRI!, state.arcCounter)
        const orientation = defaultOrientation(
          arcType,
          pendingConnection.sourceModelIri,
          obj.modelNodeIri,
          isTransportEntity(pendingConnection.sourceEntityType, catalogue),
          isTransportEntity(obj.entityType, catalogue),
          transportArcs(pendingConnection.sourceModelIri, obj.modelNodeIri),
        )
        dispatch({
          type: 'insertArc',
          iri: arcIri,
          sourceIri: pendingConnection.sourceModelIri,
          targetIri: obj.modelNodeIri,
          arcType,
          referenceFrom: orientation?.referenceFrom,
          referenceTo: orientation?.referenceTo,
        })
      }
      setPendingConnection(null)
      // Chained connect: the target becomes the armed source — a run
      // of right-clicks connects node → node → node.
      dispatch({ type: 'selectNode', id: nodeId })
      setPendingConnection({ sourceModelIri: obj.modelNodeIri, sourceEntityType: obj.entityType })
      return
    }

    // Same-view connection (source visible in this view)
    if (state.selectedVisibleNodeId && state.selectedVisibleNodeId !== nodeId) {
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
        const result = await resolveConnectionAsync(
          sourceNode.entityType,
          targetNode.entityType,
          catalogue,
          ruleResolver,
        )
        const arcType = pickArcType(result, activeArcType)
        if (arcType) {
          const arcIri = modelArcIri(GRAPH_IRI!, state.arcCounter)
          const orientation = defaultOrientation(
            arcType,
            sourceNode.modelNodeIri,
            targetNode.modelNodeIri,
            isTransportEntity(sourceNode.entityType, catalogue),
            isTransportEntity(targetNode.entityType, catalogue),
            transportArcs(sourceNode.modelNodeIri, targetNode.modelNodeIri),
          )
          dispatch({
            type: 'insertArc',
            iri: arcIri,
            sourceIri: sourceNode.modelNodeIri,
            targetIri: targetNode.modelNodeIri,
            arcType,
            referenceFrom: orientation?.referenceFrom,
            referenceTo: orientation?.referenceTo,
          })
        }
      }
      if (targetNode?.type === 'leaf') {
        dispatch({ type: 'selectNode', id: null })
        setPendingConnection(null)
        return
      }
      // Non-leaf target (composite): fall through — it gets selected
      // below rather than dissolving the pending gesture on nothing.
    }

    // Select this node as connection source
    if (obj.nodeType === 'leaf' && obj.modelNodeIri && obj.entityType) {
      dispatch({ type: 'selectNode', id: nodeId })
      setPendingConnection({ sourceModelIri: obj.modelNodeIri, sourceEntityType: obj.entityType })
    } else {
      dispatch({ type: 'selectNode', id: nodeId })
    }
  }

  const onSceneDoubleClick = (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => {
    e.cancelBubble = true
    if (wasDragged.current) return
    if (e.evt.button !== 0) return
    if (inRef) return
    if (obj.kind === 'knot') {
      dispatch({ type: 'addKnot', arcIri: obj.arcIri, x: obj.x, y: obj.y })
      return
    }
    if (obj.kind === 'arc') {
      const pos = e.target.getStage()?.getPointerPosition()
      if (!pos) return
      const sceneX = (pos.x - stageSize.width / 2 - pan.x) / scale
      const sceneY = (pos.y - stageSize.height / 2 - pan.y) / scale
      dispatch({ type: 'addKnot', arcIri: obj.arcIri!, x: sceneX, y: sceneY })
      return
    }
    if (obj.kind === 'node' && obj.treeNodeId !== undefined && obj.nodeType !== 'leaf') {
      // A referenced composite's first click already navigated — a
      // second setView here would desync the reference scope.
      if (scopeRefs?.get(obj.treeNodeId)?.refersTo) return
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

  const onSceneDragStart = (obj: SceneObject, e: KonvaEventObject<DragEvent>) => {
    wasDragged.current = false
    dragSet.current = null
    if (inRef) return

    if (obj.kind !== 'node' || !obj.selectionId) return

    // Dragging an unselected node selects it (standard behaviour).
    if (!state.selectedVisibleNodeIds.includes(obj.selectionId)) {
      dispatch({ type: 'selectNode', id: obj.selectionId })
      return
    }

    if (state.selectedVisibleNodeIds.length < 2) return

    // Multi-drag: record every member's start so dragMove can apply
    // the shared delta.  Extent follows each member's entity type
    // (same source as single-node clamping).
    const pos = e.target.position()
    const members = state.selectedVisibleNodeIds
      .map((id) => {
        const n = graphView.nodes.find((g) => g.id === id)
        if (!n || n.type !== 'leaf') return null
        const he = entityHalfExtent(n.entityType, catalogue)
        return {
          id,
          start: id === obj.id ? { x: pos.x, y: pos.y } : { x: n.x, y: n.y },
          he,
        }
      })
      .filter((m): m is NonNullable<typeof m> => m !== null)
    if (members.length > 1) dragSet.current = { originId: obj.id, members }
  }

  const onSceneDragMove = (obj: SceneObject, e: KonvaEventObject<DragEvent>) => {
    wasDragged.current = true
    if (inRef) return

    if (obj.kind === 'node') {
      const pos = e.target.position()
      let { x, y } = pos
      if (obj.nodeType === 'leaf' || obj.nodeType === 'composite') {
        // Extent comes from the object — set from its graphical
        // definition at scene-build — never a per-shape constant.
        const he = obj.halfExtent ?? { x: NODE_RADIUS, y: NODE_RADIUS }
        const p = clampToPanel(x, y, he.x, he.y)
        x = p.x
        y = p.y
      }
      e.target.position({ x, y })

      // Multi-drag: the dragged member's (clamped) delta applies to
      // the whole selection set in one dispatch.
      const ds = dragSet.current
      if (ds && ds.originId === obj.id) {
        const origin = ds.members.find((m) => m.id === ds.originId)!
        const dx = x - origin.start.x
        const dy = y - origin.start.y
        const moves = ds.members.map((m) => {
          const p = clampToPanel(m.start.x + dx, m.start.y + dy, m.he.x, m.he.y)
          return { nodeId: m.id, x: p.x, y: p.y }
        })
        dispatch({ type: 'moveNodes', viewNodeId: state.currentViewNodeId, moves })
        return
      }

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

  const onSceneDragEnd = async (obj: SceneObject, e: KonvaEventObject<DragEvent>) => {
    dragSet.current = null
    setTimeout(() => { wasDragged.current = false }, 50)
    if (inRef) return

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
            // §22 terminal: externalIri may live in the referenced
            // artefact — the declared interface entity type stands in.
            const externalNode = state.modelNodes.get(oa.externalIri)
            const externalEntityType = externalNode?.entityType
              ?? oa.externalEntityType
            if (!externalEntityType) break

            const sourceEntityType = oa.isSource ? targetNode.entityType : externalEntityType
            const targetEntityType = oa.isSource ? externalEntityType : targetNode.entityType

            const result = await resolveConnectionAsync(
              sourceEntityType,
              targetEntityType,
              catalogue,
              ruleResolver,
            )
            const arcType = pickArcType(result, oa.arcType)
            if (arcType) {
              dispatch({
                type: 'reconnectOpenArc',
                openArcIri: obj.openArcIri,
                newModelNodeIri: targetNode.modelNodeIri,
                arcType,
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
    if (inRef) return
    const selectedNodes = graphView.nodes.filter(
      (n) => state.selectedVisibleNodeIds.includes(n.id) && n.type === 'leaf'
    )
    if (selectedNodes.length === 0) return
    const treeNodeIds = selectedNodes.map((n) => n.treeNodeId!).filter((id): id is number => id !== undefined)
    const label = window.prompt('Composite name:', 'Group')
    if (label === null) return
    dispatch({
      type: 'groupNodes',
      parentViewNodeId: state.currentViewNodeId,
      treeNodeIds,
      label: label || 'Group',
    })
  }

  /** Existing arcs incident on whichever endpoint is a transport node
   *  (feeds the §15 through-path default). */
  const transportArcs = (sourceIri: string, targetIri: string) => {
    const sourceT = isTransportEntity(state.modelNodes.get(sourceIri)?.entityType, catalogue)
    const targetT = isTransportEntity(state.modelNodes.get(targetIri)?.entityType, catalogue)
    const transport = sourceT && !targetT ? sourceIri : targetT && !sourceT ? targetIri : undefined
    if (!transport) return []
    return [...state.modelArcs.values()].filter(
      (a) => a.sourceIri === transport || a.targetIri === transport)
  }

  const handleDelete = () => {
    if (inRef) return
    if (state.selectedVisibleNodeIds.length) {
      const nodes = state.selectedVisibleNodeIds
        .map((id) => graphView.nodes.find((n) => n.id === id))
        .filter((n): n is NonNullable<typeof n> =>
          n !== undefined && n.type === 'leaf' && n.treeNodeId !== undefined)
        .map((n) => ({
          visibleNodeId: n.id,
          treeNodeId: n.treeNodeId!,
          modelNodeIri: n.modelNodeIri,
        }))
      if (nodes.length) dispatch({ type: 'deleteNodes', nodes })
    } else if (state.selectedModelArcIri) {
      dispatch({ type: 'deleteArc', iri: state.selectedModelArcIri })
    }
  }

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (state.viewRefIri !== null) return   // reference view: read-only
      if (e.key === 'Delete' || e.key === 'Backspace') {
        handleDelete()
      } else if (e.key === 'Escape') {
        dispatch({ type: 'selectNodes', ids: [] })
      } else if (e.key === 'r' && state.selectedModelArcIri) {
        // §15: 'r' reverses the selected token-flow arc's reference direction
        const arc = state.modelArcs.get(state.selectedModelArcIri)
        if (arc && arcCarrier(arc.arcType) === 'token-flow') {
          dispatch({ type: 'reverseArcOrientation', iri: arc.iri })
        }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleDelete, state.selectedModelArcIri, state.modelArcs])

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
    marquee,
  }
}
