import { useRef, useEffect } from 'react'
import type { KonvaEventObject } from 'konva/lib/Node'
import type { Stage as KonvaStage } from 'konva/lib/Stage'
import type { AppState, Command } from '../state/ModelState'
import type { GraphView, NodeType, ArcType } from '../types'
import type { SceneObject, SceneInteractionHandlers } from '../scene/types'
import { resolveConnectionAsync, pickArcType, modelNodeIri } from '@promo/semantic'
import type { ConnectionRuleResolver, SemanticCatalogue } from '@promo/semantic'
import { arcCarrier, defaultOrientation } from '../model/ModelGraph'
import { NODE_RADIUS, entityHalfExtent } from '../scene/buildScene'
import { GRAPH_IRI, loadModelDoc } from '../api'
import { refViewState } from '../modelPersistence'
import { transition, editableTarget } from './interaction'
import type { Mode, Event, Ctx, Output, NodeCtx } from './interaction'

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
  /** The interaction automaton's current mode — App reads `armed`
   *  for the connect-gesture preview. */
  interaction: Mode
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
  ruleResolver: ConnectionRuleResolver,
  catalogue: SemanticCatalogue,
  interaction: Mode,
  setInteraction: (m: Mode) => void,
): CanvasEventHandlers {
  const wasDragged = useRef(false)
  const lastClickTime = useRef(0)
  const isPanning = useRef(false)
  const lastPanPos = useRef<{ x: number; y: number } | null>(null)
  /** Members of the selection set at dragStart — multi-drag applies
   *  the dragged node's delta to every member. */
  const dragSet = useRef<{
    originId: string
    members: { id: string; start: { x: number; y: number }; he: { x: number; y: number } }[]
  } | null>(null)

  const mode = interaction

  // §22 reference view — inside a referenced artefact's scope the
  // canvas is read-only: the content belongs to another artefact.
  // Only navigation (descending composites / nested references)
  // stays live; every mutating gesture is gated on `inRef`.
  const inRef = state.viewRefIri !== null
  const scopeRefs = inRef
    ? state.refStates.get(state.viewRefIri!)?.compositeRefs
    : state.compositeRefs

  // §13 (2026-11-06): an armed connect is branch-independent — the
  // automaton decides what survives a view change (armed stays;
  // marquee etc. die).  setView dispatches from several places
  // (breadcrumb, back button, enterComposite), so watch the view
  // inputs rather than each call site.
  useEffect(() => {
    setInteraction(transition(interaction, { kind: 'viewChanged' }, buildCtx()).next)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.currentViewNodeId, state.viewRefIri])

  const buildCtx = (): Ctx => {
    const arc = state.selectedModelArcIri
      ? state.modelArcs.get(state.selectedModelArcIri)
      : undefined
    return {
      inRef,
      selectedIds: state.selectedVisibleNodeIds,
      selectedId: state.selectedVisibleNodeId,
      selectedArcIri: state.selectedModelArcIri,
      selectedArcCarrier: arc ? (arcCarrier(arc.arcType) ?? null) : null,
      graphView,
    }
  }

  /** Async connect effect — resolves the rule, picks the arc type,
   *  computes the §15 orientation, dispatches insertArc.  Re-arm on
   *  the target is already encoded in the automaton's next mode. */
  const runConnect = async (o: Extract<Output, { kind: 'connect' }>) => {
    const result = await resolveConnectionAsync(
      o.source.entityType, o.target.entityType, catalogue, ruleResolver)
    const arcType = pickArcType(result, activeArcType)
    if (!arcType) return
    const orientation = defaultOrientation(
      arcType, o.source.modelIri, o.target.modelIri,
      isTransportEntity(o.source.entityType, catalogue),
      isTransportEntity(o.target.entityType, catalogue),
      transportArcs(o.source.modelIri, o.target.modelIri),
    )
    // No iri — the reducer mints on its fresh arcCounter, so two
    // interleaved resolves cannot collide.
    dispatch({
      type: 'insertArc',
      graphIri: GRAPH_IRI!,
      sourceIri: o.source.modelIri,
      targetIri: o.target.modelIri,
      arcType,
      referenceFrom: orientation?.referenceFrom,
      referenceTo: orientation?.referenceTo,
    })
  }

  /** Run one automaton output — commands dispatch, effects execute. */
  const runOutput = (o: Output) => {
    switch (o.kind) {
      case 'cmd':
        dispatch(o.cmd)
        return
      case 'insertNode':
        insertNodeAt(o.point.x, o.point.y)
        return
      case 'connect':
        void runConnect(o)
        return
      case 'enterComposite':
        enterComposite(o.treeNodeId)
        return
      case 'swallowed':
        // Dead gestures are no longer silent — surface the reason.
        console.debug(`gesture swallowed: ${o.reason}`)
        return
    }
  }

  /** Feed a normalized event through the automaton. */
  const fire = (ev: Event) => {
    const { next, out } = transition(mode, ev, buildCtx())
    setInteraction(next)
    for (const o of out) runOutput(o)
  }

  const nodeCtx = (obj: Extract<SceneObject, { kind: 'node' }>): NodeCtx => ({
    kind: obj.nodeType === 'leaf' ? 'leaf'
      : obj.nodeType === 'composite' ? 'composite' : 'chrome',
    id: obj.selectionId!,
    treeNodeId: obj.treeNodeId,
    modelNodeIri: obj.modelNodeIri,
    entityType: obj.entityType,
  })

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

  const mods = (e: { ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }) => ({
    ctrl: e.ctrlKey || e.metaKey,
    shift: e.shiftKey,
  })

  const handleStageClick = (e: KonvaEventObject<MouseEvent>) => {
    if (wasDragged.current) return
    if (e.evt.button !== 0) return   // Konva fires click for right-button too
    if (e.target !== e.target.getStage()) return

    const now = Date.now()
    if (now - lastClickTime.current < 300) return
    lastClickTime.current = now

    const pos = e.target.getStage()?.getPointerPosition()
    if (!pos) return

    const sceneX = (pos.x - stageSize.width / 2 - pan.x) / scale
    const sceneY = (pos.y - stageSize.height / 2 - pan.y) / scale
    fire({ kind: 'stageClick', point: { x: sceneX, y: sceneY }, mods: mods(e.evt) })
  }

  const handleStageRightClick = (e: KonvaEventObject<MouseEvent>) => {
    e.evt.preventDefault()
    fire({ kind: 'stageRightClick' })
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
      e.evt.button === 0 && e.evt.shiftKey &&
      e.target === e.target.getStage()
    ) {
      const p = pointerToScene(e.target.getStage())
      if (!p) return
      fire({ kind: 'marqueeStart', point: p })
    }
  }

  const handleStageMouseMove = (e: KonvaEventObject<MouseEvent>) => {
    if (mode.name === 'marquee') {
      const p = pointerToScene(e.target.getStage())
      if (!p) return
      fire({ kind: 'marqueeMove', point: p })
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
    if (mode.name === 'marquee') {
      const p = pointerToScene(e.target.getStage())
      fire({ kind: 'marqueeEnd', point: p ?? { x: 0, y: 0 }, mods: mods(e.evt) })
      // Swallow the click that follows mouseup — it would insert a node.
      wasDragged.current = true
      setTimeout(() => { wasDragged.current = false }, 50)
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
      fire({ kind: 'nodeClick', node: nodeCtx(obj), mods: mods(e.evt) })
    } else if (obj.kind === 'arc') {
      fire({ kind: 'arcClick', iri: obj.arcIri! })
    } else if (obj.kind === 'knot' && obj.arcIri !== undefined) {
      fire({ kind: 'knotClick', arcIri: obj.arcIri })
    }
  }

  const onSceneRightClick = (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => {
    e.evt.preventDefault()
    e.cancelBubble = true
    if (wasDragged.current) return

    if (obj.kind === 'knot') {
      if (obj.arcIri !== undefined && obj.knotIndex !== undefined) {
        fire({ kind: 'knotRightClick', arcIri: obj.arcIri, knotIndex: obj.knotIndex })
      }
      return
    }
    if (obj.kind === 'arc' && obj.arcIri) {
      const modelArc = state.modelArcs.get(obj.arcIri)
      fire({ kind: 'arcRightClick', arcIri: obj.arcIri, carrier: modelArc ? (arcCarrier(modelArc.arcType) ?? null) : null })
      return
    }
    if (obj.kind !== 'node') return
    fire({ kind: 'nodeRightClick', node: nodeCtx(obj) })
  }

  const onSceneDoubleClick = (obj: SceneObject, e: KonvaEventObject<MouseEvent>) => {
    e.cancelBubble = true
    if (wasDragged.current) return
    if (e.evt.button !== 0) return
    if (obj.kind === 'knot') {
      if (obj.arcIri !== undefined) {
        fire({ kind: 'knotDoubleClick', arcIri: obj.arcIri, point: { x: obj.x, y: obj.y } })
      }
      return
    }
    if (obj.kind === 'arc') {
      const pos = e.target.getStage()?.getPointerPosition()
      if (!pos) return
      const sceneX = (pos.x - stageSize.width / 2 - pan.x) / scale
      const sceneY = (pos.y - stageSize.height / 2 - pan.y) / scale
      fire({ kind: 'arcDoubleClick', arcIri: obj.arcIri!, point: { x: sceneX, y: sceneY } })
      return
    }
    if (obj.kind === 'node' && obj.treeNodeId !== undefined) {
      const isRef = !!scopeRefs?.get(obj.treeNodeId)?.refersTo
      fire({ kind: 'nodeDoubleClick', node: nodeCtx(obj), isRef })
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

    // Dragging an unselected node selects it (standard behaviour) —
    // that first drag selects, it does not start a multi-drag.
    const wasSelected = state.selectedVisibleNodeIds.includes(obj.selectionId)
    fire({ kind: 'dragStartNode', node: nodeCtx(obj) })
    if (!wasSelected) return

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
    fire({ kind: 'keyDelete' })
  }

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      // Keystrokes aimed at form controls (rename fields, dialogs)
      // are not canvas gestures — Backspace there must not delete.
      if (editableTarget(e.target)) return
      if (e.key === 'Delete' || e.key === 'Backspace') {
        handleDelete()
      } else if (e.key === 'Escape') {
        fire({ kind: 'keyEscape' })
      } else if (e.key === 'r') {
        fire({ kind: 'keyReverse' })
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })   // rebinds each render — closure must see the current mode/state

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
    marquee: mode.name === 'marquee' ? mode.rect : null,
    interaction: mode,
  }
}
