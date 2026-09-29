/** Short display form of an IRI: fragment after # or last /. */
export function frag(iri: string): string {
  const h = iri.split('#')
  if (h.length > 1) return h[h.length - 1]
  const s = iri.split('/')
  return s[s.length - 1]
}
