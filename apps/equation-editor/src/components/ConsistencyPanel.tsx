import { useEffect, useState } from 'react'
import { checkConsistency } from '../api'
import type { ConsistencyReport, ConsistencyRow, Variable } from '../types'

interface Props {
  open: boolean
  contextKey: string
  variables: Variable[]
  onRefresh: () => Promise<string>
  onVariable: (v: Variable) => void
  onEquation: (v: Variable, id: string) => void
  onClose: () => void
}

const colors = { error: '#b71c1c', consistent: '#24733e' }
const local = (iri: string) => iri.split('#').pop() ?? iri

export default function ConsistencyPanel({ open, contextKey, variables, onRefresh, onVariable, onEquation, onClose }: Props) {
  const [report, setReport] = useState<ConsistencyReport | null>(null)
  const [checkedKey, setCheckedKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('issues')
  const stale = report !== null && checkedKey !== contextKey

  const run = async () => {
    setBusy(true)
    setError('')
    try {
      const key = await onRefresh()
      const next = await checkConsistency()
      setReport(next)
      setCheckedKey(key)
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (open && report === null) void run()
  }, [open])

  if (!open) return null
  const rows = report?.equations.filter((r) => filter === 'all' || (filter === 'issues' ? r.status !== 'consistent' : r.status === filter)) ?? []
  const findVariable = (iri: string) => variables.find((v) => v.iri === iri)
  const openVariable = (iri: string) => {
    const variable = findVariable(iri)
    if (variable) onVariable(variable)
  }

  return (
    <section aria-label="Equation consistency report" style={{ border: '1px solid #b0bec5', borderRadius: 6, padding: 16, background: '#fafcfd' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <strong>Global consistency check</strong>
        <button onClick={run} disabled={busy}>{busy ? 'Checking…' : 'Check / recheck'}</button>
        <button onClick={onClose} disabled={busy} style={{ marginLeft: 'auto' }}>Close report</button>
      </div>
      <p style={{ fontSize: 12, color: '#546e7a' }}>
        Checks units, indices and expression validity in this artefact and its pinned scope.
        This is a structural check, not proof of physical meaning or connection validity. No declarations are changed.
      </p>
      {stale && <p role="status" style={{ color: '#b71c1c' }}>Out of date after edits — recheck for current results.</p>}
      {error && <p role="alert" style={{ color: '#b71c1c', whiteSpace: 'pre-wrap' }}>{error}</p>}
      {report && <>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 13 }}>
          {Object.entries(report.summary).map(([s, n]) => <span key={s} style={{ color: colors[s as ConsistencyRow['status']] }}>{s}: {n}</span>)}
          <span>Total: {report.equations.length}</span>
          <select aria-label="Filter consistency results" value={filter} onChange={(e) => setFilter(e.target.value)}>
            {['issues', 'all', 'error', 'consistent'].map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div style={{ maxHeight: '55vh', overflowY: 'auto', marginTop: 12 }}>
          {rows.map((row) => <details key={`${row.variable}:${row.equation}`} style={{ borderTop: '1px solid #ddd', padding: '8px 0' }}>
            <summary style={{ color: colors[row.status], cursor: 'pointer' }}>{row.equation_id} — {row.label} ({row.network}) — {row.status}</summary>
            <div style={{ display: 'flex', gap: 8, margin: '8px 0' }}>
              <button onClick={() => openVariable(row.variable)}>Inspect variable</button>
              <button onClick={() => {
                const variable = findVariable(row.variable)
                if (variable) onEquation(variable, row.equation_id)
              }}>Open equation</button>
            </div>
            <div style={{ fontSize: 11, overflowWrap: 'anywhere' }}>Owning artefact(s): {row.graphs.map((g) => <a key={g} style={{ marginRight: 8 }} href={`${window.location.pathname}?graph=${encodeURIComponent(g)}`} target="_blank" rel="noreferrer">{g}</a>)}</div>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{row.label} := {row.rhs}</pre>
            {row.findings.map((f, i) => <div key={i} style={{ padding: '6px 0' }}>
              <strong style={{ fontSize: 12 }}>{f.message}</strong>
              {f.code === 'units_mismatch' && <div>Declared: {row.declared.units.join(', ')}; derived: {row.derived?.units.join(', ')}</div>}
              {f.code === 'indices_mismatch' && <div>Declared: {row.declared.indices.map(local).join(', ') || 'scalar'}; derived: {row.derived?.indices.map(local).join(', ') || 'scalar'}</div>}
            </div>)}
            <div style={{ fontSize: 12, marginTop: 8 }}><strong>Operand declarations</strong>
              {row.operands.map((v) => <div key={v.iri}>
                <button onClick={() => openVariable(v.iri)}>{v.label}</button> units: {v.units.join(", ")}; indices: {v.indices.map(local).join(", ") || "scalar"}
                {report.equations.filter((r) => r.variable === v.iri).map((r) => <button key={r.equation} style={{ marginLeft: 6, color: colors[r.status] }} onClick={() => {
                  const variable = findVariable(v.iri)
                  if (variable) onEquation(variable, r.equation_id)
                }}>{r.equation_id}: {r.status}</button>)}
              </div>)}
            </div>
          </details>)}
          {rows.length === 0 && <p>No equations in this category.</p>}
        </div>
      </>}
    </section>
  )
}
