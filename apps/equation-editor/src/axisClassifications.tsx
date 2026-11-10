/** Multi-axis variable classification — one dropdown per applicable
 *  axis (determination / function / role …).
 *
 *  A variable's ``network`` is a domain *name*; axes bind to domain
 *  IRIs and inherit down the domain tree, so applicability is resolved
 *  via the domain records' parent chain.
 */
import type { CSSProperties } from 'react'
import type { AxisTerm, ClassificationAxis, Domain } from './types'

/** Shared label-cell style: the field name sits in a fixed-width
 *  column so every input/select in a stacked form starts at the
 *  same x position. */
export const FIELD_LABEL_STYLE: CSSProperties = {
  display: 'inline-block',
  width: 100,
  flexShrink: 0,
}

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

/** Derive the display ``kind`` from a classifications map (§24) —
 *  a projection, never stored; the backend applies the same rule
 *  (``compile_space.kind_tag``).  Bound-value terms win
 *  (constant > parameter), else the ``function`` axis term's label,
 *  else the first resolvable label, else ``''`` = unclassified. */
export function kindTag(
  axes: ClassificationAxis[],
  classifications: Record<string, string>,
): string {
  const labelOf = new Map<string, string>()
  for (const a of axes) for (const t of a.terms) labelOf.set(t.iri, t.label)
  const labels = Object.values(classifications).map(
    (t) => labelOf.get(t) ?? '',
  )
  for (const k of ['constant', 'parameter']) {
    if (labels.includes(k)) return k
  }
  const functionAxis = axes.find(
    (a) => a.name === 'function' || a.iri.split('#').pop()?.includes('function'),
  )
  if (functionAxis && classifications[functionAxis.iri]) {
    return labelOf.get(classifications[functionAxis.iri]) ?? ''
  }
  return labels.find((l) => l) ?? ''
}

/** Composite kind display (§24): the picked term labels joined in
 *  axis-declared order, e.g. ``flow · intensive · variable``.  Empty
 *  string when nothing is classified — callers render ``unclassified``. */
export function kindSummary(
  axes: ClassificationAxis[],
  classifications: Record<string, string>,
): string {
  const parts: string[] = []
  for (const a of axes) {
    const termIri = classifications[a.iri]
    if (!termIri) continue
    const label = a.terms.find((t) => t.iri === termIri)?.label
    if (label) parts.push(label)
  }
  return parts.join(' · ')
}

/** §24 token-neutrality ruling projected from classifications:
 *  physical ``state|effort|flow|reaction`` carry a conserved token;
 *  information ``state|input|output`` carry a reference token;
 *  ``constant|parameter|frame`` are neutral.  Term ancestry counts
 *  (``fundamental-state`` inherits ``state``); bound-value terms win
 *  over function/role — a constant or parameter is neutral whatever
 *  else is picked. */
export interface TokenPolicy {
  bearing: boolean
  family: 'conserved' | 'reference' | null
  kind: string
}

export function tokenPolicy(
  axes: ClassificationAxis[],
  classifications: Record<string, string>,
): TokenPolicy {
  const kind = kindTag(axes, classifications)
  const labelsOf = (axis: ClassificationAxis): Set<string> => {
    const byIri = new Map(axis.terms.map((t) => [t.iri, t]))
    const out = new Set<string>()
    let cur = axis.terms.find((t) => t.iri === classifications[axis.iri])
    while (cur) {
      out.add(cur.label)
      cur = cur.parent ? byIri.get(cur.parent) : undefined
    }
    return out
  }
  for (const a of axes) {
    const ls = labelsOf(a)
    if (ls.has('constant') || ls.has('parameter')) {
      return { bearing: false, family: null, kind }
    }
  }
  for (const a of axes) {
    const ls = labelsOf(a)
    const functionAxis =
      a.name === 'function' || a.iri.includes('function')
    const roleAxis = a.name === 'role' || a.iri.includes('role')
    if (functionAxis) {
      if (ls.has('frame')) return { bearing: false, family: null, kind }
      if (['state', 'effort', 'flow', 'reaction'].some((l) => ls.has(l))) {
        return { bearing: true, family: 'conserved', kind }
      }
    }
    if (roleAxis) {
      if (['state', 'input', 'output'].some((l) => ls.has(l))) {
        return { bearing: true, family: 'reference', kind }
      }
    }
  }
  return { bearing: false, family: null, kind }
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
  /** Axis names to hide — e.g. 'determination' on port variables,
   *  where port-ness is the structural port_variable flag, not a
   *  classification pick. */
  hiddenAxes?: string[]
}

/** One select per applicable axis; each option is an axis term. */
export default function AxisClassifications({
  axes,
  domain,
  domains,
  value,
  onChange,
  disabled,
  hiddenAxes,
}: AxisClassificationsProps) {
  const applicable = applicableAxes(axes, domain, domains).filter(
    (a) => !hiddenAxes?.includes(a.name),
  )
  if (!applicable.length) return null
  return (
    <>
      {applicable.map((axis) => (
        <label
          key={axis.iri}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          title={disabled ? 'Locked — variable is referenced by equations' : axis.iri}
        >
          <span style={FIELD_LABEL_STYLE}>{axis.name}:</span>
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
