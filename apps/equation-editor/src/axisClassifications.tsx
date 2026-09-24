/** Multi-axis variable classification — one dropdown per applicable
 *  axis (determination / function / variability / role …).
 *
 *  A variable's ``network`` is a domain *name*; axes bind to domain
 *  IRIs and inherit down the domain tree, so applicability is resolved
 *  via the domain records' parent chain.
 */
import type { AxisTerm, ClassificationAxis, Domain } from './types'

/** Domain IRIs applicable to a variable in network ``domainName``:
 *  the domain itself plus every ancestor.  Unknown names yield the
 *  empty set — callers then show every axis rather than none. */
export function applicableDomainIris(
  domainName: string,
  domains: Domain[],
): Set<string> {
  const byName = new Map(domains.map((d) => [d.name, d]))
  const byIri = new Map(domains.map((d) => [d.iri, d]))
  const out = new Set<string>()
  let cur = byName.get(domainName)
  while (cur) {
    if (out.has(cur.iri)) break
    out.add(cur.iri)
    cur = cur.parent ? byIri.get(cur.parent) : undefined
  }
  return out
}

/** Axes whose bound domain is the variable's domain or an ancestor.
 *  Falls back to all axes when the domain can't be resolved. */
export function applicableAxes(
  axes: ClassificationAxis[],
  domainName: string,
  domains: Domain[],
): ClassificationAxis[] {
  const iris = applicableDomainIris(domainName, domains)
  const hit = axes.filter((a) => iris.has(a.domain))
  return hit.length ? hit : axes
}

/** Terms flattened roots-first, children indented under their parent. */
function orderedTerms(axis: ClassificationAxis): { term: AxisTerm; depth: number }[] {
  const byParent = new Map<string, AxisTerm[]>()
  const termIris = new Set(axis.terms.map((t) => t.iri))
  for (const t of axis.terms) {
    // A parent outside this axis (shouldn't happen) renders as a root.
    const p = t.parent && termIris.has(t.parent) ? t.parent : ''
    byParent.set(p, [...(byParent.get(p) ?? []), t])
  }
  const out: { term: AxisTerm; depth: number }[] = []
  const walk = (parent: string, depth: number) => {
    for (const t of byParent.get(parent) ?? []) {
      out.push({ term: t, depth })
      walk(t.iri, depth + 1)
    }
  }
  walk('', 0)
  return out
}

/** Derive the legacy variableClass from a classifications map — the
 *  backend applies the same rule on save (a term labelled
 *  constant|parameter wins; classified-but-neither means "state"). */
export function deriveType(
  axes: ClassificationAxis[],
  classifications: Record<string, string>,
): string {
  const labelOf = new Map<string, string>()
  for (const a of axes) for (const t of a.terms) labelOf.set(t.iri, t.label)
  for (const termIri of Object.values(classifications)) {
    const label = labelOf.get(termIri)
    if (label === 'constant' || label === 'parameter') return label
  }
  return Object.keys(classifications).length ? 'state' : ''
}

/** IRI of the term labelled ``label`` on the axis named ``axisName`` —
 *  used to pre-fill picks (e.g. determination=port on port variables). */
export function findTermIri(
  axes: ClassificationAxis[],
  axisName: string,
  label: string,
): { axisIri: string; termIri: string } | null {
  for (const a of axes) {
    if (a.name !== axisName) continue
    const t = a.terms.find((x) => x.label === label)
    if (t) return { axisIri: a.iri, termIri: t.iri }
  }
  return null
}

export interface AxisClassificationsProps {
  axes: ClassificationAxis[]
  /** Variable's network (domain name) — filters applicable axes. */
  domain: string
  domains: Domain[]
  value: Record<string, string>
  onChange: (next: Record<string, string>) => void
  disabled?: boolean
}

/** One select per applicable axis; each option is an axis term. */
export default function AxisClassifications({
  axes,
  domain,
  domains,
  value,
  onChange,
  disabled,
}: AxisClassificationsProps) {
  const applicable = applicableAxes(axes, domain, domains)
  if (!applicable.length) return null
  return (
    <>
      {applicable.map((axis) => (
        <label
          key={axis.iri}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          title={disabled ? 'Locked — variable is referenced by equations' : axis.iri}
        >
          {axis.name}:
          <select
            value={value[axis.iri] ?? ''}
            disabled={disabled}
            onChange={(e) => {
              const next = { ...value }
              if (e.target.value) next[axis.iri] = e.target.value
              else delete next[axis.iri]
              onChange(next)
            }}
          >
            <option value="">—</option>
            {orderedTerms(axis).map(({ term, depth }) => (
              <option key={term.iri} value={term.iri}>
                {'\u00a0\u00a0'.repeat(depth)}
                {term.label}
              </option>
            ))}
          </select>
        </label>
      ))}
    </>
  )
}
