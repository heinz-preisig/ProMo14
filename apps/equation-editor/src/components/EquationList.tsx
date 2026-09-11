import { nodeToString } from '../api'
import type { AstNode, CheckResponse } from '../types'

export interface SavedEquation {
  id: string
  lhs: string
  text: string
  ast: AstNode | null
  check: CheckResponse | null
}

export interface EquationListProps {
  equations: SavedEquation[]
  onSelect: (eq: SavedEquation) => void
  onRemove: (id: string) => void
}

export default function EquationList({ equations, onSelect, onRemove }: EquationListProps) {
  if (equations.length === 0) {
    return <div style={{ color: '#888', fontSize: 13 }}>No equations saved yet.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <strong style={{ fontSize: 13 }}>Saved equations</strong>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {equations.map((eq) => {
          const ok = eq.check?.ok
          const summary = ok
            ? `${eq.check?.units_pretty ?? 'ok'}`
            : eq.check?.error_kind ?? '—'
          return (
            <div
              key={eq.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '6px 8px',
                background: ok ? '#e8f5e9' : '#fff',
                border: '1px solid #ccc',
                borderRadius: 4,
                fontSize: 12,
              }}
            >
              <button
                type="button"
                onClick={() => onSelect(eq)}
                style={{
                  flex: 1,
                  textAlign: 'left',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  fontSize: 12,
                }}
                title={eq.ast ? nodeToString(eq.ast) : eq.text}
              >
                {eq.text.length > 40 ? eq.text.slice(0, 40) + '…' : eq.text}
                <span style={{ color: ok ? '#2e7d32' : '#c62828', marginLeft: 8 }}>
                  [{summary}]
                </span>
              </button>
              <button
                type="button"
                onClick={() => onRemove(eq.id)}
                style={{
                  marginLeft: 8,
                  fontSize: 11,
                  color: '#c62828',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                ×
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
