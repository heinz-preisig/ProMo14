import type { Tree, ModelNode, ModelArc, NodeType, ArcType, OpenArc, Knot, CompositeRef } from '../types'
import { modelNodeIri, modelArcIri, childIri } from '@promo/semantic'
import { createTree, TreeOps } from '../tree/Tree'
import { arcCarrier, ModelGraphOps } from '../model/ModelGraph'

// ─── Unified application state ───
export interface AppState {
  modelNodes: Map<string, ModelNode>
  modelArcs: Map<string, ModelArc>
  tree: Tree
  layoutStore: Map<number, Map<string, { x: number; y: number }>>
  openArcs: Map<number, OpenArc[]> // keyed by composite tree node id
  knotStore: Map<number, Map<string, Knot[]>> // viewNodeId -> arc IRI -> knots (an arc renders differently per GraphView)
  currentViewNodeId: number
  /** Primary selection — the last-selected node; single-node gestures
   *  (connection source, details panel) read this.  Equals the tail
   *  of ``selectedVisibleNodeIds``, or null when the set is empty. */
  selectedVisibleNodeId: string | null
  /** Multi-select set (ordered, primary last).  Group / delete /
   *  drag-move operate on the set. */
  selectedVisibleNodeIds: string[]
  selectedModelArcIri: string | null
  arcCounter: number
  /** §20 model-level species aliasing: Component IRI → local name
   *  ("A" :: "H2O").  The species artefact owns the vocabulary; the
   *  model owns its interpretation.  Persisted as promo:speciesAlias. */
  speciesAliases: Map<string, string>
  /** §20 species-artefact pin (promo:usesSpecies on the graph IRI) —
   *  which scheme this model draws its species vocabulary from. */
  speciesPin: string | null
  /** §22 referenced composites: composite tree id → refersTo +
   *  override map (content lives in the referenced artefact). */
  compositeRefs: Map<number, CompositeRef>
  /** §22 reference view — IRI of the referenced artefact whose tree
   *  `currentViewNodeId` indexes, or null when viewing the host doc.
   *  Everything drawn from `refStates` is read-only. */
  viewRefIri: string | null
  /** §22 referenced artefacts, deserialized for in-place rendering
   *  (usesModel closure — populated on load). */
  refStates: Map<string, RefViewState>
}

/** The per-doc maps `computeGraphView` needs to render a referenced
 *  artefact's content inside the host canvas (read-only scope). */
export type RefViewState = Pick<
  AppState,
  | 'tree' | 'modelNodes' | 'modelArcs' | 'layoutStore'
  | 'openArcs' | 'knotStore' | 'compositeRefs'
>

export const initialState: AppState = {
  modelNodes: new Map(),
  modelArcs: new Map(),
  tree: createTree('Root'),
  layoutStore: new Map(),
  openArcs: new Map(),
  knotStore: new Map(),
  currentViewNodeId: 0,
  selectedVisibleNodeId: null,
  selectedVisibleNodeIds: [],
  selectedModelArcIri: null,
  arcCounter: 1,
  speciesAliases: new Map(),
  speciesPin: null,
  compositeRefs: new Map(),
  viewRefIri: null,
  refStates: new Map(),
}

// ─── Commands (discriminated union) ───
export type Command =
  | { type: 'insertNode'; id: number; iri: string; label: string; entityType: NodeType; parentViewNodeId: number; x: number; y: number }
  | { type: 'deleteNode'; visibleNodeId: string; treeNodeId: number; modelNodeIri?: string }
  | { type: 'deleteNodes'; nodes: { visibleNodeId: string; treeNodeId: number; modelNodeIri?: string }[] }
  | { type: 'insertArc'; iri?: string; graphIri?: string; sourceIri: string; targetIri: string; arcType: ArcType; referenceFrom?: string; referenceTo?: string }
  | { type: 'deleteArc'; iri: string }
  | { type: 'reverseArcOrientation'; iri: string }
  | { type: 'moveNode'; viewNodeId: number; nodeId: string; x: number; y: number }
  | { type: 'moveNodes'; viewNodeId: number; moves: { nodeId: string; x: number; y: number }[] }
  | { type: 'setView'; viewNodeId: number; refIri?: string | null }
  | { type: 'setRefStates'; states: Map<string, RefViewState> }
  | { type: 'selectNode'; id: string | null }
  | { type: 'selectNodes'; ids: string[] }
  | { type: 'toggleSelectNode'; id: string }
  | { type: 'selectArc'; iri: string | null }
  | { type: 'groupNodes'; parentViewNodeId: number; treeNodeIds: number[]; label?: string }
  | { type: 'setNodeLabel'; treeNodeId: number; label: string }
  | { type: 'ungroup'; treeNodeId: number }
  | { type: 'reconnectOpenArc'; openArcIri: string; newModelNodeIri: string; arcType?: string }
  | { type: 'exposeTerminal'; iri: string; compositeId: number; modelNodeIri: string; entityType: string; phantomEntityType?: string; arcType?: string }
  | { type: 'unexposeTerminal'; compositeId: number; openArcIri: string }
  | { type: 'flipTerminalDirection'; compositeId: number; openArcIri: string }
  | { type: 'moveKnot'; arcIri: string; knotIndex: number; x: number; y: number }
  | { type: 'addKnot'; arcIri: string; x: number; y: number }
  | { type: 'removeKnot'; arcIri: string; knotIndex: number }
  | { type: 'setNodeSpecies'; iri: string; speciesAllocation?: string; reactions?: string[] }
  | { type: 'setArcPermeable'; iri: string; permeable?: string[] }
  | { type: 'setSpeciesAlias'; componentIri: string; alias: string }
  | { type: 'setSpeciesPin'; iri: string | null }
  | { type: 'toggleNodeFix'; iri: string; varIri: string }
  | { type: 'setCompositeRef'; treeNodeId: number; ref: CompositeRef | null }
  | { type: 'insertReferencedComposite'; id?: number; label: string; parentViewNodeId: number; x: number; y: number; refersTo: string; terminals: OpenArc[]; graphIri: string }
  | { type: 'insertStamped'; id?: number; label: string; parentViewNodeId: number; x: number; y: number; stamped: AppState; graphIri: string; sourceIri?: string }
  | { type: 'reset' }
  | { type: 'loadState'; state: AppState }

function findCompositeForOpenArc(openArcs: Map<number, OpenArc[]>, iri: string): number | undefined {
  for (const [compositeId, list] of openArcs) {
    if (list.some((a) => a.iri === iri)) return compositeId
  }
  return undefined
}

/** Drop open-arc entries failing `keep`; emptied lists go with them. */
function purgeOpenArcs(
  openArcs: Map<number, OpenArc[]>,
  keep: (a: OpenArc) => boolean,
): Map<number, OpenArc[]> {
  const next = new Map<number, OpenArc[]>()
  for (const [cid, list] of openArcs) {
    const kept = list.filter(keep)
    if (kept.length) next.set(cid, kept)
  }
  return next
}

/** §13: a cross-branch arc needs no record — the flat-arc
 *  projection (findVisibleId) renders it at every level in local
 *  terms: leaf→sibling-composite inside the branch, comp→comp at the
 *  parent.  The one case the projection cannot reach is a FOREIGN
 *  endpoint (a leaf inside a referenced artefact has no host tree
 *  node) — there the crossing is recorded as an open-arc stub on
 *  every composite along leaf→LCA on both sides, and the arc tags
 *  the ref shell via `via` so it dies with the occurrence.
 *  The shell resolves to the ref occurrence the view was in;
 *  several occurrences of one artefact share the refersTo → first
 *  match, same caveat as the back button. */
function boundaryStubs(
  state: AppState,
  arcIri: string,
  sourceIri: string,
  targetIri: string,
  arcType: string,
  referenceTo?: string,
): { openArcs: Map<number, OpenArc[]>; via: number } | null {
  const leafOf = (iri: string): number | null => {
    for (const [id, n] of state.tree.nodes)
      if (n.children.length === 0 && n.iri === iri) return id
    return null
  }
  const parentOf = (id: number | null): number | null =>
    id === null ? null : state.tree.nodes.get(id)?.parentId ?? null
  const refShellId = (): number | null => {
    if (!state.viewRefIri) return null
    for (const [id, r] of state.compositeRefs)
      if (r.refersTo === state.viewRefIri) return id
    return null
  }
  const srcLeaf = leafOf(sourceIri)
  const tgtLeaf = leafOf(targetIri)
  // Both endpoints in-doc — the projection renders the crossing
  // everywhere; nothing to record.
  if (srcLeaf !== null && tgtLeaf !== null) return null
  // Walk start: a host leaf starts at its parent composite; a
  // foreign endpoint starts AT the ref shell — its boundary is crossed.
  const srcStart = srcLeaf !== null ? parentOf(srcLeaf) : refShellId()
  const tgtStart = tgtLeaf !== null ? parentOf(tgtLeaf) : refShellId()
  if (srcStart === null || tgtStart === null) return null

  const srcAnc = new Set<number>()
  for (let c: number | null = srcStart; c !== null; c = parentOf(c)) srcAnc.add(c)
  let lca: number | null = null
  for (let c: number | null = tgtStart; c !== null; c = parentOf(c))
    if (srcAnc.has(c)) { lca = c; break }
  if (lca === null) return null

  const entityTypeOf = (iri: string) =>
    state.modelNodes.get(iri)?.entityType
    ?? (state.viewRefIri
        ? state.refStates.get(state.viewRefIri)?.modelNodes.get(iri)?.entityType
        : undefined)
  // refToExternal — does the reference direction point at the
  // external node (same convention as extract's host stubs).
  const refTo = referenceTo ?? targetIri
  const openArcs = new Map(state.openArcs)
  let touched = false
  const add = (comp: number, external: string, insideIsSource: boolean) => {
    const list = openArcs.get(comp) ?? []
    if (list.some((a) => a.iri === arcIri)) return
    openArcs.set(comp, [...list, {
      iri: arcIri,
      externalIri: external,
      arcType,
      isSource: insideIsSource,
      refToExternal: refTo === external,
      externalEntityType: entityTypeOf(external),
    }])
    touched = true
  }
  for (let c: number | null = srcStart; c !== null && c !== lca; c = parentOf(c))
    add(c, targetIri, true)
  for (let c: number | null = tgtStart; c !== null && c !== lca; c = parentOf(c))
    add(c, sourceIri, false)
  const via = refShellId()
  return touched && via !== null ? { openArcs, via } : null
}

// ─── Pure reducer ───
export function applyCommand(state: AppState, cmd: Command): AppState {
  switch (cmd.type) {
    case 'insertNode': {
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      modelGraph.insertNode(cmd.iri, cmd.entityType, cmd.label)

      const nextTree = new TreeOps(state.tree)
      const parent = nextTree.getState().nodes.get(cmd.parentViewNodeId)
      const oldParentIri = parent?.iri

      const openForView: OpenArc[] = []
      if (oldParentIri) {
        for (const arc of modelGraph.getConnectedArcs(oldParentIri)) {
          const isSource = arc.sourceIri === oldParentIri
          const externalIri = isSource ? arc.targetIri : arc.sourceIri
          // §15: preserve the reference direction across the boundary —
          // boundary-relative (toward the external node?) so it survives
          // the leaf→composite→leaf cycle.  Token-flow arcs only.
          const refToExternal = arcCarrier(arc.arcType) === 'token-flow'
            ? (arc.referenceTo ?? arc.targetIri) === externalIri
            : undefined
          openForView.push({
            iri: arc.iri,
            externalIri,
            arcType: arc.arcType,
            isSource,
            refToExternal,
          })
        }
        modelGraph.deleteNode(oldParentIri)
      }

      nextTree.addChild(cmd.parentViewNodeId, cmd.label, cmd.iri, cmd.id)
      if (parent) parent.iri = undefined

      const nextOpenArcs = new Map(state.openArcs)
      if (oldParentIri) nextOpenArcs.set(cmd.parentViewNodeId, openForView)

      const nextLayouts = new Map(state.layoutStore)
      const viewLayouts = new Map(nextLayouts.get(cmd.parentViewNodeId) ?? [])
      viewLayouts.set(String(cmd.id), { x: cmd.x, y: cmd.y })
      nextLayouts.set(cmd.parentViewNodeId, viewLayouts)

      return {
        ...state,
        modelNodes: modelGraph.getNodes(),
        modelArcs: modelGraph.getArcs(),
        tree: nextTree.getState(),
        layoutStore: nextLayouts,
        openArcs: nextOpenArcs,
        selectedVisibleNodeId: String(cmd.id),
        selectedVisibleNodeIds: [String(cmd.id)],
        selectedModelArcIri: null,
      }
    }

    case 'deleteNode':
      // Singular alias for the deleteNodes cascade — keeps composite
      // subtree semantics in one place.
      return applyCommand(state, {
        type: 'deleteNodes',
        nodes: [{
          visibleNodeId: cmd.visibleNodeId,
          treeNodeId: cmd.treeNodeId,
          modelNodeIri: cmd.modelNodeIri,
        }],
      })

    case 'deleteNodes': {
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      const nextTree = new TreeOps(state.tree)
      const compositeRefs = new Map(state.compositeRefs)
      const nextOpenArcs = new Map(state.openArcs)
      const nextLayouts = new Map(state.layoutStore)
      // Subtree cascade: a composite victim takes its descendants —
      // leaf model nodes, per-composite ref/terminal/layout state.
      const victimTreeIds = new Set<number>()
      for (const node of cmd.nodes) {
        victimTreeIds.add(node.treeNodeId)
        for (const id of nextTree.getDescendants(node.treeNodeId))
          victimTreeIds.add(id)
        for (const layouts of nextLayouts.values())
          layouts.delete(node.visibleNodeId)
      }
      // Fewest descendants first → parents empty before removal.
      const depth = new Map(
        [...victimTreeIds].map((id) => [id, nextTree.getDescendants(id).length]))
      const ordered = [...victimTreeIds]
        .sort((a, b) => depth.get(a)! - depth.get(b)!)
      const deadModelIris = new Set<string>()
      for (const id of ordered) {
        const iri = state.tree.nodes.get(id)?.iri
        if (iri && state.modelNodes.has(iri)) {
          modelGraph.deleteNode(iri)
          deadModelIris.add(iri)
        }
        nextTree.removeNode(id)
        compositeRefs.delete(id)
        nextOpenArcs.delete(id)
        nextLayouts.delete(id)
      }
      // Arcs bound through a removed composite's terminals die with it —
      // otherwise they keep foreign endpoints as ghosts.
      for (const arc of modelGraph.getArcs().values())
        if (arc.via !== undefined && victimTreeIds.has(arc.via))
          modelGraph.deleteArc(arc.iri)
      // Stubs declaring a deleted leaf or a dead arc would dangle —
      // drop them (cross-branch stubs record the arc's own iri).
      const deadArcIris = new Set(
        [...state.modelArcs.keys()].filter((a) => !modelGraph.getArcs().has(a)))
      for (const [cid, list] of nextOpenArcs) {
        const kept = list.filter((a) =>
          !deadModelIris.has(a.externalIri) && !deadArcIris.has(a.iri))
        if (kept.length !== list.length)
          if (kept.length) nextOpenArcs.set(cid, kept)
          else nextOpenArcs.delete(cid)
      }
      return {
        ...state,
        modelNodes: modelGraph.getNodes(),
        modelArcs: modelGraph.getArcs(),
        tree: nextTree.getState(),
        layoutStore: nextLayouts,
        compositeRefs,
        openArcs: nextOpenArcs,
        selectedVisibleNodeId: null,
        selectedVisibleNodeIds: [],
        selectedModelArcIri: null,
      }
    }

    case 'insertArc': {
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      // The IRI is minted here, not at dispatch time — async connect
      // resolutions can interleave and must not share a captured
      // counter.  Callers pass an explicit iri only when carrying a
      // template IRI (open-arc reconnect, stamped copies).
      const iri = cmd.iri ?? modelArcIri(cmd.graphIri!, modelGraph.getArcCounter())
      const arc = modelGraph.insertArc(iri, cmd.sourceIri, cmd.targetIri, cmd.arcType, cmd.referenceFrom, cmd.referenceTo)

      // §13: only a FOREIGN endpoint needs a record — stubs on the
      // crossed composites plus `via` on the arc (dies with the ref
      // occurrence).  In-doc crossings render via projection alone.
      const stub = boundaryStubs(
        state, iri, cmd.sourceIri, cmd.targetIri, cmd.arcType, cmd.referenceTo)
      if (stub) arc.via = stub.via

      return {
        ...state,
        modelNodes: modelGraph.getNodes(),
        modelArcs: modelGraph.getArcs(),
        openArcs: stub?.openArcs ?? state.openArcs,
        arcCounter: modelGraph.getArcCounter(),
        selectedVisibleNodeId: null,
        selectedVisibleNodeIds: [],
        selectedModelArcIri: iri,
      }
    }

    case 'exposeTerminal': {
      // §22/§33 authored interface: declaring a leaf as a terminal
      // appends an open-arc record on the leaf's owning composite.
      // The phantom peer (§33) names the imagined partner and the
      // caller derives the contract kind (arcType) from the pair's
      // connection rules; direction stays a flippable convention
      // (flipTerminalDirection), and reconnectOpenArc resolves what
      // remains undecided at bind time.  Idempotent per identical
      // contract — a leaf may host several terminals of different
      // kinds (§33: valve = two token-flow ports + one signal port).
      const candidate: OpenArc = {
        iri: cmd.iri,
        externalIri: cmd.modelNodeIri,
        arcType: cmd.arcType ?? '',
        isSource: false,
        externalEntityType: cmd.entityType,
        phantomEntityType: cmd.phantomEntityType,
      }
      const key = (a: OpenArc) =>
        `${a.externalIri}|${a.phantomEntityType ?? ''}|${a.arcType}|${a.refToExternal ?? ''}`
      const nextOpenArcs = new Map(state.openArcs)
      const list = nextOpenArcs.get(cmd.compositeId) ?? []
      if (list.some((a) => key(a) === key(candidate))) return state
      nextOpenArcs.set(cmd.compositeId, [...list, candidate])
      return { ...state, openArcs: nextOpenArcs, arcCounter: state.arcCounter + 1 }
    }

    case 'unexposeTerminal': {
      const list = state.openArcs.get(cmd.compositeId) ?? []
      const kept = list.filter((a) => a.iri !== cmd.openArcIri)
      if (kept.length === list.length) return state
      const nextOpenArcs = new Map(state.openArcs)
      if (kept.length) nextOpenArcs.set(cmd.compositeId, kept)
      else nextOpenArcs.delete(cmd.compositeId)
      return { ...state, openArcs: nextOpenArcs }
    }

    case 'flipTerminalDirection': {
      // §33: the reference direction is the one underivable bit of an
      // authored contract — a flippable convention (§15: any
      // assignment valid, existence is the only requirement).
      const list = state.openArcs.get(cmd.compositeId)
      if (!list?.some((a) => a.iri === cmd.openArcIri)) return state
      const nextOpenArcs = new Map(state.openArcs)
      nextOpenArcs.set(cmd.compositeId, list.map((a) =>
        a.iri === cmd.openArcIri
          ? { ...a, refToExternal: a.refToExternal === true ? false : true }
          : a))
      return { ...state, openArcs: nextOpenArcs }
    }

    case 'reverseArcOrientation': {
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      modelGraph.reverseArc(cmd.iri)
      return { ...state, modelArcs: modelGraph.getArcs() }
    }

    case 'deleteArc': {
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      modelGraph.deleteArc(cmd.iri)
      return {
        ...state,
        modelArcs: modelGraph.getArcs(),
        // Boundary stubs declaring the dead arc would dangle — drop.
        openArcs: purgeOpenArcs(state.openArcs, (a) => a.iri !== cmd.iri),
        selectedModelArcIri: null,
        selectedVisibleNodeId: null,
        selectedVisibleNodeIds: [],
      }
    }

    case 'moveNode': {
      const nextLayouts = new Map(state.layoutStore)
      const viewLayouts = new Map(nextLayouts.get(cmd.viewNodeId) ?? [])
      viewLayouts.set(cmd.nodeId, { x: cmd.x, y: cmd.y })
      nextLayouts.set(cmd.viewNodeId, viewLayouts)
      return { ...state, layoutStore: nextLayouts }
    }

    case 'moveNodes': {
      const nextLayouts = new Map(state.layoutStore)
      const viewLayouts = new Map(nextLayouts.get(cmd.viewNodeId) ?? [])
      for (const m of cmd.moves) viewLayouts.set(m.nodeId, { x: m.x, y: m.y })
      nextLayouts.set(cmd.viewNodeId, viewLayouts)
      return { ...state, layoutStore: nextLayouts }
    }

    case 'setView':
      return {
        ...state,
        currentViewNodeId: cmd.viewNodeId,
        viewRefIri: cmd.refIri !== undefined ? cmd.refIri : state.viewRefIri,
        selectedVisibleNodeId: null,
        selectedVisibleNodeIds: [],
        selectedModelArcIri: null,
      }

    case 'setRefStates':
      return { ...state, refStates: cmd.states }

    case 'selectNode':
      return {
        ...state,
        selectedVisibleNodeId: cmd.id,
        selectedVisibleNodeIds: cmd.id ? [cmd.id] : [],
        selectedModelArcIri: null,
      }

    case 'selectNodes': {
      const ids = [...new Set(cmd.ids)]
      return {
        ...state,
        selectedVisibleNodeIds: ids,
        selectedVisibleNodeId: ids.length ? ids[ids.length - 1] : null,
        selectedModelArcIri: null,
      }
    }

    case 'toggleSelectNode': {
      const has = state.selectedVisibleNodeIds.includes(cmd.id)
      const ids = has
        ? state.selectedVisibleNodeIds.filter((i) => i !== cmd.id)
        : [...state.selectedVisibleNodeIds, cmd.id]
      return {
        ...state,
        selectedVisibleNodeIds: ids,
        selectedVisibleNodeId: ids.length ? ids[ids.length - 1] : null,
        selectedModelArcIri: null,
      }
    }

    case 'selectArc':
      return {
        ...state,
        selectedModelArcIri: cmd.iri,
        selectedVisibleNodeId: null,
        selectedVisibleNodeIds: [],
      }

    case 'setNodeSpecies': {
      const modelNodes = new Map(state.modelNodes)
      const n = modelNodes.get(cmd.iri)
      if (n) {
        modelNodes.set(cmd.iri, {
          ...n,
          speciesAllocation: cmd.speciesAllocation,
          reactions: cmd.reactions,
        })
      }
      return { ...state, modelNodes }
    }

    case 'setArcPermeable': {
      const modelArcs = new Map(state.modelArcs)
      const a = modelArcs.get(cmd.iri)
      if (a) modelArcs.set(cmd.iri, { ...a, permeable: cmd.permeable })
      return { ...state, modelArcs }
    }

    case 'setSpeciesAlias': {
      const speciesAliases = new Map(state.speciesAliases)
      const alias = cmd.alias.trim()
      if (alias) speciesAliases.set(cmd.componentIri, alias)
      else speciesAliases.delete(cmd.componentIri)
      return { ...state, speciesAliases }
    }

    case 'setSpeciesPin':
      return { ...state, speciesPin: cmd.iri }

    case 'toggleNodeFix': {
      const modelNodes = new Map(state.modelNodes)
      const n = modelNodes.get(cmd.iri)
      if (n) {
        const fixes = new Set(n.fixes ?? [])
        if (fixes.has(cmd.varIri)) fixes.delete(cmd.varIri)
        else fixes.add(cmd.varIri)
        modelNodes.set(cmd.iri, { ...n, fixes: [...fixes] })
      }
      return { ...state, modelNodes }
    }

    case 'setCompositeRef': {
      const compositeRefs = new Map(state.compositeRefs)
      if (cmd.ref) compositeRefs.set(cmd.treeNodeId, cmd.ref)
      else compositeRefs.delete(cmd.treeNodeId)
      return { ...state, compositeRefs }
    }

    case 'insertReferencedComposite': {
      // §22 library pick: a composite occurrence referring to another
      // model artefact.  Its declared interface (the artefact's open
      // arcs, copied verbatim — externalIri is the submodel-internal
      // endpoint, which never resolves in this tree → renders as a
      // terminal stub) becomes its connectable terminals.
      // The id is allocated HERE — the artefact doc fetch is async
      // and a second palette insert could interleave on a stale
      // nextId captured at click time.
      const id = cmd.id ?? state.tree.nextId + 1
      const nextTree = new TreeOps(state.tree)
      nextTree.addChild(cmd.parentViewNodeId, cmd.label, undefined, id)

      const compositeRefs = new Map(state.compositeRefs)
      compositeRefs.set(id, { refersTo: cmd.refersTo, overrides: {} })

      // Occurrence-scoped terminal IRIs ({comp}/{template arc}) —
      // the artefact's own arc IRIs would collide across two
      // occurrences of the same artefact, and reconnectOpenArc
      // binds the ModelArc under this name.
      const compIri = childIri(cmd.graphIri, `Composite_${id}`)
      const nextOpenArcs = new Map(state.openArcs)
      if (cmd.terminals.length) nextOpenArcs.set(id, cmd.terminals.map((t) => ({
        ...t, iri: `${compIri}/${t.iri}`,
      })))

      const nextLayouts = new Map(state.layoutStore)
      const viewLayouts = new Map(nextLayouts.get(cmd.parentViewNodeId) ?? [])
      viewLayouts.set(String(id), { x: cmd.x, y: cmd.y })
      nextLayouts.set(cmd.parentViewNodeId, viewLayouts)

      return {
        ...state,
        tree: nextTree.getState(),
        compositeRefs,
        openArcs: nextOpenArcs,
        layoutStore: nextLayouts,
        selectedVisibleNodeId: String(id),
        selectedVisibleNodeIds: [String(id)],
        selectedModelArcIri: null,
      }
    }

    case 'insertStamped': {
      // Stamp semantics: deep-copy the artefact's subtree into the
      // host — fresh tree ids and fresh {graph}/Node_{id} leaf IRIs
      // per insert.  The copy is ordinary host content: connectable
      // by plain arcs, deletable, editable.  Its open arcs persist
      // as host open arcs (§33: they may even become the host's own
      // interface later); dissolvedFrom records provenance on the
      // wrapper composite and dies if it is ungrouped.
      const stamped = cmd.stamped
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      const nextTree = new TreeOps(state.tree)
      const compositeRefs = new Map(state.compositeRefs)
      const nextOpenArcs = new Map(state.openArcs)
      const nextLayouts = new Map(state.layoutStore)
      const nextKnots = new Map(state.knotStore)
      const speciesAliases = new Map(state.speciesAliases)

      // Same async-interleave rule as insertReferencedComposite —
      // the wrapper id is allocated on the fresh state, not the
      // click-time capture.
      const id = cmd.id ?? state.tree.nextId + 1
      nextTree.addChild(cmd.parentViewNodeId, cmd.label, undefined, id)
      const viewLayouts = new Map(nextLayouts.get(cmd.parentViewNodeId) ?? [])
      viewLayouts.set(String(id), { x: cmd.x, y: cmd.y })
      nextLayouts.set(cmd.parentViewNodeId, viewLayouts)
      // §33 provenance: the wrapper remembers its template — a
      // reference-free CompositeRef (refersTo: '') so ungrouping the
      // copy drops the record with the group.
      if (cmd.sourceIri) {
        compositeRefs.set(id, { refersTo: '', overrides: {}, dissolvedFrom: cmd.sourceIri })
      }

      // Pass 1 — BFS: allocate fresh tree ids for the stamped subtree.
      const idMap = new Map<number, number>()
      const order: Array<{ oldId: number; newId: number; parent: number }> = []
      const queue: Array<{ oldId: number; parent: number }> =
        (stamped.tree.nodes.get(stamped.tree.rootId)?.children ?? [])
          .map((oldId) => ({ oldId, parent: id }))
      let alloc = id
      while (queue.length) {
        const { oldId, parent } = queue.shift()!
        const newId = ++alloc
        idMap.set(oldId, newId)
        order.push({ oldId, newId, parent })
        for (const ch of stamped.tree.nodes.get(oldId)?.children ?? [])
          queue.push({ oldId: ch, parent: newId })
      }

      // Pass 2 — rebuild the subtree; fresh leaf IRIs keyed to new ids.
      const iriMap = new Map<string, string>()
      for (const { oldId, newId, parent } of order) {
        const old = stamped.tree.nodes.get(oldId)!
        const freshIri = old.iri ? modelNodeIri(cmd.graphIri, newId) : undefined
        if (old.iri) iriMap.set(old.iri, freshIri!)
        nextTree.addChild(parent, old.label, freshIri, newId)
        const mn = old.iri ? stamped.modelNodes.get(old.iri) : undefined
        if (mn && freshIri) {
          const node = modelGraph.insertNode(freshIri, mn.entityType, mn.label)
          node.speciesAllocation = mn.speciesAllocation
          node.reactions = mn.reactions
          node.fixes = mn.fixes
        }
      }

      // Pass 3 — internal arcs, remapped endpoints, fresh arc IRIs.
      const arcIriMap = new Map<string, string>()
      for (const arc of stamped.modelArcs.values()) {
        const source = iriMap.get(arc.sourceIri)
        const target = iriMap.get(arc.targetIri)
        if (!source || !target) continue
        const freshArc = modelArcIri(cmd.graphIri, modelGraph.getArcCounter())
        const a = modelGraph.insertArc(
          freshArc, source, target, arc.arcType,
          arc.referenceFrom ? iriMap.get(arc.referenceFrom) ?? arc.referenceFrom : undefined,
          arc.referenceTo ? iriMap.get(arc.referenceTo) ?? arc.referenceTo : undefined)
        a.permeable = arc.permeable
        arcIriMap.set(arc.iri, freshArc)
      }

      // Pass 4 — per-composite bookkeeping follows the id remap.
      for (const [oldId, newId] of idMap) {
        const ref = stamped.compositeRefs.get(oldId)
        if (ref) compositeRefs.set(newId, {
          refersTo: ref.refersTo,
          overrides: { ...ref.overrides },
          dissolvedFrom: ref.dissolvedFrom,
        })
        const oa = stamped.openArcs.get(oldId)
        // Every copied open arc needs a fresh host IRI — the
        // template's own would collide on a second stamp, and
        // reconnectOpenArc binds the ModelArc under this name.
        if (oa) nextOpenArcs.set(newId, oa.map((a) => ({
          ...a,
          iri: arcIriMap.get(a.iri) ?? modelGraph.mintArcIri(cmd.graphIri),
          externalIri: iriMap.get(a.externalIri) ?? a.externalIri,
        })))
        const lay = stamped.layoutStore.get(oldId)
        if (lay) nextLayouts.set(newId, new Map(
          [...lay].map(([vid, p]) => [String(idMap.get(Number(vid)) ?? vid), p])))
        const knots = stamped.knotStore.get(oldId)
        if (knots) nextKnots.set(newId, new Map(
          [...knots].map(([airi, ks]) => [arcIriMap.get(airi) ?? airi, ks])))
      }
      // The stamped root's own view bookkeeping maps onto the wrapper —
      // without it the copy's children lose their template positions.
      const rootLay = stamped.layoutStore.get(stamped.tree.rootId)
      if (rootLay) nextLayouts.set(id, new Map(
        [...rootLay].map(([vid, p]) => [String(idMap.get(Number(vid)) ?? vid), p])))
      const rootKnots = stamped.knotStore.get(stamped.tree.rootId)
      if (rootKnots) nextKnots.set(id, new Map(
        [...rootKnots].map(([airi, ks]) => [arcIriMap.get(airi) ?? airi, ks])))
      for (const [k, v] of stamped.speciesAliases)
        if (!speciesAliases.has(k)) speciesAliases.set(k, v)

      return {
        ...state,
        modelNodes: modelGraph.getNodes(),
        modelArcs: modelGraph.getArcs(),
        tree: nextTree.getState(),
        layoutStore: nextLayouts,
        openArcs: nextOpenArcs,
        knotStore: nextKnots,
        compositeRefs,
        speciesAliases,
        speciesPin: state.speciesPin ?? stamped.speciesPin,
        arcCounter: modelGraph.getArcCounter(),
        selectedVisibleNodeId: String(id),
        selectedVisibleNodeIds: [String(id)],
        selectedModelArcIri: null,
      }
    }

    case 'groupNodes': {
      const nextTree = new TreeOps(state.tree)
      const compositeId = nextTree.addChild(cmd.parentViewNodeId, cmd.label ?? 'Group', undefined)
      for (const id of cmd.treeNodeIds) {
        nextTree.moveID(id, compositeId)
      }
      return {
        ...state,
        tree: nextTree.getState(),
        selectedVisibleNodeId: null,
        selectedVisibleNodeIds: [],
      }
    }

    case 'setNodeLabel': {
      const nextTree = new TreeOps(state.tree)
      nextTree.setLabel(cmd.treeNodeId, cmd.label)
      const tree = nextTree.getState()
      // Leaf labels persist via the ModelNode — keep the copies in sync.
      const iri = tree.nodes.get(cmd.treeNodeId)?.iri
      const modelNodes = iri !== undefined && state.modelNodes.has(iri)
        ? new Map(state.modelNodes).set(iri, { ...state.modelNodes.get(iri)!, label: cmd.label })
        : state.modelNodes
      return { ...state, tree, modelNodes }
    }

    case 'ungroup': {
      const comp = state.tree.nodes.get(cmd.treeNodeId)
      // Only an in-doc composite (no leaf iri, not root); referenced
      // composites go through Dissolve instead.
      if (!comp || comp.parentId === null || comp.iri !== undefined) return state
      const nextTree = new TreeOps(state.tree)
      nextTree.ungroup(cmd.treeNodeId)
      // Drop every store entry keyed by the vanished composite id.
      const openArcs = new Map(state.openArcs); openArcs.delete(cmd.treeNodeId)
      const compositeRefs = new Map(state.compositeRefs); compositeRefs.delete(cmd.treeNodeId)
      const layoutStore = new Map(state.layoutStore); layoutStore.delete(cmd.treeNodeId)
      const knotStore = new Map(state.knotStore); knotStore.delete(cmd.treeNodeId)
      return {
        ...state,
        tree: nextTree.getState(),
        openArcs, compositeRefs, layoutStore, knotStore,
        selectedVisibleNodeId: null,
        selectedVisibleNodeIds: [],
      }
    }

    case 'reconnectOpenArc': {
      const compositeId = findCompositeForOpenArc(state.openArcs, cmd.openArcIri)
      if (!compositeId) return state
      const openForView = state.openArcs.get(compositeId)!
      const openArc = openForView.find((a) => a.iri === cmd.openArcIri)
      if (!openArc) return state
      if (!state.modelNodes.has(cmd.newModelNodeIri)) return state

      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      const sourceIri = openArc.isSource ? cmd.newModelNodeIri : openArc.externalIri
      const targetIri = openArc.isSource ? openArc.externalIri : cmd.newModelNodeIri
      // §15: restore the preserved reference direction — refToExternal
      // says whether positive flow points at the external node.
      const referenceFrom = openArc.refToExternal === undefined
        ? undefined
        : openArc.refToExternal ? cmd.newModelNodeIri : openArc.externalIri
      const referenceTo = openArc.refToExternal === undefined
        ? undefined
        : openArc.refToExternal ? openArc.externalIri : cmd.newModelNodeIri
      const boundArc = modelGraph.insertArc(
        openArc.iri, sourceIri, targetIri,
        (cmd.arcType || openArc.arcType) as ArcType, referenceFrom, referenceTo)
      boundArc.via = compositeId

      const nextOpenArcs = new Map(state.openArcs)
      const remaining = openForView.filter((a) => a.iri !== cmd.openArcIri)
      if (remaining.length > 0) nextOpenArcs.set(compositeId, remaining)
      else nextOpenArcs.delete(compositeId)

      return {
        ...state,
        modelNodes: modelGraph.getNodes(),
        modelArcs: modelGraph.getArcs(),
        arcCounter: modelGraph.getArcCounter(),
        openArcs: nextOpenArcs,
        selectedVisibleNodeId: null,
        selectedVisibleNodeIds: [],
        selectedModelArcIri: openArc.iri,
      }
    }

    case 'moveKnot': {
      const viewKnots = state.knotStore.get(state.currentViewNodeId)
      const knots = viewKnots?.get(cmd.arcIri)
      if (!knots || cmd.knotIndex < 0 || cmd.knotIndex >= knots.length) return state
      const nextKnots = knots.map((k, i) => i === cmd.knotIndex ? { x: cmd.x, y: cmd.y } : k)
      const nextViewKnots = new Map(viewKnots)
      nextViewKnots.set(cmd.arcIri, nextKnots)
      const nextKnotStore = new Map(state.knotStore)
      nextKnotStore.set(state.currentViewNodeId, nextViewKnots)
      return { ...state, knotStore: nextKnotStore }
    }

    case 'addKnot': {
      const viewKnots = state.knotStore.get(state.currentViewNodeId)
      const knots = viewKnots?.get(cmd.arcIri) ?? []
      const nextKnots = [...knots, { x: cmd.x, y: cmd.y }]
      const nextViewKnots = new Map(viewKnots)
      nextViewKnots.set(cmd.arcIri, nextKnots)
      const nextKnotStore = new Map(state.knotStore)
      nextKnotStore.set(state.currentViewNodeId, nextViewKnots)
      return { ...state, knotStore: nextKnotStore }
    }

    case 'removeKnot': {
      const viewKnots = state.knotStore.get(state.currentViewNodeId)
      const knots = viewKnots?.get(cmd.arcIri)
      if (!knots || cmd.knotIndex < 0 || cmd.knotIndex >= knots.length) return state
      const nextKnots = knots.filter((_, i) => i !== cmd.knotIndex)
      const nextViewKnots = new Map(viewKnots)
      if (nextKnots.length > 0) nextViewKnots.set(cmd.arcIri, nextKnots)
      else nextViewKnots.delete(cmd.arcIri)
      const nextKnotStore = new Map(state.knotStore)
      nextKnotStore.set(state.currentViewNodeId, nextViewKnots)
      return { ...state, knotStore: nextKnotStore }
    }

    case 'reset':
      return { ...initialState }

    case 'loadState':
      return cmd.state

    default:
      return state
  }
}
