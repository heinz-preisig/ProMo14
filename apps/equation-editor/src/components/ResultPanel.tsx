import { indexShortLabel } from '../latex'
import type { CheckResponse, Index, Variable } from '../types'

export interface ResultPanelProps {
  result: CheckResponse | null
  loading: boolean
  indices?: Index[]
  label?: string
  variables?: Variable[]
  /** Applies a structured-advisory fix (signature-only write). */
}

function formatIndex(iri: string, indices: Index[] = []) {
  const idx = indices.find((i) => i.iri === iri)
  if (!idx) return iri
  return `${indexShortLabel(idx)} (${idx.label})`
}

// Incidence entries are IRIs (".../ontology#Mm", "net!x", "...#x") — display the
// internal ID with the human label when the variable is known: "V_62 (setPoint)".
function formatIncidence(iri: string, variables: Variable[] = []): string {
  const local = iri.split(/[:#!]/).pop() ?? iri
  const v = variables.find((x) => x.iri === iri)
  return v && v.label && v.label !== local ? `${local} (${v.label})` : local
}

export default function ResultPanel({ result, loading, indices = [], label, variables = [] }: ResultPanelProps) {
  if (loading) return <div style={{ color: '#666', fontSize: 13 }}>Checking…</div>
  if (!result) return <div style={{ color: '#888', fontSize: 13 }}>No check result yet.</div>

  if (!result.ok) {
    return (
      <div
        style={{
          padding: 12,
          background: '#ffebee',
          border: '1px solid #ef9a9a',
          borderRadius: 4,
          color: '#c62828',
        }}
      >
        <strong>{result.error_kind ?? 'Error'}</strong>
        <div style={{ marginTop: 4, fontSize: 13 }}>{result.error}</div>
        {result.candidates && result.candidates.length > 0 && (
          <div style={{ marginTop: 8, fontSize: 12 }}>
            <strong>Did you mean one of these?</strong>
            <ul style={{ margin: '4px 0', paddingLeft: 18 }}>
              {result.candidates.map((c, i) => (
                <li key={i}>
                  {c.network as string}!{c.label as string} ({c.iri as string})
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      style={{
        padding: 12,
        background: '#e8f5e9',
        border: '1px solid #a5d6a7',
        borderRadius: 4,
      }}
    >
      <div style={{ color: '#2e7d32', fontWeight: 'bold' }}>Check passed</div>
      <div style={{ marginTop: 8, fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div>
          <strong>Units:</strong> {result.units_pretty ?? result.units?.join(', ') ?? '—'}
        </div>
        <div>
          <strong>Index structure:</strong>{' '}
          {result.indices && result.indices.length > 0
            ? result.indices.map((iri) => formatIndex(iri, indices)).join(', ')
            : 'none — the expression has no free indices'}
        </div>
        <div>
          <strong>Incidence:</strong>{' '}
          {result.incidence ? result.incidence.map((i) => formatIncidence(i, variables)).join(', ') : '[]'}
        </div>
        {(label ?? result.label) && (
          <div>
            <strong>Label:</strong> {label ?? result.label}
          </div>
        )}
      </div>
    </div>
  )
}
