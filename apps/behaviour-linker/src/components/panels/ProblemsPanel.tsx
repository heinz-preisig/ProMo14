import { card } from '../../styles'
import type { EvaluateReport } from '../../types'

interface ProblemsPanelProps {
  report: EvaluateReport | null
  lab: (iri: string | null | undefined) => string
  eqLhs: (iri: string) => string
}

export function ProblemsPanel({ report, lab, eqLhs }: ProblemsPanelProps) {
  if (
    !report ||
    (report.cycles.length === 0 &&
      report.conflicts.length === 0 &&
      report.order_violations.length === 0 &&
      report.warnings.length === 0)
  ) {
    return null
  }

  return (
    <div style={{ ...card, borderColor: '#e0b0b0' }}>
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          marginBottom: 6,
          color: '#a00',
        }}
      >
        Problems
      </div>
      {report.cycles.map((c, i) => (
        <div key={i} style={{ fontSize: 13, color: '#a00' }}>
          cycle: {c.map(eqLhs).join(' → ')}
        </div>
      ))}
      {report.conflicts.map((c, i) => (
        <div key={i} style={{ fontSize: 13, color: '#a00' }}>
          {c.kind}: {lab(c.variable)} {c.detail}
        </div>
      ))}
      {report.order_violations.map((v, i) => (
        <div key={i} style={{ fontSize: 13, color: '#a00' }}>
          order: {eqLhs(v.equation)} uses {lab(v.variable)}{' '}
          defined later by {eqLhs(v.defined_by)}
        </div>
      ))}
      {report.warnings.map((w, i) => (
        <div key={i} style={{ fontSize: 13, color: '#c80' }}>
          {w}
        </div>
      ))}
    </div>
  )
}
