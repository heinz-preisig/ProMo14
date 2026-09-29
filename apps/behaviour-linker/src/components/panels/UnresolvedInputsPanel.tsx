import { EqLine } from '../EqLine'
import { btn, card } from '../../styles'
import type { Equation, EvaluateReport, UnresolvedVar } from '../../types'

interface UnresolvedInputsPanelProps {
  unresolved: UnresolvedVar[]
  report: EvaluateReport | null
  eqs: Map<string, Equation>
  lab: (iri: string | null | undefined) => string
  onResolve: (varIri: string, eqIri: string) => void
  onMark: (varIri: string, role: 'instantiated' | 'ports') => void
}

export function UnresolvedInputsPanel({
  unresolved,
  report,
  eqs,
  lab,
  onResolve,
  onMark,
}: UnresolvedInputsPanelProps) {
  return (
    <div style={card}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        Unresolved inputs ({report?.unresolved.length ?? 0})
      </div>
      {unresolved.map((u) => (
        <div
          key={u.variable}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexWrap: 'wrap',
            fontSize: 13,
            padding: '3px 0',
          }}
        >
          <code style={{ minWidth: 90 }}>{lab(u.variable)}</code>
          {u.candidates.map((c) => {
            const cand = eqs.get(c)
            return (
              <button
                key={c}
                style={btn}
                title={cand?.rhs}
                onClick={() => onResolve(u.variable, c)}
              >
                +{' '}
                {cand ? (
                  <EqLine eq={cand} lhsLabel={lab(cand.lhs)} />
                ) : (
                  lab(c)
                )}
              </button>
            )
          })}
          {u.candidates.length === 0 && (
            <span style={{ color: '#999' }}>no defining eq</span>
          )}
          <button style={btn} onClick={() => onMark(u.variable, 'instantiated')}>
            instantiate
          </button>
          <button style={btn} onClick={() => onMark(u.variable, 'ports')}>
            port
          </button>
        </div>
      ))}
      {report && report.unresolved.length === 0 && (
        <div style={{ fontSize: 13, color: '#0a7' }}>all inputs resolved</div>
      )}
    </div>
  )
}
