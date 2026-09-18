// ---------------------------------------------------------------------------
// Model persistence — serialize/deserialize AppState <-> ModelDocument
// (ADR-007: the artefact graph is one model document; GET/PUT /api/modeller/model)
// ---------------------------------------------------------------------------

import type { AppState } from './state/ModelState'
import type { Knot, ModelArc, ModelNode, OpenArc, Tree, TreeNode } from './types'

export interface ModelNodeDoc {
  iri: string
  entityType: string
  label: string
}

export interface ModelArcDoc {
  iri: string
  sourceIri: string
  targetIri: string
  arcType: string
}

export interface ChildDoc {
  id: number
  iri?: string
}

export interface CompositeDoc {
  treeId: number
  label: string
  parentTreeId: number | null
  children: ChildDoc[]
  layout: Record<string, { x: number; y: number }>
  /** Per-view arc routing: arc IRI -> knots (an arc renders differently
   *  on each GraphView, so knots are keyed by view, not by arc). */
  knots: Record<string, Knot[]>
  openArcs: OpenArc[]
}

export interface ModelDocument {
  nodes: ModelNodeDoc[]
  arcs: ModelArcDoc[]
  composites: CompositeDoc[]
  rootTreeId: number
  nextTreeId: number
  arcCounter: number
}

export function serializeState(state: AppState): ModelDocument {
  const nodes: ModelNodeDoc[] = [...state.modelNodes.values()].map((n) => ({
    iri: n.iri,
    entityType: n.entityType,
    label: n.label,
  }))

  const arcs: ModelArcDoc[] = [...state.modelArcs.values()].map((a) => ({
    iri: a.iri,
    sourceIri: a.sourceIri,
    targetIri: a.targetIri,
    arcType: a.arcType,
  }))

  const composites: CompositeDoc[] = [...state.tree.nodes.values()]
    .filter((n) => n.iri === undefined)
    .map((n) => ({
      treeId: n.id,
      label: n.label,
      parentTreeId: n.parentId,
      children: n.children.map((cid) => {
        const child = state.tree.nodes.get(cid)
        return child?.iri ? { id: cid, iri: child.iri } : { id: cid }
      }),
      layout: Object.fromEntries(state.layoutStore.get(n.id) ?? []),
      knots: Object.fromEntries(state.knotStore.get(n.id) ?? []),
      openArcs: state.openArcs.get(n.id) ?? [],
    }))

  return {
    nodes,
    arcs,
    composites,
    rootTreeId: state.tree.rootId,
    nextTreeId: state.tree.nextId,
    arcCounter: state.arcCounter,
  }
}

export function deserializeState(doc: ModelDocument): AppState {
  const modelNodes = new Map<string, ModelNode>(
    doc.nodes.map((n) => [n.iri, { iri: n.iri, entityType: n.entityType, label: n.label }]),
  )
  const modelArcs = new Map<string, ModelArc>(
    doc.arcs.map((a) => [
      a.iri,
      { iri: a.iri, sourceIri: a.sourceIri, targetIri: a.targetIri, arcType: a.arcType },
    ]),
  )
  const knotStore = new Map<number, Map<string, Knot[]>>(
    doc.composites.map((c) => [c.treeId, new Map(Object.entries(c.knots))]),
  )

  const treeNodes = new Map<number, TreeNode>()
  for (const c of doc.composites) {
    treeNodes.set(c.treeId, {
      id: c.treeId,
      parentId: c.parentTreeId,
      children: c.children.map((ch) => ch.id),
      label: c.label,
    })
    for (const ch of c.children) {
      if (ch.iri) {
        treeNodes.set(ch.id, {
          id: ch.id,
          parentId: c.treeId,
          children: [],
          label: modelNodes.get(ch.iri)?.label ?? ch.iri,
          iri: ch.iri,
        })
      }
    }
  }
  const tree: Tree = { rootId: doc.rootTreeId, nodes: treeNodes, nextId: doc.nextTreeId }

  const layoutStore = new Map<number, Map<string, { x: number; y: number }>>(
    doc.composites.map((c) => [c.treeId, new Map(Object.entries(c.layout))]),
  )
  const openArcs = new Map<number, OpenArc[]>(
    doc.composites.filter((c) => c.openArcs.length > 0).map((c) => [c.treeId, c.openArcs]),
  )

  return {
    modelNodes,
    modelArcs,
    tree,
    layoutStore,
    openArcs,
    knotStore,
    currentViewNodeId: doc.rootTreeId,
    selectedVisibleNodeId: null,
    selectedModelArcIri: null,
    arcCounter: doc.arcCounter,
  }
}

/** True when the document carries actual content (not an empty artefact). */
export function hasContent(doc: ModelDocument): boolean {
  return doc.nodes.length > 0 || doc.arcs.length > 0 || doc.composites.length > 1
}
