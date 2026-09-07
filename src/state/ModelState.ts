import type { Tree, ModelNode, ModelArc, NodeType, ArcType } from '../types'
import { createTree, TreeOps } from '../tree/Tree'
import { ModelGraphOps } from '../model/ModelGraph'

// ─── Unified application state ───
export interface AppState {
  modelNodes: Map<string, ModelNode>
  modelArcs: Map<string, ModelArc>
  tree: Tree
  layoutStore: Map<number, Map<string, { x: number; y: number }>>
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
  | { type: 'convertLeafToComposite'; treeNodeId: number; stageWidth: number; stageHeight: number }
  | { type: 'reset' }

// ─── Pure reducer ───
export function applyCommand(state: AppState, cmd: Command): AppState {
  switch (cmd.type) {
    case 'insertNode': {
      const modelGraph = new ModelGraphOps(state.modelNodes, state.modelArcs, state.arcCounter)
      modelGraph.insertNode(cmd.iri, cmd.entityType, cmd.label)

      const nextTree = new TreeOps(state.tree)
      nextTree.addChild(cmd.parentViewNodeId, cmd.label, cmd.iri, cmd.id)

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

    case 'convertLeafToComposite': {
      const nextTree = new TreeOps(state.tree)
      const node = state.tree.nodes.get(cmd.treeNodeId)
      if (!node || node.children.length > 0) return state

      const newChildId = nextTree.addChild(cmd.treeNodeId, 'Detail', undefined)
      const nextTreeState = nextTree.getState()

      const nextLayouts = new Map(state.layoutStore)
      const viewLayouts = new Map(nextLayouts.get(cmd.treeNodeId) ?? [])
      viewLayouts.set(String(newChildId), {
        x: cmd.stageWidth / 2,
        y: cmd.stageHeight / 2,
      })
      nextLayouts.set(cmd.treeNodeId, viewLayouts)

      return {
        ...state,
        tree: nextTreeState,
        layoutStore: nextLayouts,
        currentViewNodeId: cmd.treeNodeId,
        selectedVisibleNodeId: null,
        selectedModelArcIri: null,
      }
    }

    case 'reset':
      return { ...initialState }

    default:
      return state
  }
}
