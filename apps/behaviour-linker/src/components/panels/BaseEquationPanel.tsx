import { EqLine } from '../EqLine'
import { card } from '../../styles'
import type { BehaviourContext, Equation } from '../../types'

interface BaseEquationPanelProps {
  ctx: BehaviourContext | null
  baseEquation: string | null
  baseMode: 'state' | 'stateless'
  onPickBase: (iri: string | null) => void
  onSetMode: (mode: 'state' | 'stateless') => void
  lab: (iri: string | null | undefined) => string
}

export function BaseEquationPanel({
  ctx,
  baseEquation,
  baseMode,
  onPickBase,
  onSetMode,
  lab,
}: BaseEquationPanelProps) {
  const allEqs = ctx?.equations ?? []
  const stateEqs = allEqs.filter((e) => e.lhs_class === 'state')
  const otherEqs = allEqs.filter((e) => e.lhs_class !== 'state')

  const renderGroup = (title: string, eqs: Equation[]) =>
    eqs.length === 0 ? null : (
      <div key={title} style={{ marginTop: 6 }}>
        <div
          style={{
            fontSize: 12,
            color: '#666',
            marginBottom: 2,
          }}
        >
          {title}
        </div>
        {eqs.map((e) => (
          <label
            key={e.iri}
            style={{
              display: 'block',
              fontSize: 13,
              padding: '2px 0',
            }}
          >
            <input
              type="radio"
              checked={baseEquation === e.iri}
              onChange={() => onPickBase(e.iri)}
            />{' '}
            <EqLine eq={e} lhsLabel={lab(e.lhs)} />
          </label>
        ))}
      </div>
    )

  return (
    <div style={card}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        Base equation
      </div>
      <div style={{ fontSize: 13 }}>
        <label style={{ display: 'block', padding: '2px 0' }}>
          <input
            type="radio"
            checked={baseMode === 'state'}
            disabled={allEqs.length === 0}
            onChange={() => onSetMode('state')}
          />{' '}
          with base equation
        </label>
        {baseMode === 'state' && (
          <div style={{ marginLeft: 16 }}>
            {renderGroup('suggested base equations', stateEqs)}
            {renderGroup('other equations', otherEqs)}
          </div>
        )}
        <label style={{ display: 'block', padding: '2px 0' }}>
          <input
            type="radio"
            checked={baseMode === 'stateless'}
            onChange={() => {
              onSetMode('stateless')
              onPickBase(null)
            }}
          />{' '}
          without base equation
        </label>
        {baseMode === 'stateless' && (
          <div style={{ marginLeft: 16 }}>
            <label
              style={{
                display: 'block',
                fontSize: 13,
                padding: '2px 0',
              }}
            >
              <input
                type="radio"
                checked={baseEquation === null}
                onChange={() => onPickBase(null)}
              />{' '}
              <em>none — entity without base equation</em>
            </label>
          </div>
        )}
      </div>
    </div>
  )
}
