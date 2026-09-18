import type { Tree, ModelNode, ModelArc, NodeType, ArcType, OpenArc, Knot } from '../types'
import { createTree, TreeOps } from '../tree/Tree'
import { ModelGraphOps } from '../model/ModelGraph'

// ─── Unified application state ───
export interface AppState {
  modelNodes: Map<string, ModelNode>
  modelArcs: Map<string, ModelArc>
  tree: Tree
  layoutStore: Map<number, Map<string, { x: number; y: number }>>
  openArcs: Map<number, OpenArc[]> // keyed by composite tree node id
  knotStore: Map<number, Map<string, Knot[]>> // viewNodeId -> arc IRI -> knots (an arc renders differently per GraphView)
  currentViewNodeId: number
  selectedVisibleNodeId: string | null
  selectedModelArcIri: string | null
  arcCounter: number
}

export const initialState: AppState = {
  modelNodes: new Map(),
  modelArcs: new Map(),
  tree: createTree('Root'),
  layoutStore: new Map(),
  openArcs: new Map(),
  knotStore: new Map(),
  currentViewNodeId: 0,
  selectedVisibleNodeId: null,
  selectedModelArcIri: null,
  arcCounter: 1,
}

// ─── Commands (discriminated union) ───
export type Command =
  | { type: 'insertNode'; id: number; iri: string; label: string; entityType: NodeType; parentViewNodeId: number; x: number; y: number }
  | { type: 'deleteNode'; visibleNodeId: string; treeNodeId: number; modelNodeIri?: string }
  | { type: 'insertArc'; iri: string; sourceIri: string; targetIri: string; arcType: ArcType }
  | { type: 'deleteArc'; iri: string }
  | { type: 'moveNode'; viewNodeId: number; nodeId: string; x: number; y: number }
  | { type: 'setView'; viewNodeId: number }
  | { type: 'selectNode'; id: string | null }
  | { type: 'selectArc'; iri: string | null }
  | { type: 'groupNodes'; parentViewNodeId: number; treeNodeIds: number[] }
  | { type: 'reconnectOpenArc'; openArcIri: string; newModelNodeIri: string }
  | { type: 'moveKnot'; arcIri: string; knotIndex: number; x: number; y: number }
  | { type: 'addKnot'; arcIri: string; x: number; y: number }
  | { type: 'removeKnot'; arcIri: string; knotIndex: number }
  | { type: 'reset' }
  | { type: 'loadState'; state: AppState }

function findCompositeForOpenArc(openArcs: Map<number, OpenArc[]>, iri: string): number | undefined {
  for (const [compositeId, list] of openArcs) {
    if (list.some((a) => a.iri === iri)) return compositeId
  }
  return undefined
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
          openForView.push({
            iri: arc.iri,
            externalIri: isSource ? arc.targetIri : arc.sourceIri,
            arcType: arc.arcType,
            isSource,
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
        selectedModelArcIri: null,
      }
    }

    case 'deleteNode': {
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      if (cmd.modelNodeIri) {
        modelGraph.deleteNode(cmd.modelNodeIri)
      }

      const nextTree = new TreeOps(state.tree)
      nextTree.removeNode(cmd.treeNodeId)

      return {
        ...state,
        modelNodes: modelGraph.getNodes(),
        modelArcs: modelGraph.getArcs(),
        tree: nextTree.getState(),
        selectedVisibleNodeId: null,
        selectedModelArcIri: null,
      }
    }

    case 'insertArc': {
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      modelGraph.insertArc(cmd.iri, cmd.sourceIri, cmd.targetIri, cmd.arcType)

      return {
        ...state,
        modelNodes: modelGraph.getNodes(),
        modelArcs: modelGraph.getArcs(),
        arcCounter: modelGraph.getArcCounter(),
        selectedVisibleNodeId: null,
        selectedModelArcIri: cmd.iri,
      }
    }

    case 'deleteArc': {
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      modelGraph.deleteArc(cmd.iri)
      return {
        ...state,
        modelArcs: modelGraph.getArcs(),
        selectedModelArcIri: null,
        selectedVisibleNodeId: null,
      }
    }

    case 'moveNode': {
      const nextLayouts = new Map(state.layoutStore)
      const viewLayouts = new Map(nextLayouts.get(cmd.viewNodeId) ?? [])
      viewLayouts.set(cmd.nodeId, { x: cmd.x, y: cmd.y })
      nextLayouts.set(cmd.viewNodeId, viewLayouts)
      return { ...state, layoutStore: nextLayouts }
    }

    case 'setView':
      return {
        ...state,
        currentViewNodeId: cmd.viewNodeId,
        selectedVisibleNodeId: null,
        selectedModelArcIri: null,
      }

    case 'selectNode':
      return { ...state, selectedVisibleNodeId: cmd.id, selectedModelArcIri: null }

    case 'selectArc':
      return { ...state, selectedModelArcIri: cmd.iri, selectedVisibleNodeId: null }

    case 'groupNodes': {
      const nextTree = new TreeOps(state.tree)
      const compositeId = nextTree.addChild(cmd.parentViewNodeId, 'Group', undefined)
      for (const id of cmd.treeNodeIds) {
        nextTree.moveID(id, compositeId)
      }
      return { ...state, tree: nextTree.getState(), selectedVisibleNodeId: null }
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
      modelGraph.insertArc(openArc.iri, sourceIri, targetIri, openArc.arcType as ArcType)

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
