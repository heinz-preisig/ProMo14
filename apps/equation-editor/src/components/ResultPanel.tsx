import { useEffect, useState } from 'react'
import { getVariableReferences } from '../api'
import { indexShortLabel } from '../latex'
import { referenceDisplay } from '../variableUtils'
import type { CheckResponse, Index, TokenFix, Variable } from '../types'

export interface ResultPanelProps {
  result: CheckResponse | null
  loading: boolean
  indices?: Index[]
  label?: string
  variables?: Variable[]
  /** Applies a structured-advisory fix (signature-only write). */
  onApplyFix?: (fix: TokenFix) => void
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

export default function ResultPanel({ result, loading, indices = [], label, variables = [], onApplyFix }: ResultPanelProps) {
  const [pendingFix, setPendingFix] = useState<{
    fix: TokenFix
    refs: { equation: string; graph: string; via: string }[] | null
  } | null>(null)
  useEffect(() => setPendingFix(null), [result])

  const requestFix = async (fix: TokenFix) => {
    if (!fix.variable) return
    try {
      const refs = await getVariableReferences(fix.variable)
      setPendingFix({ fix, refs: refs.references })
    } catch {
      setPendingFix({ fix, refs: null })
    }
  }

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
        {result.tokens_pretty != null && (
          <div>
            <strong>Tokens:</strong> {result.tokens_pretty}
          </div>
        )}
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
        {(result.advisories ?? []).length > 0 ? (
          <div style={{ color: '#8d6e00' }}>
            <strong>Advisories:</strong>
            {result.advisories!.map((a, i) => (
              <div key={i} style={{ margin: '4px 0 0 16px', fontSize: 12 }}>
                <div>{a.message}</div>
                {a.cause?.operands && a.cause.operands.length > 0 && (
                  <div style={{ fontSize: 11, marginTop: 2 }}>
                    operand signatures:{' '}
                    {a.cause.operands
                      .map((o) => `${o.label} = ${o.pretty}`)
                      .join(' · ')}
                  </div>
                )}
                {(a.fixes ?? []).length > 0 && onApplyFix && (
                  <div
                    style={{
                      display: 'flex',
                      gap: 8,
                      marginTop: 4,
                      flexWrap: 'wrap',
                    }}
                  >
                    {a.fixes!.map((f, j) => {
                      const resolvable =
                        !f.variable ||
                        variables.some((v) => v.iri === f.variable)
                      return (
                        <button
                          key={j}
                          disabled={!resolvable}
                          title={
                            resolvable
                              ? undefined
                              : 'variable not in this context'
                          }
                          onClick={() => requestFix(f)}
                          style={{
                            fontSize: 11,
                            padding: '2px 8px',
                            cursor: resolvable ? 'pointer' : 'default',
                            border: '1px solid #8d6e00',
                            background: '#fff',
                            borderRadius: 3,
                            color: '#8d6e00',
                          }}
                        >
                          {f.label}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            ))}
            {pendingFix && (
              <div
                style={{
                  margin: '6px 0 0 16px',
                  padding: 8,
                  background: '#fff8e1',
                  border: '1px solid #ffe082',
                  borderRadius: 4,
                  fontSize: 12,
                }}
              >
                <div>
                  {pendingFix.fix.label}
                  {pendingFix.refs !== null
                    ? pendingFix.refs.length
                      ? ` — changes the derived signature of ${pendingFix.refs.length} equation(s): ${pendingFix.refs
                          .map((r) => referenceDisplay(r, variables).eqId)
                          .join(', ')}`
                      : ' — no equations reference it'
                    : ' (reference count unavailable)'}
                </div>
                <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
                  <button
                    onClick={() => {
                      onApplyFix?.(pendingFix.fix)
                      setPendingFix(null)
                    }}
                  >
                    Apply
                  </button>
                  <button onClick={() => setPendingFix(null)}>Cancel</button>
                </div>
              </div>
            )}
          </div>
        ) : (
          (result.warnings ?? []).length > 0 && (
            <div style={{ color: '#8d6e00' }}>
              <strong>Warnings:</strong>
              <ul style={{ margin: '2px 0 0 16px', padding: 0 }}>
                {result.warnings!.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )
        )}
      </div>
    </div>
  )
}
