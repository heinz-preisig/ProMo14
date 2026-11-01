/**
 * §26 instance-IRI shapes — the TypeScript side of the single
 * contract (mirror of ``backend/core/iri.py``).
 *
 * The server owns minting for anything it writes: variables are sent
 * with an empty ``iri`` and get ``{graph}#{internal_id}`` back.  The shapes
 * below are the ones clients mint themselves — whole-document
 * topology IDs the server validates but never re-mints — plus the
 * synthesised ``promo#ArcType/<carrier>`` read shape.
 */

export const VOCAB_NS = 'https://w3id.org/promo#'

/** ``{base}/{segment}`` — a resource subordinate to ``base``.
 *  Artefact graph IRIs are slash-free names, so ``{graph}/x`` yields
 *  a uniform path for every member. */
export const childIri = (base: string, segment: string): string =>
  `${base.replace(/\/+$/, '')}/${segment}`

/** ``{graph}/Node_{id}`` — a model node's IRI. */
export const modelNodeIri = (graph: string, id: number | string): string =>
  childIri(graph, `Node_${id}`)

/** ``{graph}/Arc_{counter}`` — a model arc's IRI. */
export const modelArcIri = (graph: string, counter: number | string): string =>
  childIri(graph, `Arc_${counter}`)

/**
 * ``{graph}/{kind}_{stamp}`` — a species-artefact member
 * (Component / Allocation / Reaction).
 */
export const speciesMemberIri = (
  graph: string | undefined,
  kind: string,
  stamp: string = Date.now().toString(36),
): string => childIri(graph ?? 'species', `${kind}_${stamp}`)

/**
 * ``promo#ArcType/<carrier>`` — synthesised, never a stored subject.
 * Prefer the server's ``arc_type_iri`` field on rule records; this is
 * the offline/fallback form only.
 */
export const arcTypeIri = (carrier: string | null | undefined): string =>
  `${VOCAB_NS}ArcType/${carrier ?? 'generic'}`

/**
 * Carrier category from an arc-type IRI — the inverse of
 * {@link arcTypeIri}.  Mirrors
 * ``backend.instantiate.resolver.arc_carrier``.
 */
export const arcTypeCarrier = (iri: string | undefined): string | undefined => {
  if (!iri) return undefined
  const i = iri.indexOf('ArcType/')
  if (i >= 0) return iri.slice(i + 'ArcType/'.length)
  return iri.split('#').pop()?.split('/').pop() ?? iri
}

/** The trailing fragment of any IRI shape — after ``#`` or ``/``. */
export const localName = (iri: string): string =>
  iri.split('#').pop()?.split('/').pop() ?? iri
