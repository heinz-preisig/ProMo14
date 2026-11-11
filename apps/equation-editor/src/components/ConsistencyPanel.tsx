import { useEffect, useState } from 'react'
import { checkConsistency, fixConsistency, getVariableReferences, type VariableReferences } from '../api'
import { affectedEquations, signatureText } from '../consistencyUtils'
import type { ConsistencyReport, ConsistencyRow, TokenFix, Variable } from '../types'

interface Props {
  open: boolean
  contextKey: string
  variables: Variable[]
  onRefresh: () => Promise<string>
  onVariable: (v: Variable) => void
  onEquation: (v: Variable, id: string) => void
  onClose: () => void
}

const colors = { error: '#b71c1c', advisory: '#946200', untracked: '#536878', consistent: '#24733e' }
const local = (iri: string) => iri.split('#').pop() ?? iri

export default function ConsistencyPanel({ open, contextKey, variables, onRefresh, onVariable, onEquation, onClose }: Props) {
  const [report, setReport] = useState<ConsistencyReport | null>(null)
  const [checkedKey, setCheckedKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('issues')
  const [pending, setPending] = useState<{
    row: ConsistencyRow; fix: TokenFix; references: VariableReferences['references']
  } | null>(null)
  const stale = report !== null && checkedKey !== contextKey

  const run = async () => {
    setBusy(true)
    setError('')
    setPending(null)
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

  const preview = async (row: ConsistencyRow, fix: TokenFix) => {
    if (!fix.variable) return
    setBusy(true)
    setError('')
    try {
      const refs = await getVariableReferences(fix.variable)
      setPending({ row, fix, references: refs.references })
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  const apply = async () => {
    if (!pending?.fix.variable || !report || stale) return
    setBusy(true)
    setError('')
    try {
      const next = await fixConsistency(report.revision, pending.row.equation, pending.fix.variable, pending.fix.action)
      setPending(null)
      const key = await onRefresh()
      setReport(next)
      setCheckedKey(key)
    } catch (err) {
      setPending(null)
      setError(`${err}. Recheck before trying again.`)
      setCheckedKey('')
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
        Checks saved-in-memory equations in this artefact and its pinned scope. Untracked is not verified-consistent.
        Corrections are suggestions, not proof of semantic correctness. No equations or memberships are changed automatically.
      </p>
      {stale && <p role="status" style={{ color: '#b71c1c' }}>Out of date after edits — recheck before applying corrections.</p>}
      {error && <p role="alert" style={{ color: '#b71c1c', whiteSpace: 'pre-wrap' }}>{error}</p>}
      {report && <>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 13 }}>
          {Object.entries(report.summary).map(([s, n]) => <span key={s} style={{ color: colors[s as ConsistencyRow['status']] }}>{s}: {n}</span>)}
          <span>Total: {report.equations.length}</span>
          <select aria-label="Filter consistency results" value={filter} onChange={(e) => setFilter(e.target.value)}>
            {['issues', 'all', 'error', 'advisory', 'untracked', 'consistent'].map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        {pending && <div role="alertdialog" aria-label="Confirm signature correction" style={{ padding: 12, border: '1px solid #e0aa44', marginTop: 12, background: '#fff8e1' }}>
          <strong>{pending.fix.label}</strong>
          <p>Replacement signature: {signatureText(pending.fix.action === 'clear_signature' ? {} : pending.fix.token_vector ?? null)}. Membership, units, indices and equations stay unchanged.</p>
          <p>Potentially affected in this scope: {affectedEquations(report, pending.fix.variable!).map((r) => `${r.equation_id} (${r.label})`).join(', ') || 'none'}.</p>
          <details><summary>Direct references across artefacts ({pending.references.length})</summary>
            {pending.references.map((r, i) => <div key={i}>{local(r.equation)} — {r.via} — {r.graph}</div>)}
          </details>
          <p>Review the cause before applying: a derived signature may inherit an incorrect operand declaration.</p>
          <button disabled={busy || stale} onClick={apply}>Confirm correction and recheck</button>{' '}
          <button disabled={busy} onClick={() => setPending(null)}>Cancel</button>
        </div>}
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
            <div style={{ fontSize: 12 }}>Declared tokens: {row.declared.tokens === null ? 'not explicitly declared' : signatureText(row.declared.tokens)}<br />
              Derived tokens: {signatureText(row.derived?.tokens ?? null)}</div>
            {row.conflicts.map((parts, i) => <div key={i} style={{ padding: 8, background: '#fff3e0', marginTop: 8 }}>
              <strong>Incompatible terms</strong>
              {parts.map((part, j) => <div key={j}><code>{part.expression}</code>: {signatureText(part.tokens)}</div>)}
            </div>)}
            {row.findings.map((f, i) => <div key={i} style={{ padding: '6px 0' }}>
              <strong style={{ fontSize: 12 }}>{f.message}</strong>
              {f.code === 'units_mismatch' && <div>Declared: {row.declared.units.join(', ')}; derived: {row.derived?.units.join(', ')}</div>}
              {f.code === 'indices_mismatch' && <div>Declared: {row.declared.indices.map(local).join(', ') || 'scalar'}; derived: {row.derived?.indices.map(local).join(', ') || 'scalar'}</div>}
              {f.fixes.map((fix, j) => <div key={j} style={{ marginTop: 4 }}>
                <button disabled={busy || stale || !!fix.blocked} onClick={() => preview(row, fix)}>{fix.label}…</button>
                {fix.blocked && <span style={{ fontSize: 12 }}> {fix.blocked}</span>}
              </div>)}
            </div>)}
            <div style={{ fontSize: 12, marginTop: 8 }}><strong>Operand declarations</strong>
              {row.operands.map((v) => <div key={v.iri}>
                <button onClick={() => openVariable(v.iri)}>{v.label}</button> {signatureText(v.tokens)}
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
