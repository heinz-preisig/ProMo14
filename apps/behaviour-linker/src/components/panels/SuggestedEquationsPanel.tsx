import { EqLine } from '../EqLine'
import { btn, card } from '../../styles'
import type { Equation } from '../../types'

interface SuggestedEquationsPanelProps {
  frontier: string[]
  eqs: Map<string, Equation>
  lab: (iri: string | null | undefined) => string
  onResolve: (varIri: string, eqIri: string) => void
}

export function SuggestedEquationsPanel({
  frontier,
  eqs,
  lab,
  onResolve,
}: SuggestedEquationsPanelProps) {
  return (
    <div style={card}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        Suggested next equations
      </div>
      {frontier.length === 0 && (
        <div style={{ fontSize: 13, color: '#888' }}>
          No further equations needed.
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {frontier.map((eqIri) => {
          const e = eqs.get(eqIri)
          if (!e) return null
          return (
            <button
              key={eqIri}
              style={btn}
              title={e.rhs}
              onClick={() => onResolve(e.lhs, eqIri)}
            >
              + <EqLine eq={e} lhsLabel={lab(e.lhs)} />
            </button>
          )
        })}
      </div>
    </div>
  )
}
