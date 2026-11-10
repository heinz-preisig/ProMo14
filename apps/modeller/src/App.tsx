import { useState, useEffect, useMemo, useReducer, useCallback, useRef } from 'react'
import { Stage, Layer, Line, Group, Rect } from 'react-konva'
import type Konva from 'konva'
import type { NodeType, ArcType, OpenArc } from './types'
import type { Iri, NodeGraphicalDefinition, ArcGraphicalDefinition, SemanticCatalogue } from '@promo/semantic'
import { placeholderCatalogue, placeholderRuleResolver, resolveConnection, RemoteRuleResolver, RemoteCatalogue, childIri, modelArcIri, localName } from '@promo/semantic'
import { GRAPH_IRI, SPECIES_IRI, catalogueFetchers, dissolveComposite, extractSubmodel, fetchBehaviourEntityTypes, fetchCatalogueLines, fetchEntityCapabilities, fetchEntityTokens, fetchEntityVariables, fetchSpecies, fetchSpeciesDistribution, loadModel, loadModelDoc, saveModel, saveOntology } from './api'
import type { CatalogueLine, EntityVariable, SpeciesDistribution, SpeciesDocument } from './api'
import { SpeciesPanel } from './SpeciesPanel'
import { SpeciesAliasDialog } from './SpeciesAliasDialog'
import { fetchPortSatisfaction } from './api'
import { hasCarrierArc } from './model/ModelGraph'
import type { PortSatisfaction } from './api'
import { deserializeState, hasContent, refViewState, serializeState } from './modelPersistence'
import type { ModelDocument } from './modelPersistence'
import type { Command, RefViewState } from './state/ModelState'
import { computeGraphView } from './tree/computeGraphView'
import type { AppState } from './state/ModelState'
import { initialState, applyCommand } from './state/ModelState'
import { useCanvasEvents } from './canvas/useCanvasEvents'
import { initialInteraction } from './canvas/interaction'
import type { Mode } from './canvas/interaction'
import { buildScene } from './scene/buildScene'
import { SceneRenderer } from './scene/SceneRenderer'
import type { SceneObject } from './scene/types'

const TOOLBAR_HEIGHT = 40
const BOTTOM_BAR_HEIGHT = 24
const PALETTE_WIDTH = 140

function reducer(state: AppState, cmd: Command): AppState {
  // console.log('Command:', cmd)
  return applyCommand(state, cmd)
}

/** §22: deserialize every artefact the doc references (transitively)
 *  so referenced composites can render their content in place. */
async function fetchRefStates(doc: ModelDocument): Promise<Map<string, RefViewState>> {
  const out = new Map<string, RefViewState>()
  const queue = [...(doc.usesModel ?? [])]
  const seen = new Set(queue)
  while (queue.length) {
    const iri = queue.shift()!
    try {
      const d = await loadModelDoc(iri)
      out.set(iri, refViewState(d))
      for (const r of d.usesModel ?? []) {
        if (!seen.has(r)) { seen.add(r); queue.push(r) }
      }
    } catch { /* stale reference — the composite renders as a shell */ }
  }
  return out
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

  const [catalogue, setCatalogue] = useState<SemanticCatalogue>(placeholderCatalogue)
  const [behaviourEntityTypes, setBehaviourEntityTypes] = useState<Set<string>>(new Set())

  const [speciesDoc, setSpeciesDoc] = useState<SpeciesDocument | null>(null)
  const [speciesIri, setSpeciesIri] = useState<string | undefined>(undefined)
  const [dist, setDist] = useState<SpeciesDistribution | null>(null)
  const [capabilities, setCapabilities] = useState<Map<string, string[]>>(new Map())
  const [entityTokens, setEntityTokens] = useState<Map<string, string>>(new Map())
  const [aliasDialogOpen, setAliasDialogOpen] = useState(false)
  const [fixVars, setFixVars] = useState<EntityVariable[]>([])
  const [modelArtefacts, setModelArtefacts] = useState<CatalogueLine[]>([])

  useEffect(() => {
    let cancelled = false
    RemoteCatalogue.load(catalogueFetchers, placeholderCatalogue).then((cat) => {
      if (!cancelled) setCatalogue(cat)
    })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchBehaviourEntityTypes()
      .then((types) => { if (!cancelled) setBehaviourEntityTypes(types) })
      .catch(() => { if (!cancelled) setBehaviourEntityTypes(new Set()) })
    return () => { cancelled = true }
  }, [])

  // Load the persisted model document once on start (ADR-007), then
  // resolve the species artefact: ?species= overrides the model's
  // promo:usesSpecies pin; a URL override is seeded into state so the
  // next save stamps the pin (§20).
  useEffect(() => {
    let cancelled = false
    fetchEntityCapabilities()
      .then((m) => { if (!cancelled) setCapabilities(m) })
      .catch(() => { /* capabilities optional — gestures stay hidden */ })
    fetchEntityTokens()
      .then((m) => { if (!cancelled) setEntityTokens(m) })
      .catch(() => { /* token labels optional */ })
    loadModel()
      .then((doc) => {
        if (cancelled) return null
        if (hasContent(doc)) {
          dispatch({ type: 'loadState', state: deserializeState(doc) })
        }
        fetchRefStates(doc)
          .then((m) => { if (!cancelled) dispatch({ type: 'setRefStates', states: m }) })
          .catch(() => { /* referenced docs optional — comps stay shells */ })
        if (SPECIES_IRI) {
          dispatch({ type: 'setSpeciesPin', iri: SPECIES_IRI })
        }
        return SPECIES_IRI ?? doc.usesSpecies?.[0] ?? null
      })
      .catch(() => SPECIES_IRI ?? null)  // backend down — honour the URL param
      .then((iri) => {
        if (cancelled || !iri) return
        setSpeciesIri(iri)
        fetchSpecies(iri)
          .then((d) => { if (!cancelled) setSpeciesDoc(d) })
      })
    return () => { cancelled = true }
  }, [])

  // §20 live readout: recompute the species distribution whenever the
  // model's nodes/arcs change (debounced — placements are edited in
  // bursts).  Selection-only commands reuse the same Map refs and do
  // not retrigger.
  useEffect(() => {
    if (!speciesIri) return
    let cancelled = false
    const t = setTimeout(() => {
      fetchSpeciesDistribution(SPECIES_IRI ?? speciesIri)
        .then((d) => { if (!cancelled) setDist(d) })
    }, 400)
    return () => { cancelled = true; clearTimeout(t) }
  }, [state.modelNodes, state.modelArcs, speciesIri])

  const onSave = useCallback(async () => {
    try {
      await saveModel(serializeState(state))
      await saveOntology()
    } catch (err) {
      console.error('Failed to save model:', err)
    }
  }, [state])

  const stageRef = useRef<Konva.Stage>(null)
  const onScreenshot = useCallback(() => {
    try {
      const stage = stageRef.current
      if (!stage) {
        console.warn('screenshot: no stage')
        return
      }
      const viewLabel = (
        state.tree.nodes.get(state.currentViewNodeId)?.label ?? 'root'
      ).replace(/[^\w-]+/g, '_')
      const stamp = new Date().toISOString().replace(/[:.]/g, '-')
      const a = document.createElement('a')
      a.href = stage.toDataURL({ pixelRatio: 2 })
      a.download = `promo-${viewLabel}-${stamp}.png`
      document.body.appendChild(a)
      a.click()
      a.remove()
    } catch (err) {
      console.error('screenshot failed:', err)
    }
  }, [state])

  const reload = useCallback(async () => {
    const doc = await loadModel()
    if (hasContent(doc)) dispatch({ type: 'loadState', state: deserializeState(doc) })
    fetchRefStates(doc)
      .then((m) => dispatch({ type: 'setRefStates', states: m }))
      .catch(() => { /* referenced docs optional */ })
  }, [])

  // §22 library pick: model artefacts usable as referenced composites
  useEffect(() => {
    let cancelled = false
    fetchCatalogueLines().then((lines) => {
      if (!cancelled) setModelArtefacts(lines.filter((l) => l.type === 'model'))
    })
    return () => { cancelled = true }
  }, [])

  // §22 interface summary: lazily fetch each artefact's declared
  // terminals (root composite open arcs) on first hover.
  const [ifaceSummary, setIfaceSummary] =
    useState<Map<string, OpenArc[]>>(new Map())
  const ifaceRequested = useRef<Set<string>>(new Set())
  const loadInterface = useCallback((iri: string) => {
    if (ifaceRequested.current.has(iri)) return
    ifaceRequested.current.add(iri)
    loadModelDoc(iri).then((doc) => {
      const root = doc.composites.find((c) => c.treeId === doc.rootTreeId)
      setIfaceSummary((m) => new Map(m).set(iri, root?.openArcs ?? []))
    }).catch(() => {
      setIfaceSummary((m) => new Map(m).set(iri, []))
    })
  }, [])

  // §22 insert: materialize the referenced artefact's declared interface
  // (its root composite's open arcs) as this occurrence's terminals.
  const insertReferenced = useCallback(async (line: CatalogueLine) => {
    if (state.viewRefIri !== null) return   // reference view is read-only
    try {
      const doc = await loadModelDoc(line.iri)
      const root = doc.composites.find((c) => c.treeId === doc.rootTreeId)
      const entityOf = new Map(doc.nodes.map((n) => [n.iri, n.entityType]))
      const refs = new Map(state.refStates)
      refs.set(line.iri, refViewState(doc))
      dispatch({ type: 'setRefStates', states: refs })
      dispatch({
        type: 'insertReferencedComposite',
        label: line.label,
        parentViewNodeId: state.currentViewNodeId,
        x: 0,
        y: 0,
        refersTo: line.iri,
        graphIri: GRAPH_IRI!,
        terminals: (root?.openArcs ?? []).map((o) => ({
          iri: o.iri,
          externalIri: o.externalIri,
          arcType: o.arcType,
          isSource: o.isSource,
          refToExternal: o.refToExternal,
          externalEntityType: o.externalEntityType
            ?? entityOf.get(o.externalIri),
          phantomEntityType: o.phantomEntityType,
        })),
      })
    } catch (err) {
      console.error('Failed to insert referenced composite:', err)
    }
  }, [state.tree.nextId, state.currentViewNodeId, state.viewRefIri, state.refStates])

  // Stamp semantics (repeated structures): the artefact is a template —
  // its subtree is deep-copied inline with fresh tree ids and fresh
  // {graph}/Node_{id} leaf IRIs.  §33 copy insert: no refersTo; open
  // arcs persist as host open arcs; dissolvedFrom keeps provenance.
  const insertCopy = useCallback(async (line: CatalogueLine) => {
    if (state.viewRefIri !== null) return   // reference view is read-only
    try {
      const doc = await loadModelDoc(line.iri)
      const stamped = deserializeState(doc)
      // A refersTo inside the stamped subtree stays a live reference —
      // preload its read-only view state or it renders empty.
      const missing = [...stamped.compositeRefs.values()]
        .map((r) => r.refersTo)
        .filter((iri) => iri && !state.refStates.has(iri))
      if (missing.length) {
        const refs = new Map(state.refStates)
        for (const iri of missing) {
          try { refs.set(iri, refViewState(await loadModelDoc(iri))) }
          catch { /* unresolved reference — composite renders empty */ }
        }
        dispatch({ type: 'setRefStates', states: refs })
      }
      dispatch({
        type: 'insertStamped',
        label: line.label,
        parentViewNodeId: state.currentViewNodeId,
        x: 0,
        y: 0,
        stamped,
        graphIri: GRAPH_IRI!,
        sourceIri: line.iri,
      })
    } catch (err) {
      console.error('Failed to stamp copy:', err)
    }
  }, [state.tree.nextId, state.currentViewNodeId, state.viewRefIri])

  const NODE_TYPES = useMemo(() => catalogue.getBaseEntities()
    .filter((entity) => behaviourEntityTypes.has(entity.iri))
    .map((entity) => {
      const g = catalogue.getGraphicalDefinition(entity.graphicalDefinitionIri!) as NodeGraphicalDefinition | undefined
      return { id: entity.iri, label: entity.label, fill: g?.fill ?? '#eee', stroke: g?.stroke ?? '#333' }
    }), [catalogue, behaviourEntityTypes])

  const ARC_TYPES = useMemo(() => catalogue.getArcTypes().map((arcType) => {
    const g = catalogue.getGraphicalDefinition(arcType.graphicalDefinitionIri!) as ArcGraphicalDefinition | undefined
    return { id: arcType.iri, label: arcType.label, stroke: g?.stroke ?? '#333', dash: g?.dash }
  }), [catalogue])

  // --- Palette state (UI only, not part of model) ---
  const [activeNodeType, setActiveNodeType] = useState<NodeType>('https://w3id.org/promo#TypeA')
  const [activeArcType, setActiveArcType] = useState<ArcType>('https://w3id.org/promo#ArcType1')
  // §33 phantom pick: entity type the user imagines on a terminal's
  // missing end; the connection rules derive the contract's arc kind.
  const [phantomPeer, setPhantomPeer] = useState('')
  /** §33: when the rule set licenses several contract kinds for the
   *  pair (access/reference + physical-same/token-flow), the user
   *  picks; falls back to the first licensed kind. */
  const [arcPick, setArcPick] = useState<string | null>(null)

  // Keep the active palette selection valid when the catalogue swaps.
  useEffect(() => {
    if (NODE_TYPES.length && !NODE_TYPES.some((t) => t.id === activeNodeType)) {
      setActiveNodeType(NODE_TYPES[0].id as NodeType)
    }
    if (ARC_TYPES.length && !ARC_TYPES.some((t) => t.id === activeArcType)) {
      setActiveArcType(ARC_TYPES[0].id as ArcType)
    }
  }, [NODE_TYPES, ARC_TYPES, activeNodeType, activeArcType])

  const [stageSize, setStageSize] = useState({
    width: window.innerWidth - PALETTE_WIDTH * 2,
    height: window.innerHeight - TOOLBAR_HEIGHT - BOTTOM_BAR_HEIGHT,
  })

  // --- View transform (pan / zoom) ---
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [scale, setScale] = useState(1)

  // --- Hovered node for connection feedback ---
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)
  const [hoveredObject, setHoveredObject] = useState<SceneObject | null>(null)

  // --- Interaction automaton: the canvas gesture mode lives here.
  //  `armed` = connect gesture awaiting its target — the old
  //  pendingConnection, now a mode the transition table owns.
  const [interaction, setInteraction] = useState<Mode>(initialInteraction)
  const pendingConnection = interaction.name === 'armed'
    ? { sourceModelIri: interaction.source.modelIri, sourceEntityType: interaction.source.entityType }
    : null

  // --- Connection rule resolver: remote (ontology backend) with the
  // placeholder allow-all as fallback while the backend is unreachable.
  // cacheBump re-renders hover feedback when an async answer lands.
  const [cacheBump, setCacheBump] = useState(0)
  const [ruleResolver] = useState(
    () =>
      new RemoteRuleResolver({
        graphIri: GRAPH_IRI,
        fallback: placeholderRuleResolver,
        onUpdate: () => setCacheBump((v) => v + 1),
      }),
  )

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
  // §22 reference view: when `viewRefIri` is set, `currentViewNodeId`
  // indexes the referenced artefact's tree — render its (read-only)
  // maps instead of the host's.
  const refScope = state.viewRefIri ? state.refStates.get(state.viewRefIri) : undefined
  const graphView = useMemo(
    () => computeGraphView(
      state.currentViewNodeId,
      refScope?.tree ?? state.tree,
      refScope?.modelNodes ?? state.modelNodes,
      refScope?.modelArcs ?? state.modelArcs,
      refScope?.layoutStore ?? state.layoutStore,
      refScope?.openArcs ?? state.openArcs,
      refScope?.knotStore ?? state.knotStore,
      stageSize.width, stageSize.height),
    [state.currentViewNodeId, refScope, state.tree, state.modelNodes, state.modelArcs, state.layoutStore, state.openArcs, state.knotStore, stageSize.width, stageSize.height]
  )

  // ADR-008 fix picker: the selected leaf's assignment variables.
  useEffect(() => {
    const vis = graphView.nodes.find((n) => n.id === state.selectedVisibleNodeId)
    const sel = vis?.modelNodeIri ? state.modelNodes.get(vis.modelNodeIri) : undefined
    if (!sel) { setFixVars([]); return }
    let cancelled = false
    fetchEntityVariables(sel.entityType).then((vs) => {
      if (!cancelled) setFixVars(vs)
    })
    return () => { cancelled = true }
  }, [state.selectedVisibleNodeId, state.modelNodes, graphView])

  // --- Gesture pair (source entity type + hovered leaf) ---
  // Shared by the resolve-connection memo and the §13/§14
  // port-satisfaction fetch below.
  const gestureSourceEt = pendingConnection?.sourceEntityType
    ?? (state.selectedVisibleNodeId
      ? graphView.nodes.find((n) => n.id === state.selectedVisibleNodeId)?.entityType
      : undefined)
  const hoveredLeaf = hoveredNodeId
    ? graphView.nodes.find((n) => n.id === hoveredNodeId)
    : undefined
  const gestureTargetEt =
    hoveredLeaf?.type === 'leaf' ? hoveredLeaf.entityType : undefined
  const gestureHasSource = !!(pendingConnection || state.selectedVisibleNodeId)

  // --- Compute connection-rule feedback for hovered target ---
  const { hoveredHighlight, validConnections, alreadyConnected } = useMemo(() => {
    const sourceEntityType = gestureSourceEt
    const hasSource = gestureHasSource
    if (!hasSource || !hoveredNodeId || sourceEntityType === undefined) {
      return { hoveredHighlight: null, alreadyConnected: false, validConnections: [] as { arcTypeIri: Iri; matchedTokens?: Iri[] }[] }
    }
    const targetNode = graphView.nodes.find((n) => n.id === hoveredNodeId)
    if (targetNode?.type !== 'leaf' || !targetNode.entityType) {
      return { hoveredHighlight: null, alreadyConnected: false, validConnections: [] as { arcTypeIri: Iri; matchedTokens?: Iri[] }[] }
    }
    // Don't show feedback if hovering the pending source itself
    if (pendingConnection && targetNode.modelNodeIri === pendingConnection.sourceModelIri) {
      return { hoveredHighlight: null, alreadyConnected: false, validConnections: [] as { arcTypeIri: Iri; matchedTokens?: Iri[] }[] }
    }
    // §14 duplicate guard: a same-carrier arc already spans the pair
    // — the gesture is refused even when the rules license it.
    const srcModelIri = pendingConnection?.sourceModelIri
      ?? graphView.nodes.find(
        (n) => n.id === state.selectedVisibleNodeId)?.modelNodeIri
    const alreadyConnected = hasCarrierArc(
      state.modelArcs, srcModelIri ?? '',
      targetNode.modelNodeIri ?? '', activeArcType)
    const result = resolveConnection(
      sourceEntityType,
      targetNode.entityType,
      catalogue,
      ruleResolver,
    )
    if (result.status === 'forbidden') {
      return { hoveredHighlight: 'invalid' as const, alreadyConnected, validConnections: [] as { arcTypeIri: Iri; matchedTokens?: Iri[] }[] }
    }
    if (result.connections.length === 0) {
      // Cache miss — remote answer in flight; no highlight yet.
      return { hoveredHighlight: null, alreadyConnected, validConnections: [] as { arcTypeIri: Iri; matchedTokens?: Iri[] }[] }
    }
    // The gesture is legal only for the *selected* carrier — other
    // licensed types are still listed, but hover marks the pair
    // invalid so the refusal is visible before release.
    const licensed = result.connections.map((c) => ({
      arcTypeIri: c.arcTypeIri,
      matchedTokens: c.matchedTokens,
    }))
    return {
      hoveredHighlight: !alreadyConnected && licensed.some(
        (c) => c.arcTypeIri === activeArcType)
        ? 'valid' as const
        : 'invalid' as const,
      alreadyConnected,
      validConnections: licensed,
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.selectedVisibleNodeId, hoveredNodeId, graphView, pendingConnection, ruleResolver, catalogue, cacheBump, activeArcType, state.modelArcs])

  // §14 admissibility hint: leaves the armed connect cannot reach
  // with the *selected* carrier — forbidden pair, or allowed under
  // other carriers only.  Sync resolve warms the cache: a miss
  // answers neutral (not blocked) and the fetch's cacheBump
  // recomputes when the real answer lands.
  const blockedLeafIds = useMemo(() => {
    const out = new Set<string>()
    if (!gestureHasSource || !gestureSourceEt) return out
    const srcModelIri = pendingConnection?.sourceModelIri
      ?? graphView.nodes.find(
        (n) => n.id === state.selectedVisibleNodeId)?.modelNodeIri
    for (const n of graphView.nodes) {
      if (n.type !== 'leaf' || !n.entityType) continue
      if (n.id === state.selectedVisibleNodeId) continue
      if (pendingConnection
          && n.modelNodeIri === pendingConnection.sourceModelIri) continue
      const res = resolveConnection(
        gestureSourceEt, n.entityType, catalogue, ruleResolver)
      if (res.status === 'forbidden'
          || (res.connections.length > 0
              && !res.connections.some((c) => c.arcTypeIri === activeArcType))
          || hasCarrierArc(state.modelArcs, srcModelIri ?? '',
                           n.modelNodeIri ?? '', activeArcType)) {
        out.add(n.id)
      }
    }
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gestureHasSource, gestureSourceEt, graphView,
      state.selectedVisibleNodeId, pendingConnection,
      catalogue, ruleResolver, activeArcType, cacheBump,
      state.modelArcs])

  // §13/§14 port-satisfaction: adjudicate the hovered pair.  Union
  // over all licensed carriers until the user picks an arc type, then
  // narrowed to that carrier so `unlicensed` reflects the choice.
  const [portSat, setPortSat] = useState<PortSatisfaction | null>(null)
  useEffect(() => {
    if (!gestureHasSource || !gestureSourceEt || !gestureTargetEt
        || (pendingConnection
            && hoveredLeaf?.modelNodeIri === pendingConnection.sourceModelIri)) {
      setPortSat(null)
      return
    }
    const carrier = validConnections.some(
        (c) => c.arcTypeIri === activeArcType)
      ? activeArcType : undefined
    let cancelled = false
    fetchPortSatisfaction(gestureSourceEt, gestureTargetEt, carrier)
      .then((s) => { if (!cancelled) setPortSat(s) })
      .catch(() => { if (!cancelled) setPortSat(null) })
    return () => { cancelled = true }
  }, [gestureHasSource, gestureSourceEt, gestureTargetEt, hoveredLeaf,
      pendingConnection, activeArcType, validConnections])

  // --- Three-panel zone boundaries ---
  const leftZoneX = -stageSize.width / 2 + 80
  const rightZoneX = stageSize.width / 2 - 80
  const zoneTop = -stageSize.height / 2
  const zoneBottom = stageSize.height / 2

  // --- Build unified scene object list ---
  const selectedNodeIds = useMemo(
    () => new Set(state.selectedVisibleNodeIds),
    [state.selectedVisibleNodeIds]
  )
  const sceneObjects = useMemo(
    () => buildScene({
      graphView,
      selectedNodeIds,
      selectedArcIri: state.selectedModelArcIri,
      draggingOpenArc,
      hoveredNodeId,
      hoveredHighlight,
      blockedNodeIds: blockedLeafIds,
      catalogue,
      tokenByEntityType: entityTokens,
      readOnly: state.viewRefIri !== null,
    }),
    [graphView, selectedNodeIds, state.selectedModelArcIri, draggingOpenArc, hoveredNodeId, hoveredHighlight, blockedLeafIds, catalogue, entityTokens, state.viewRefIri]
  )

  // --- Canvas event handlers (isolated from rendering) ---
  const {
    handleStageClick,
    handleStageRightClick,
    handleStageMouseDown,
    handleStageMouseMove,
    handleStageMouseUp,
    handleStageWheel,
    groupSelectedNodes,
    sceneHandlers,
    marquee,
  } = useCanvasEvents(state, graphView, stageSize, activeNodeType, activeArcType, dispatch, pan, setPan, scale, setScale, setDraggingOpenArc, setHoveredNodeId, setHoveredObject, ruleResolver, catalogue, interaction, setInteraction)

  const selectedVisibleNode = graphView.nodes.find((n) => n.id === state.selectedVisibleNodeId)
  const selectedArc = graphView.arcs.find((a) => a.modelArcIri === state.selectedModelArcIri)

  // §22 extract to submodel (move): the selected composite's subtree
  // moves to a new artefact; the host keeps a referenced composite.
  // One name is asked — the artefact IRI is derived (slugged) and
  // pre-checked against the catalogue; the backend 409 is the hard
  // guard if the catalogue is stale.
  const extractSelected = useCallback(async () => {
    if (selectedVisibleNode?.treeNodeId === undefined) return
    const treeId = selectedVisibleNode.treeNodeId
    const slugOf = (s: string) =>
      s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
    const taken = new Set(
      (await fetchCatalogueLines().catch(() => [] as CatalogueLine[]))
        .map((l) => l.iri))
    let suggestion = selectedVisibleNode.label
    let ask = 'Name for the extracted submodel:'
    while (true) {
      const name = window.prompt(ask, suggestion)
      if (name === null) return
      const label = name || suggestion
      const slug = slugOf(label)
      if (!slug) {
        ask = 'Name produces no usable IRI — pick another:'
        suggestion = name || suggestion
        continue
      }
      const iri = childIri(GRAPH_IRI!, slug)
      if (taken.has(iri)) {
        ask = `"${slug}" already names an artefact — choose another name:`
        suggestion = name || suggestion
        continue
      }
      try {
        await extractSubmodel(iri, [treeId], label)
        await reload()
        fetchCatalogueLines().then((lines) =>
          setModelArtefacts(lines.filter((l) => l.type === 'model')))
      } catch (err) {
        console.error('Extract failed:', err)
      }
      return
    }
  }, [selectedVisibleNode, reload])

  // §22 dissolve: one-way flatten — the referenced artefact's content
  // is inlined; external arcs remap onto the copied terminals.
  const dissolveSelected = useCallback(async () => {
    const treeId = selectedVisibleNode?.treeNodeId
    if (treeId === undefined) return
    if (!window.confirm('Dissolve this reference into inline content? This cannot be undone.')) return
    try {
      await dissolveComposite(treeId)
      await reload()
    } catch (err) {
      console.error('Dissolve failed:', err)
    }
  }, [selectedVisibleNode, reload])

  const ungroupSelected = useCallback(() => {
    const treeId = selectedVisibleNode?.treeNodeId
    if (treeId === undefined) return
    dispatch({ type: 'ungroup', treeNodeId: treeId })
  }, [selectedVisibleNode])

  // Derived arc token display: the arc carries no declared token — the
  // licensed token set comes from resolve-connection's matched_tokens
  // for its endpoint entity types (cache-backed sync read).
  const tokenLabel = (iri: Iri) =>
    catalogue.getToken(iri)?.label ?? iri.split(/[/#]/).pop() ?? iri
  const selectedArcTokens = ((): Iri[] => {
    if (!selectedArc) return []
    const selArc = state.modelArcs.get(selectedArc.modelArcIri)
    if (!selArc) return []
    const srcEt = state.modelNodes.get(selArc.sourceIri)?.entityType
    const tgtEt = state.modelNodes.get(selArc.targetIri)?.entityType
    if (!srcEt || !tgtEt) return []
    const res = resolveConnection(srcEt, tgtEt, catalogue, ruleResolver)
    if (res.status !== 'allowed') return []
    const conn =
      res.connections.find((c) => c.arcTypeIri === selectedArc.modelArcType)
      ?? res.connections[0]
    return conn?.matchedTokens ?? []
  })()

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
?        <span style={{ fontSize: 15, color: '#333' }}>
          Model: <strong>{localName(GRAPH_IRI!)}</strong>
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, fontSize: 13 }}>
          <span style={{ color: '#555' }}>
            {state.viewRefIri ? (
              <>
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault()
                    // Back to the host view containing the reference.
                    const refComp = [...state.compositeRefs]
                      .find(([, r]) => r.refersTo === state.viewRefIri)?.[0]
                    const back = refComp !== undefined
                      ? state.tree.nodes.get(refComp)?.parentId ?? state.tree.rootId
                      : state.tree.rootId
                    dispatch({ type: 'setView', viewNodeId: back, refIri: null })
                  }}
                  style={{ color: '#58c', cursor: 'pointer', textDecoration: 'none' }}
                >
                  ◂ back
                </a>{' '}
                {refScope?.tree.nodes.get(state.currentViewNodeId)?.label ?? 'reference'}{' '}
                <em style={{ color: '#999', fontStyle: 'normal' }}>(referenced — read-only)</em>
              </>
            ) : (
              <>
                View:{' '}
                <input
                  style={{
                    fontSize: 13,
                    border: 'none',
                    borderBottom: '1px dotted #999',
                    background: 'transparent',
                    width: 110,
                  }}
                  title="Composite name — renames the view you're inside"
                  value={state.tree.nodes.get(state.currentViewNodeId)?.label ?? ''}
                  onChange={(e) => dispatch({
                    type: 'setNodeLabel',
                    treeNodeId: state.currentViewNodeId,
                    label: e.target.value,
                  })}
                />
              </>
            )}
          </span>
          {speciesDoc && (
            <button style={{ fontSize: 12 }}
                    onClick={() => setAliasDialogOpen(true)}>
              Species aliases
            </button>
          )}
          <button style={{ fontSize: 12 }} onClick={onSave}>Save</button>
          <button style={{ fontSize: 12 }} onClick={onScreenshot}>Screenshot</button>
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
            <strong style={{ fontSize: 12 }}>Submodels</strong>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Click to stamp a copy — Ctrl+click for a live reference</div>
            {modelArtefacts.map((l) => {
              const iface = ifaceSummary.get(l.iri)
              const frag = (iri: string) => iri.split(/[/#]/).pop() ?? iri
              return (
                <button
                  key={l.iri}
                  onClick={(e) => e.ctrlKey ? insertReferenced(l) : insertCopy(l)}
                  onMouseEnter={() => loadInterface(l.iri)}
                  title={`${l.iri}${l.referencedBy.length ? ` — referenced by ${l.referencedBy.length}` : ''}`}
                  style={{
                    fontSize: 12,
                    padding: '6px 8px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    background: '#e8e8e8',
                    border: '1px solid #bbb',
                    borderRadius: 4,
                    width: '100%',
                  }}
                >
                  {l.label}
                  {iface !== undefined && (
                    <div style={{ fontSize: 10, color: '#666', marginTop: 2 }}>
                      {iface.length === 0
                        ? 'closed — no declared terminals'
                        : iface.map((o) =>
                            `${o.isSource ? '→' : '←'} ${frag(o.arcType)}` +
                            (o.externalEntityType ? ` · ${frag(o.externalEntityType)}` : '')
                          ).join('  |  ')}
                    </div>
                  )}
                </button>
              )
            })}
            {modelArtefacts.length === 0 && (
              <div style={{ fontSize: 11, color: '#999' }}>no model artefacts</div>
            )}
          </div>

          <div style={{ marginTop: 8, borderTop: '1px solid #ccc', paddingTop: 8 }}>
            <strong style={{ fontSize: 12 }}>Actions</strong>
            <button
              onClick={extractSelected}
              disabled={selectedVisibleNode?.type !== 'composite' || state.viewRefIri !== null}
              title="Move the selected composite into a new artefact; the host keeps a reference"
              style={{
                fontSize: 12,
                padding: '6px 8px',
                width: '100%',
                cursor: selectedVisibleNode?.type === 'composite' ? 'pointer' : 'not-allowed',
                background: selectedVisibleNode?.type === 'composite' ? '#e8f4fd' : '#eee',
                border: '1px solid #bbb',
                borderRadius: 4,
                marginTop: 4,
              }}
            >
              Extract to submodel
            </button>
            <button
              onClick={groupSelectedNodes}
              disabled={!state.selectedVisibleNodeIds.length || state.viewRefIri !== null}
              title="Wrap the selected nodes in a composite (Ctrl+click or Shift+drag to multi-select)"
              style={{
                fontSize: 12,
                padding: '6px 8px',
                width: '100%',
                cursor: state.selectedVisibleNodeIds.length ? 'pointer' : 'not-allowed',
                background: state.selectedVisibleNodeIds.length ? '#e8f4fd' : '#eee',
                border: '1px solid #bbb',
                borderRadius: 4,
                marginTop: 4,
              }}
            >
              Group selected
            </button>
            <button
              onClick={ungroupSelected}
              disabled={
                selectedVisibleNode?.type !== 'composite'
                || !!state.compositeRefs.get(selectedVisibleNode?.treeNodeId ?? -1)?.refersTo
                || state.viewRefIri !== null
              }
              title="Explode this composite — children move up one level, the shell is removed (references: use Dissolve in Properties)"
              style={{
                fontSize: 12,
                padding: '6px 8px',
                width: '100%',
                cursor: selectedVisibleNode?.type === 'composite' ? 'pointer' : 'not-allowed',
                background: selectedVisibleNode?.type === 'composite' ? '#e8f4fd' : '#eee',
                border: '1px solid #bbb',
                borderRadius: 4,
                marginTop: 4,
              }}
            >
              Ungroup
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
          ref={stageRef}
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
              <SceneRenderer objects={sceneObjects} handlers={sceneHandlers} />
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
              {marquee && (
                <Rect
                  x={marquee.x}
                  y={marquee.y}
                  width={marquee.w}
                  height={marquee.h}
                  fill="rgba(11, 124, 190, 0.08)"
                  stroke="#0b7cbe"
                  strokeWidth={1}
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
              {selectedVisibleNode.treeNodeId !== undefined && (
                <div style={{ marginBottom: 4 }}>
                  Label:{' '}
                  <input
                    style={{ width: 78, fontSize: 11 }}
                    value={selectedVisibleNode.label}
                    onChange={(e) => dispatch({
                      type: 'setNodeLabel',
                      treeNodeId: selectedVisibleNode.treeNodeId!,
                      label: e.target.value,
                    })}
                  />
                </div>
              )}
              <div>ID: {selectedVisibleNode.id}</div>
              <div>Type: {selectedVisibleNode.type}</div>
              {selectedVisibleNode.entityType && (
                <div>Entity: {catalogue.getBaseEntity(selectedVisibleNode.entityType)?.label
                  ?? selectedVisibleNode.entityType}</div>
              )}
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
          {selectedVisibleNode?.modelNodeIri && (() => {
            const selNode = state.modelNodes.get(selectedVisibleNode.modelNodeIri!)
            const fixed = new Set(selNode?.fixes ?? [])
            return (
              <div style={{ fontSize: 11, borderTop: '1px solid #ccc', paddingTop: 6 }}>
                <strong style={{ fontSize: 12 }}>Fix (bound at this node)</strong>
                {fixVars.length === 0 && (
                  <div style={{ color: '#999', fontSize: 10 }}>
                    no closed assignment for this entity type — or no assignment artefact pinned
                  </div>
                )}
                {fixVars.map((v) => (
                  <label key={v.var} style={{ display: 'block', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={fixed.has(v.var)}
                      onChange={() => dispatch({
                        type: 'toggleNodeFix',
                        iri: selNode!.iri,
                        varIri: v.var,
                      })}
                    />
                    {' '}{v.label || v.var.split(/[/#]/).pop()}
                    <span style={{ color: '#999' }}> · {v.role}</span>
                  </label>
                ))}
              </div>
            )
          })()}
          {selectedVisibleNode?.type === 'leaf' &&
            !!selectedVisibleNode.modelNodeIri && (() => {
            const sel = state.modelNodes.get(selectedVisibleNode.modelNodeIri!)
            if (!sel || selectedVisibleNode.treeNodeId === undefined) return null
            const parentId = state.tree.nodes
              .get(selectedVisibleNode.treeNodeId)?.parentId
            if (parentId === null || parentId === undefined) return null
            const terminals = (state.openArcs.get(parentId) ?? [])
              .filter((a) => a.externalIri === sel.iri)
            const short = (iri?: string) => iri?.split(/[/#]/).pop() ?? '—'
            // §33 phantom declare: naming the imagined peer lets the
            // connection rules derive the contract's arc kind.
            const peerRes = phantomPeer
              ? resolveConnection(sel.entityType, phantomPeer, catalogue, ruleResolver)
              : null
            const peerKinds = peerRes?.status !== 'forbidden'
              ? (peerRes?.connections ?? []).map((c) => c.arcTypeIri)
              : []
            const peerEntity = NODE_TYPES.find((t) => t.id === phantomPeer)
            const canDeclare = !!peerEntity && peerKinds.length > 0
            const chosenKind = arcPick && peerKinds.includes(arcPick)
              ? arcPick : peerKinds[0]
            return (
              <div style={{ fontSize: 11, borderTop: '1px solid #ccc', paddingTop: 6 }}>
                <strong style={{ fontSize: 12 }}>Terminals</strong>
                {terminals.map((t) => (
                  <div key={t.iri} style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    marginTop: 4, fontSize: 11,
                  }}>
                    <span style={{ flex: 1 }}>
                      {short(t.phantomEntityType)} · {short(t.arcType)}
                      {t.refToExternal !== undefined &&
                        (t.refToExternal ? ' · →out' : ' · →in')}
                    </span>
                    <button
                      title='flip reference direction'
                      onClick={() => dispatch({
                        type: 'flipTerminalDirection',
                        compositeId: parentId,
                        openArcIri: t.iri,
                      })}
                      style={{ fontSize: 11, cursor: 'pointer' }}
                    >⇄</button>
                    <button
                      title='remove terminal'
                      onClick={() => dispatch({
                        type: 'unexposeTerminal',
                        compositeId: parentId,
                        openArcIri: t.iri,
                      })}
                      style={{ fontSize: 11, cursor: 'pointer' }}
                    >✕</button>
                  </div>
                ))}
                <select
                  value={phantomPeer}
                  onChange={(e) => setPhantomPeer(e.target.value)}
                  style={{ width: '100%', marginTop: 4, fontSize: 11 }}
                >
                  <option value=''>imagine a peer…</option>
                  {NODE_TYPES.map((t) => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>
                <button
                  onClick={() => {
                    dispatch({
                      type: 'exposeTerminal',
                      iri: modelArcIri(GRAPH_IRI!, state.arcCounter),
                      compositeId: parentId,
                      modelNodeIri: sel.iri,
                      entityType: sel.entityType,
                      phantomEntityType: phantomPeer || undefined,
                      arcType: chosenKind,
                    })
                  }}
                  disabled={!canDeclare}
                  style={{
                    fontSize: 12, width: '100%', marginTop: 4,
                    padding: '4px 6px', cursor: canDeclare ? 'pointer' : 'default',
                    background: '#fff', border: '1px solid #bbb',
                    borderRadius: 4,
                  }}
                >
                  Declare terminal
                </button>
                <div style={{ color: '#888', marginTop: 2 }}>
                  {phantomPeer === ''
                    ? 'pick the imagined peer — the rules derive the contract'
                    : peerRes?.status === 'forbidden'
                      ? 'no connection licensed for that pair'
                      : peerKinds.length === 0
                        ? 'resolving the rule set…'
                        : peerKinds.length > 1
                          ? (
                            <label>
                              contract:{' '}
                              <select
                                value={chosenKind}
                                onChange={(e) => setArcPick(e.target.value)}
                                style={{ fontSize: 11 }}
                              >
                                {peerKinds.map((k) => (
                                  <option key={k} value={k}>{short(k)}</option>
                                ))}
                              </select>
                            </label>
                          )
                          : `contract: ${short(chosenKind)}`}
                </div>
              </div>
            )
          })()}
          {selectedVisibleNode?.treeNodeId !== undefined &&
            !!state.compositeRefs.get(selectedVisibleNode.treeNodeId)?.refersTo && (() => {
            const ref = state.compositeRefs.get(selectedVisibleNode.treeNodeId!)!
            const terminals = state.openArcs.get(selectedVisibleNode.treeNodeId!) ?? []
            const kinds = ['ontology', 'library', 'assignment', 'species', 'values']
            return (
              <div style={{ fontSize: 11, borderTop: '1px solid #ccc', paddingTop: 6 }}>
                <strong style={{ fontSize: 12 }}>Reference</strong>
                <div style={{ wordBreak: 'break-all', color: '#555' }}>{ref.refersTo}</div>
                <div style={{ color: '#888' }}>{terminals.length} terminal(s)</div>
                <strong style={{ fontSize: 12 }}>Overrides</strong>
                {kinds.map((k) => (
                  <label key={k} style={{ display: 'block', marginTop: 2 }}>
                    {k}:{' '}
                    <input
                      style={{ width: '100%', fontSize: 11, boxSizing: 'border-box' }}
                      value={ref.overrides[k] ?? ''}
                      placeholder="inherit"
                      onChange={(e) => dispatch({
                        type: 'setCompositeRef',
                        treeNodeId: selectedVisibleNode.treeNodeId!,
                        ref: {
                          refersTo: ref.refersTo,
                          overrides: e.target.value
                            ? { ...ref.overrides, [k]: e.target.value }
                            : Object.fromEntries(
                                Object.entries(ref.overrides).filter(([key]) => key !== k)),
                        },
                      })}
                    />
                  </label>
                ))}
                <button
                  onClick={dissolveSelected}
                  disabled={state.viewRefIri !== null}
                  style={{
                    fontSize: 12,
                    width: '100%',
                    marginTop: 6,
                    padding: '4px 6px',
                    cursor: 'pointer',
                    background: '#fff3e0',
                    border: '1px solid #ffb74d',
                    borderRadius: 4,
                  }}
                >
                  Dissolve (inline content)
                </button>
              </div>
            )
          })()}
          {selectedArc && (
            <div style={{ fontSize: 11 }}>
              <div>Arc: {selectedArc.modelArcIri}</div>
              <div>Type: {selectedArc.arcType}</div>
              <div>From: {selectedArc.sourceId}</div>
              <div>To: {selectedArc.targetId}</div>
              {selectedArcTokens.length > 0 && (
                <div>Tokens: {selectedArcTokens.map(tokenLabel).join(', ')}</div>
              )}
            </div>
          )}
          {/* §20 species gestures — capability-gated, needs ?species= */}
          {speciesDoc && (() => {
            const selNode = selectedVisibleNode?.modelNodeIri
              ? state.modelNodes.get(selectedVisibleNode.modelNodeIri)
              : undefined
            const selArc = selectedArc?.modelArcIri
              ? state.modelArcs.get(selectedArc.modelArcIri)
              : undefined
            const arcTransport = selArc
              ? [selArc.sourceIri, selArc.targetIri].some((ep) =>
                  (capabilities.get(
                    state.modelNodes.get(ep)?.entityType ?? '') ?? [])
                    .includes('species_transport'))
              : false
            return (
              <SpeciesPanel
                node={selNode}
                nodeCaps={capabilities.get(selNode?.entityType ?? '') ?? []}
                arc={selArc}
                arcIsTransport={arcTransport}
                speciesDoc={speciesDoc}
                aliases={state.speciesAliases}
                dist={dist}
                dispatch={dispatch}
              />
            )
          })()}
          {validConnections.length > 0 && (
            <div style={{ fontSize: 11, borderTop: '1px solid #ccc', paddingTop: 8 }}>
              <strong style={{ fontSize: 12 }}>Valid arc types</strong>
              <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Click to select, then right-click target</div>
              {validConnections.map(({ arcTypeIri, matchedTokens }) => {
                const arcDef = ARC_TYPES.find((t) => t.id === arcTypeIri)
                const isActive = activeArcType === arcTypeIri
                return (
                  <button
                    key={arcTypeIri}
                    onClick={() => setActiveArcType(arcTypeIri)}
                    style={{
                      fontSize: 12,
                      padding: '4px 6px',
                      textAlign: 'left',
                      cursor: 'pointer',
                      background: isActive ? '#fff' : '#e8e8e8',
                      border: isActive ? '2px solid #2ecc71' : '1px solid #bbb',
                      borderRadius: 4,
                      width: '100%',
                      marginBottom: 2,
                    }}
                  >
                    {arcDef?.label ?? arcTypeIri}
                    {matchedTokens && matchedTokens.length > 0 && (
                      <span style={{ fontSize: 10, color: '#888' }}>
                        {' '}· {matchedTokens.map(tokenLabel).join(', ')}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          )}
          {/* §13/§14 port demands this connection would feed (advisory) */}
          {portSat && [portSat.source, portSat.target].some(
              (s) => s.ports.length > 0 || !s.has_assignment) && (
            <div style={{ fontSize: 11, borderTop: '1px solid #ccc', paddingTop: 8 }}>
              <strong style={{ fontSize: 12 }}>Ports</strong>
              {[portSat.source, portSat.target].map((side) =>
                (side.ports.length === 0 && side.has_assignment) ? null : (
                  <div key={side.entity_type} style={{ marginTop: 2 }}>
                    <span style={{ color: '#666' }}>
                      {side.entity_type.split(/[/#]/).pop()}
                    </span>
                    {!side.has_assignment && (
                      <div style={{ color: '#888', paddingLeft: 6 }}>
                        no assignment
                      </div>
                    )}
                    {side.ports.map((p) => {
                      const frag = (iri: string) =>
                        iri.split(/[/#]/).pop() ?? iri
                      const colour = p.status === 'satisfied'
                        ? '#2e7d32' : '#c62828'
                      return (
                        <div key={p.var} style={{ color: colour, paddingLeft: 6 }}>
                          {p.label || frag(p.var)}
                          {p.status === 'satisfied' &&
                            ` ← ${p.candidates.map(frag).join(', ')}`}
                          {p.status === 'ambiguous' &&
                            ` ? ${p.candidates.map(frag).join(', ')}`}
                          {p.status === 'unbound' &&
                            ` — no supply${p.state_hidden ? ' (state not exported)' : ''}`}
                          {p.status === 'unlicensed' && ' — not carried'}
                          {p.status === 'unreachable' && ' — one-way arc cannot feed source'}
                        </div>
                      )
                    })}
                  </div>
                ))}
            </div>
          )}
          {hoveredHighlight === 'invalid' && (
            <div style={{ fontSize: 11, color: '#c62828', borderTop: '1px solid #ccc', paddingTop: 8 }}>
              Connection not allowed
            </div>
          )}
          {/* Hover info (when nothing is selected) */}
          {!selectedVisibleNode && !selectedArc && hoveredObject && (
            <div style={{ fontSize: 11, borderTop: '1px solid #ccc', paddingTop: 8, color: '#555' }}>
              <strong style={{ fontSize: 12, color: '#333' }}>Hover</strong>
              {hoveredObject.kind === 'node' && (
                <>
                  <div>{hoveredObject.label}</div>
                  <div>Type: {hoveredObject.nodeType}</div>
                  {hoveredObject.entityType && <div>Entity: {hoveredObject.entityType}</div>}
                  {hoveredObject.modelNodeIri && <div>IRI: {hoveredObject.modelNodeIri}</div>}
                  <div>x: {hoveredObject.x.toFixed(1)}, y: {hoveredObject.y.toFixed(1)}</div>
                </>
              )}
              {hoveredObject.kind === 'arc' && (
                <>
                  <div>Arc: {hoveredObject.arcIri}</div>
                </>
              )}
              {hoveredObject.kind === 'knot' && (
                <>
                  <div>Knot #{hoveredObject.knotIndex}</div>
                  <div>Arc: {hoveredObject.arcIri}</div>
                  <div>x: {hoveredObject.x.toFixed(1)}, y: {hoveredObject.y.toFixed(1)}</div>
                </>
              )}
              {hoveredObject.kind === 'openArcHandle' && (
                <>
                  <div>Open arc handle</div>
                  <div>Arc: {hoveredObject.openArcIri}</div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* §20 model-level species aliases (only with a pinned artefact) */}
      {aliasDialogOpen && speciesDoc && (
        <SpeciesAliasDialog
          speciesDoc={speciesDoc}
          aliases={state.speciesAliases}
          dispatch={dispatch}
          onClose={() => setAliasDialogOpen(false)}
        />
      )}

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
          {hoveredHighlight === 'valid'
            ? `Valid target — right-click to connect (${validConnections.length} arc type${validConnections.length > 1 ? 's' : ''})`
            : hoveredHighlight === 'invalid'
              ? alreadyConnected
                ? 'Already connected with this arc type'
                : validConnections.length > 0
                  ? `Selected arc type not licensed — ${validConnections.length} other${validConnections.length > 1 ? 's' : ''} allowed`
                  : 'Invalid target — connection not allowed'
              : pendingConnection && !state.selectedVisibleNodeId
                ? `Source selected (${pendingConnection.sourceModelIri}) — navigate to target view, right-click a leaf to connect`
                : hoveredObject?.kind === 'knot'
                  ? 'Drag to move — double-click to add knot — right-click to remove'
                  : hoveredObject?.kind === 'arc'
                    ? 'Click to select — right-click to reverse flow direction — double-click to add knot — Delete to remove'
                    : hoveredObject?.kind === 'openArcHandle'
                      ? 'Drag to reconnect to a nearby node'
                      : hoveredObject?.kind === 'node' && !state.selectedVisibleNodeId
                        ? hoveredObject.nodeType === 'leaf'
                          ? 'Click to select — right-click to connect — drag to move'
                          : 'Click to open — Ctrl+click or right-click to select'
                        : state.selectedVisibleNodeId
                          ? 'Right-click a leaf to connect — click composite to open — Delete to remove'
                          : state.selectedModelArcIri
                            ? 'Delete to remove — drag knots to route — r or right-click to reverse flow direction'
                            : 'Click canvas to add node — click composite to open — Delete to remove'}
        </span>
        <span style={{ marginLeft: 'auto', color: '#555' }}>
          {state.modelNodes.size} model nodes, {state.modelArcs.size} arcs (next node: {state.tree.nextId + 1})
        </span>
      </div>
    </div>
  )
}
