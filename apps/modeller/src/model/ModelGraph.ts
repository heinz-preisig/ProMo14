import type { ModelNode, ModelArc, NodeType, ArcType } from '../types'

/** Carrier category from an arc-type IRI (``promo:ArcType/<carrier>``).
 *  Mirrors backend.instantiate.resolver.arc_carrier. */
export function arcCarrier(arcTypeIri: string | undefined): string | undefined {
  if (!arcTypeIri) return undefined
  const i = arcTypeIri.indexOf('ArcType/')
  if (i >= 0) return arcTypeIri.slice(i + 'ArcType/'.length)
  return arcTypeIri.split('#').pop()!.split('/').pop()
}

/** §15 default reference direction for a new arc.
 *
 *  Token-flow arcs get an explicit orientation; other carriers return
 *  ``undefined`` (their direction is inherent — output → input).
 *
 *  For an arc touching exactly one transport node T the default is the
 *  through-path: if T's existing arcs all point into T, the new arc
 *  points out (and vice versa); otherwise draw order.  Arcs with no
 *  transport end — or transports on both ends — follow draw order. */
export function defaultOrientation(
  arcType: ArcType,
  sourceIri: string,
  targetIri: string,
  sourceIsTransport: boolean,
  targetIsTransport: boolean,
  arcsOnTransport: ModelArc[],
): { referenceFrom: string; referenceTo: string } | undefined {
  if (arcCarrier(arcType) !== 'token-flow') return undefined

  const transport =
    sourceIsTransport && !targetIsTransport ? sourceIri
    : targetIsTransport && !sourceIsTransport ? targetIri
    : undefined
  if (!transport) return { referenceFrom: sourceIri, referenceTo: targetIri }

  const other = transport === sourceIri ? targetIri : sourceIri
  const ins = arcsOnTransport.filter(
    (a) => (a.referenceTo ?? a.targetIri) === transport).length
  const outs = arcsOnTransport.filter(
    (a) => (a.referenceFrom ?? a.sourceIri) === transport).length

  if (ins > 0 && outs === 0) return { referenceFrom: transport, referenceTo: other }
  if (outs > 0 && ins === 0) return { referenceFrom: other, referenceTo: transport }
  return { referenceFrom: sourceIri, referenceTo: targetIri }
}

/**
 * Immutable operations on the flat model graph (Layer 1).
 * Similar to TreeOps — wraps Maps with mutation helpers and returns fresh copies.
 */
export class ModelGraphOps {
  private nodes: Map<string, ModelNode>
  private arcs: Map<string, ModelArc>
  private arcCounter: number

  constructor(nodes: Map<string, ModelNode>, arcs: Map<string, ModelArc>, arcCounter: number) {
    this.nodes = new Map(nodes)
    this.arcs = new Map(arcs)
    this.arcCounter = arcCounter
  }

  getNodes(): Map<string, ModelNode> {
    return this.nodes
  }

  getArcs(): Map<string, ModelArc> {
    return this.arcs
  }

  getArcCounter(): number {
    return this.arcCounter
  }

  /** Insert a model node. Returns the new node. */
  insertNode(iri: string, entityType: NodeType, label: string): ModelNode {
    const node: ModelNode = { iri, entityType, label }
    this.nodes.set(iri, node)
    return node
  }

  /** Delete a model node and all connected arcs. Returns true if deleted. */
  deleteNode(iri: string): boolean {
    if (!this.nodes.has(iri)) return false
    this.nodes.delete(iri)

    // Remove connected arcs
    for (const [arcIri, arc] of this.arcs) {
      if (arc.sourceIri === iri || arc.targetIri === iri) {
        this.arcs.delete(arcIri)
      }
    }
    return true
  }

  /** Insert a model arc.  ``referenceFrom``/``referenceTo`` give the §15
   *  semantic reference direction (token-flow arcs); absent = draw order. */
  insertArc(
    iri: string,
    sourceIri: string,
    targetIri: string,
    arcType: ArcType,
    referenceFrom?: string,
    referenceTo?: string,
  ): ModelArc {
    const arc: ModelArc = { iri, sourceIri, targetIri, arcType }
    if (referenceFrom && referenceTo) {
      arc.referenceFrom = referenceFrom
      arc.referenceTo = referenceTo
    }
    this.arcs.set(iri, arc)
    this.arcCounter += 1
    return arc
  }

  /** Flip an arc's §15 reference direction (effective direction first,
   *  then swap — so reversing a draw-order arc stores the explicit
   *  reverse).  No-op for unknown arcs. */
  reverseArc(iri: string): void {
    const arc = this.arcs.get(iri)
    if (!arc) return
    const from = arc.referenceFrom ?? arc.sourceIri
    const to = arc.referenceTo ?? arc.targetIri
    this.arcs.set(iri, { ...arc, referenceFrom: to, referenceTo: from })
  }

  /** Delete a model arc. */
  deleteArc(iri: string): boolean {
    return this.arcs.delete(iri)
  }

  /** Generate a new arc IRI using the internal counter. */
  nextArcIri(prefix = 'promo:Arc/Arc_'): string {
    const iri = `${prefix}${this.arcCounter}`
    return iri
  }

  /** Get all arcs connected to a given node IRI. */
  getConnectedArcs(iri: string): ModelArc[] {
    const result: ModelArc[] = []
    for (const arc of this.arcs.values()) {
      if (arc.sourceIri === iri || arc.targetIri === iri) {
        result.push(arc)
      }
    }
    return result
  }

  /** Clone this ModelGraphOps with fresh copies. */
  clone(): ModelGraphOps {
    return new ModelGraphOps(this.nodes, this.arcs, this.arcCounter)
  }
}
