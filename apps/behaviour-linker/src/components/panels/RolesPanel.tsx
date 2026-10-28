import { EqLine } from '../EqLine'
import { btn, card } from '../../styles'
import type { Equation, EvaluateReport, Variable } from '../../types'

interface RolesPanelProps {
  report: EvaluateReport | null
  eqs: Map<string, Equation>
  instantiated: string[]
  ports: string[]
  outputs: string[]
  variables: Variable[]
  lab: (iri: string | null | undefined) => string
  onUnmark: (varIri: string) => void
  onMark: (
    varIri: string,
    role: 'instantiated' | 'ports' | 'outputs',
  ) => void
  onResolve: (varIri: string, eqIri: string) => void
}

export function RolesPanel({
  report,
  eqs,
  instantiated,
  ports,
  outputs,
  variables,
  lab,
  onUnmark,
  onMark,
  onResolve,
}: RolesPanelProps) {
  return (
    <div style={card}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        Roles
      </div>
      <div style={{ fontSize: 13 }}>
        <div>
          <b>state:</b> {lab(report?.state_variable)}
        </div>
        <div>
          <b>ports:</b>{' '}
          {ports.map((v) => (
            <span key={v} style={{ marginRight: 8 }}>
              <code>{lab(v)}</code>{' '}
              <a
                style={{ cursor: 'pointer', color: '#c00' }}
                onClick={() => onUnmark(v)}
              >
                ✕
              </a>
            </span>
          ))}
          {ports.length === 0 && '—'}
        </div>
        <div>
          <b>instantiated:</b>{' '}
          {instantiated.map((v) => (
            <span key={v} style={{ marginRight: 8 }}>
              <code>{lab(v)}</code>{' '}
              <a
                style={{ cursor: 'pointer', color: '#c00' }}
                onClick={() => onUnmark(v)}
              >
                ✕
              </a>
            </span>
          ))}
          {instantiated.length === 0 && '—'}
        </div>
        <div>
          <b>outputs:</b>{' '}
          {outputs.map((v) => (
            <span key={v} style={{ marginRight: 8 }}>
              <code>{lab(v)}</code>{' '}
              <a
                style={{ cursor: 'pointer', color: '#c00' }}
                onClick={() => onUnmark(v)}
              >
                ✕
              </a>
            </span>
          ))}
          {outputs.length === 0 && '—'}
        </div>
        {(report?.unconsumed.length ?? 0) > 0 && (
          <div style={{ color: '#c80' }}>
            <b>unconsumed:</b>{' '}
            {report!.unconsumed.map((v) => (
              <span key={v} style={{ marginRight: 8 }}>
                <code>{lab(v)}</code>
                <button
                  style={{ ...btn, marginLeft: 4 }}
                  title="declare output"
                  onClick={() => onMark(v, 'outputs')}
                >
                  output
                </button>
              </span>
            ))}
          </div>
        )}
        {(report?.auto_instantiated.length ?? 0) > 0 && (
          <div>
            <b>constants/parameters:</b>{' '}
            {report!.auto_instantiated.map((u) => (
              <span key={u.variable} style={{ marginRight: 8 }}>
                <code>{lab(u.variable)}</code>
                {u.candidates.map((c) => {
                  const cand = eqs.get(c)
                  return (
                    <button
                      key={c}
                      style={{ ...btn, marginLeft: 4 }}
                      title={`override: define via ${cand?.rhs ?? ''}`}
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
              </span>
            ))}
          </div>
        )}
        <div style={{ marginTop: 4 }}>
          <b>mark variable:</b>{' '}
          <select
            style={{ fontSize: 13 }}
            value=""
            onChange={(e) => {
              if (e.target.value) onMark(e.target.value, 'instantiated')
            }}
          >
            <option value="">instantiate…</option>
            {variables.map((v) => (
              <option key={v.iri} value={v.iri}>
                {v.label}
              </option>
            ))}
          </select>{' '}
          <select
            style={{ fontSize: 13 }}
            value=""
            onChange={(e) => {
              if (e.target.value) onMark(e.target.value, 'ports')
            }}
          >
            <option value="">port…</option>
            {variables.map((v) => (
              <option key={v.iri} value={v.iri}>
                {v.label}
              </option>
            ))}
          </select>{' '}
          <select
            style={{ fontSize: 13 }}
            value=""
            onChange={(e) => {
              if (e.target.value) onMark(e.target.value, 'outputs')
            }}
          >
            <option value="">output…</option>
            {variables.map((v) => (
              <option key={v.iri} value={v.iri}>
                {v.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  )
}
