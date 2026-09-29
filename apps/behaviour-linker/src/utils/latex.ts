import type { Assignment, Equation, EvaluateReport } from '../types'

/** Escape a plain string for safe insertion into HTML text/attributes. */
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

/** Short display form of an IRI: fragment after # or last /. */
function frag(iri: string): string {
  const h = iri.split('#')
  if (h.length > 1) return h[h.length - 1]
  const s = iri.split('/')
  return s[s.length - 1]
}

/** Escape plain text so it is safe inside a LaTeX math \text{...} block. */
export function texEscape(s: string): string {
  return s
    .replace(/\\/g, '\\textbackslash{}')
    .replace(/&/g, '\\&')
    .replace(/%/g, '\\%')
    .replace(/#/g, '\\#')
    .replace(/_/g, '\\_')
    .replace(/\{/g, '\\{')
    .replace(/\}/g, '\\}')
    .replace(/\$/g, '\\$')
    .replace(/~/g, '\\textasciitilde{}')
    .replace(/\^/g, '\\textasciicircum{}')
}

/** Render-ready LaTeX for an entity assignment. */
export function buildPrintableLatex(args: {
  entityType: string
  entityLabel?: string | null
  report: EvaluateReport
  assignment: Pick<
    Assignment,
    'sequence' | 'base_equation' | 'instantiated' | 'ports'
  >
  eqs: Map<string, Equation>
  lab: (iri: string | null | undefined) => string
}): string {
  const {
    entityType,
    entityLabel,
    report,
    assignment: { sequence, base_equation, instantiated, ports },
    eqs,
    lab,
  } = args
  const esc = texEscape
  const header: string[] = []
  header.push(`\\text{Entity: ${esc(entityLabel ?? frag(entityType))}}`)
  if (report.state_variable) {
    header.push(`\\text{state: } ${esc(lab(report.state_variable))}`)
  }
  const eqLines = sequence
    .map((eqIri) => {
      const e = eqs.get(eqIri)
      if (!e) return ''
      const marker = eqIri === base_equation ? ' \\text{(base)}' : ''
      const lhs = e.lhs_latex ?? esc(lab(e.lhs))
      const rhs = e.rhs_latex ?? ''
      return `${lhs} = ${rhs}${marker}`
    })
    .filter(Boolean)
  const meta: string[] = []
  if (instantiated.length > 0) {
    meta.push(
      `\\text{instantiated: } ${instantiated
        .map((v) => esc(lab(v)))
        .join(', ')}`,
    )
  }
  if (ports.length > 0) {
    meta.push(
      `\\text{ports: } ${ports.map((v) => esc(lab(v))).join(', ')}`,
    )
  }
  const all = [...header, ...eqLines, ...meta]
  if (all.length === 0) return ''
  const eqBlockEnd = header.length + eqLines.length - 1
  return `\\begin{gathered}\n${all
    .map((l, i) => {
      const br =
        eqLines.length > 0 && meta.length > 0 && i === eqBlockEnd
          ? '\\\\[6pt]'
          : '\\\\'
      return `  ${l} ${br}`
    })
    .join('\n')}\n\\end{gathered}`
}
