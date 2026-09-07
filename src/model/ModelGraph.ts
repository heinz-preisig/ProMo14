import type { ModelNode, ModelArc, NodeType, ArcType } from '../types'

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

  /** Insert a model arc. */
  insertArc(iri: string, sourceIri: string, targetIri: string, arcType: ArcType): ModelArc {
    const arc: ModelArc = { iri, sourceIri, targetIri, arcType }
    this.arcs.set(iri, arc)
    this.arcCounter += 1
    return arc
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
