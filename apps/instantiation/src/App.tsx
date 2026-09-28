import { useCallback, useEffect, useState } from 'react'
import {
  generateCode,
  GRAPH_IRI,
  loadReport,
  putValues,
  saveStore,
  solveInitial,
  VARS_IRI,
} from './api'
import type {
  CodeOut,
  EntityInstantiation,
  InitialOut,
  InstantiationReport,
  VarBinding,
} from './types'
import { useStoreDirty } from '@promo/ui'

/** All coordinate keys for a binding — the cartesian product of its
 *  index element sets, "|"-joined in indexStructure order, last index
 *  fastest (a scalar yields the single empty key).  Convention:
 *  docs/value-cells.md. */
function coordKeys(indices: Record<string, string[] | null>): string[] {
  let keys = ['']
  for (const els of Object.values(indices))
    keys = keys.flatMap((k) => (els ?? []).map((e) => (k ? `${k}|${e}` : e)))
  return keys
}

/** Parse a par input — a lone number or a comma/space-separated flat
 *  list (index order). */
function parsePar(raw: string): number | number[] | undefined {
  const t = raw.trim()
  if (!t) return undefined
  const parts = t.split(/[\s,;]+/).filter(Boolean)
  const nums = parts.map(Number)
  if (nums.some(Number.isNaN)) return undefined
  return nums.length === 1 ? nums[0] : nums
}

const TARGETS = ['python', 'julia', 'matlab'] as const
type Target = (typeof TARGETS)[number]

/** Short display form of an IRI — the label map, else the fragment. */
function useLabel(report: InstantiationReport | null) {
  return useCallback(
    (iri: string | null | undefined): string => {
      if (!iri) return '—'
      const lab = report?.labels?.[iri]
      if (lab) return lab
      const frag = iri.split(/[/#]/).pop()
      return frag || iri
    },
    [report],
  )
}

const S = {
  app: {
    display: 'flex', flexDirection: 'column' as const,
    height: '100%', color: '#1a1a1a',
  },
  header: {
    display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' as const,
    padding: '10px 16px', background: '#fff',
    borderBottom: '1px solid #ddd', minHeight: 48,
  },
  title: { fontSize: 16, fontWeight: 600 },
  meta: { fontSize: 12, color: '#666', fontFamily: 'monospace' },
  main: {
    flex: 1, overflow: 'auto', padding: 16,
    display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16,
    alignContent: 'start',
  },
  card: {
    background: '#fff', border: '1px solid #ddd', borderRadius: 6,
    padding: 12, marginBottom: 12,
  },
  h3: { margin: '0 0 8px', fontSize: 13, fontWeight: 600, color: '#333' },
  table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: 12 },
  th: {
    textAlign: 'left' as const, padding: '4px 8px', color: '#666',
    borderBottom: '1px solid #eee', fontWeight: 600, fontSize: 11,
  },
  td: { padding: '4px 8px', borderBottom: '1px solid #f3f3f3' },
  badge: (bg: string) => ({
    display: 'inline-block', padding: '1px 7px', borderRadius: 10,
    fontSize: 11, fontWeight: 600, background: bg, color: '#fff',
  }),
  pre: {
    margin: 0, padding: 12, background: '#0f172a', color: '#e2e8f0',
    borderRadius: 6, fontSize: 12, lineHeight: 1.5, overflow: 'auto',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    maxHeight: '60vh',
  },
  btn: (primary: boolean) => ({
    padding: '6px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
    border: '1px solid ' + (primary ? '#2563eb' : '#ccc'),
    borderRadius: 6, background: primary ? '#2563eb' : '#fff',
    color: primary ? '#fff' : '#333',
  }),
  select: {
    padding: '6px 8px', fontSize: 13, borderRadius: 6,
    border: '1px solid #ccc', background: '#fff',
  },
}

function Problems({ report }: { report: InstantiationReport }) {
  if (!report.problems.length) return null
  return (
    <div style={{ ...S.card, borderColor: '#f59e0b', background: '#fffbeb' }}>
      <h3 style={{ ...S.h3, color: '#b45309' }}>
        {report.problems.length} problem{report.problems.length > 1 ? 's' : ''}
      </h3>
      {report.problems.map((p, i) => (
        <div key={i} style={{ fontSize: 12, padding: '2px 0' }}>
          <span style={S.badge('#f59e0b')}>{p.kind}</span>{' '}
          {p.message}
        </div>
      ))}
    </div>
  )
}

function EntityCard({
  e, lab,
}: { e: EntityInstantiation; lab: (i: string | null | undefined) => string }) {
  return (
    <div style={S.card}>
      <h3 style={S.h3}>
        {lab(e.entity_type)}{' '}
        <span style={{ fontWeight: 400, color: '#888', fontSize: 11 }}>
          {e.nodes.length} node{e.nodes.length !== 1 ? 's' : ''}
          {e.closed ? ' · closed' : ' · open'}
        </span>
      </h3>
      <table style={S.table}>
        <thead>
          <tr>
            <th style={S.th}>variable</th>
            <th style={S.th}>binding</th>
            <th style={S.th}>instance</th>
            <th style={S.th}>indices</th>
          </tr>
        </thead>
        <tbody>
          {e.variables.map((v) => (
            <tr key={v.instance}>
              <td style={S.td}>{lab(v.var)}</td>
              <td style={S.td}>
                <span style={S.badge(
                  v.binding === 'incidence' ? '#7c3aed'
                  : v.binding === 'port' ? '#0891b2'
                  : v.binding === 'parameter' ? '#059669'
                  : v.binding === 'constant' ? '#65a30d'
                  : '#64748b',
                )}>
                  {v.binding}
                </span>
                {v.role === 'state' && (
                  <span style={{ ...S.badge('#dc2626'), marginLeft: 4 }}>
                    state
                  </span>
                )}
              </td>
              <td style={{ ...S.td, fontFamily: 'monospace' }}>{v.instance}</td>
              <td style={{ ...S.td, color: '#888', fontSize: 11 }}>
                {Object.entries(v.indices)
                  .map(([i, els]) => els == null
                    ? `${lab(i)}[·]` : `${lab(i)}[${els.length}]`)
                  .join(' ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {e.equations.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#555' }}>
          {e.equations.map((q) => (
            <div key={q.equation} style={{ fontFamily: 'monospace' }}>
              {lab(q.lhs)} := {q.equation.split(/[/#]/).pop()}
            </div>
          ))}
        </div>
      )}
      {e.initial_equations.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#555' }}>
          {e.initial_equations.map((q) => (
            <div key={q.equation} style={{ fontFamily: 'monospace' }}>
              {lab(q.lhs)} := {q.equation.split(/[/#]/).pop()}{' '}
              <span style={S.badge('#0d9488')}>init</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/** Bindings that take §20 value cells: parameter slots (ν) and state
 *  IC pins, plus anything that already carries a table. */
function editableBindings(report: InstantiationReport) {
  return report.entity_types.flatMap((e) =>
    e.variables
      .filter((v) =>
        v.binding === 'parameter' || v.role === 'state'
        || Object.keys(v.values ?? {}).length > 0)
      .map((v) => ({ entityType: e.entity_type, v })),
  )
}

/** Seed the cell-editor drafts from a freshly loaded report. */
function seedCells(report: InstantiationReport) {
  const out: Record<string, Record<string, string>> = {}
  for (const e of report.entity_types)
    for (const v of e.variables)
      for (const [k, val] of Object.entries(v.values ?? {}))
        (out[v.var] ??= {})[k] = String(val)
  return out
}

function ValuesCard({
  report, lab, onSaved,
}: {
  report: InstantiationReport
  lab: (i: string | null | undefined) => string
  onSaved: () => void
}) {
  const [edits, setEdits] = useState<Record<string, Record<string, string>>>(
    () => seedCells(report))
  const [saving, setSaving] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  // Report reloads surface freshly stored cells; keep in-flight edits
  // on other variables untouched.
  useEffect(() => {
    setEdits((prev) => {
      const seeded = seedCells(report)
      const merged = { ...seeded }
      for (const [varIri, tbl] of Object.entries(prev))
        merged[varIri] = { ...seeded[varIri], ...tbl }
      return merged
    })
  }, [report])

  const rows = editableBindings(report)

  const save = async (v: VarBinding) => {
    setSaving(v.var)
    setErr(null)
    try {
      const values: Record<string, number> = {}
      for (const key of coordKeys(v.indices)) {
        const raw = (edits[v.var]?.[key] ?? '').trim()
        if (raw !== '') values[key] = Number(raw)
      }
      const res = await putValues(v.var, values)
      setEdits((prev) => ({
        ...prev,
        [v.var]: Object.fromEntries(coordKeys(v.indices).map((k) =>
          [k, res.values[k] != null ? String(res.values[k]) : ''])),
      }))
      onSaved()
    } catch (e) {
      setErr(String(e))
    } finally {
      setSaving(null)
    }
  }

  return (
    <div style={S.card}>
      <h3 style={S.h3}>Values</h3>
      <div style={{ fontSize: 11, color: '#888', marginBottom: 8 }}>
        value cells — ν parameter tables and IC pins, keyed by
        index-element coordinates
      </div>
      {err && (
        <div style={{ color: '#dc2626', fontSize: 12, marginBottom: 8 }}>
          {err}
        </div>
      )}
      {rows.length === 0 && (
        <div style={{ fontSize: 12, color: '#888' }}>
          no parameter or state bindings to value
        </div>
      )}
      {rows.map(({ entityType, v }) => {
        const keys = coordKeys(v.indices)
        const stored = Object.keys(v.values ?? {}).length
        return (
          <div key={v.instance} style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 12, marginBottom: 4 }}>
              <b>{lab(v.var)}</b>{' '}
              <span style={{ color: '#888', fontSize: 11 }}>
                {lab(entityType)}{v.role === 'state' ? ' · IC pin' : ''}
                {stored ? ` · ${stored} cell${stored > 1 ? 's' : ''}` : ''}
              </span>
              <button
                style={{ ...S.btn(false), float: 'right', padding: '2px 10px', fontSize: 11 }}
                disabled={saving === v.var}
                onClick={() => save(v)}
              >
                {saving === v.var ? '…' : 'save cells'}
              </button>
            </div>
            <table style={S.table}>
              <tbody>
                {keys.map((k) => (
                  <tr key={k}>
                    <td style={{ ...S.td, fontSize: 11, color: '#666' }}>
                      {k ? k.split('|').map(lab).join(' · ') : 'scalar'}
                    </td>
                    <td style={{ ...S.td, textAlign: 'right' }}>
                      <input
                        style={{
                          width: 110, padding: '2px 6px', fontSize: 12,
                          border: '1px solid #ccc', borderRadius: 4,
                          textAlign: 'right', fontFamily: 'monospace',
                        }}
                        value={edits[v.var]?.[k] ?? ''}
                        placeholder='—'
                        onChange={(e) => setEdits((prev) => ({
                          ...prev,
                          [v.var]: { ...prev[v.var], [k]: e.target.value },
                        }))}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      })}
    </div>
  )
}

/** The emitted identifier for a binding — mirrors ``plan.emit_name``:
 *  the sanitised instance base, suffixed with the entity-type fragment
 *  when several types share the variable's base id. */
function emitName(v: VarBinding, counts: Map<string, number>): string {
  const i = v.instance.indexOf('@')
  const base = i < 0 ? v.instance : v.instance.slice(0, i)
  const frag = i < 0 ? '' : v.instance.slice(i + 1)
  const n = base.replace(/\W/g, '_')
  return (counts.get(base) ?? 0) > 1
    ? `${n}_${frag.replace(/\W/g, '_').replace(/^etype_/, '')}`
    : n
}

/** The par keys the t=0 solve reads, derived client-side — parameter
 *  slots without cells or literal values, plus ``ic0_<name>`` for
 *  states whose IC is covered by neither an ``initialise`` equation
 *  nor cells.  Keys are the emitted names (``par["V_5"]``), not the
 *  display labels; the server echoes its own list in ``par_needed``. */
function deriveParKeys(report: InstantiationReport) {
  const all = report.entity_types.flatMap((e) => e.variables)
  const counts = new Map<string, number>()
  for (const v of all) {
    const base = v.instance.split('@')[0]
    counts.set(base, (counts.get(base) ?? 0) + 1)
  }
  const keys: string[] = []
  for (const e of report.entity_types) {
    const initLhs = new Set(e.initial_equations.map((q) => q.lhs))
    for (const v of e.variables) {
      const name = emitName(v, counts)
      const cellCovered = Object.keys(v.values ?? {}).length > 0
      if ((v.binding === 'parameter' || v.binding === 'input'
          || (v.binding === 'constant' && v.value == null))
          && !cellCovered)
        keys.push(name)
      if (v.role === 'state' && !initLhs.has(v.var) && !cellCovered)
        keys.push(`ic0_${name}`)
    }
  }
  return keys
}

function SolveCard({
  report, lab,
}: {
  report: InstantiationReport
  lab: (i: string | null | undefined) => string
}) {
  const [parText, setParText] = useState<Record<string, string>>({})
  const [steady, setSteady] = useState(false)
  const [out, setOut] = useState<InitialOut | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const keys = Array.from(new Set([
    ...deriveParKeys(report),
    ...(out?.par_needed ?? []),
  ]))

  const solve = async () => {
    setBusy(true)
    setErr(null)
    try {
      const par: Record<string, number | number[]> = {}
      for (const k of keys) {
        const p = parsePar(parText[k] ?? '')
        if (p !== undefined) par[k] = p
      }
      setOut(await solveInitial(par, steady))
    } catch (e) {
      setErr(String(e))
      setOut(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={S.card}>
      <h3 style={S.h3}>
        t = 0 solve{' '}
        <label style={{ fontSize: 11, fontWeight: 400, color: '#666' }}>
          <input
            type='checkbox'
            checked={steady}
            onChange={(e) => setSteady(e.target.checked)}
          />{' '}
          steady state
        </label>
        <button
          style={{ ...S.btn(true), float: 'right', padding: '4px 12px', fontSize: 12 }}
          disabled={busy}
          onClick={solve}
        >
          {busy ? '…' : 'solve'}
        </button>
      </h3>

      {report.ic_needs.length > 0 && (
        <table style={{ ...S.table, marginBottom: 8 }}>
          <thead>
            <tr>
              <th style={S.th}>need</th>
              <th style={S.th}>kind</th>
              <th style={S.th}>status</th>
            </tr>
          </thead>
          <tbody>
            {report.ic_needs.map((n, i) => (
              <tr key={i}>
                <td style={S.td}>{lab(n.var)}</td>
                <td style={S.td}>{n.kind}</td>
                <td style={S.td}>
                  <span style={S.badge(
                    n.status === 'supplied' ? '#059669' : '#dc2626')}>
                    {n.status}
                  </span>
                  {n.supplied_by && (
                    <span style={{ fontSize: 11, color: '#888' }}>
                      {' '}{n.supplied_by}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {keys.length > 0 && (
        <table style={{ ...S.table, marginBottom: 8 }}>
          <tbody>
            {keys.map((k) => (
              <tr key={k}>
                <td style={{ ...S.td, fontFamily: 'monospace', fontSize: 11 }}>
                  {k}
                </td>
                <td style={{ ...S.td, textAlign: 'right' }}>
                  <input
                    style={{
                      width: 140, padding: '2px 6px', fontSize: 12,
                      border: '1px solid #ccc', borderRadius: 4,
                      textAlign: 'right', fontFamily: 'monospace',
                    }}
                    value={parText[k] ?? ''}
                    placeholder='scalar or list'
                    onChange={(e) => setParText((prev) => ({
                      ...prev, [k]: e.target.value,
                    }))}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {err && (
        <pre style={{ ...S.pre, background: '#7f1d1d', maxHeight: 160 }}>
          {err}
        </pre>
      )}
      {out && !out.ok && (
        <pre style={{ ...S.pre, background: '#7f1d1d', maxHeight: 160 }}>
          {out.error}
        </pre>
      )}
      {out?.ok && (
        <div style={{ fontSize: 12 }}>
          {out.states.map((s) => (
            <div key={s.name} style={{ padding: '2px 0' }}>
              <b>{lab(s.var)}</b>{' '}
              <span style={{ fontFamily: 'monospace', color: '#333' }}>
                = [{s.values.map((x) => +x.toPrecision(6)).join(', ')}]
              </span>
            </div>
          ))}
          <div style={{ color: '#888', fontSize: 11, marginTop: 4 }}>
            y0 = [{out.y0.map((x) => +x.toPrecision(6)).join(', ')}]
            {out.steady_state ? ' · steady state' : ''}
          </div>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const { dirty } = useStoreDirty()
  const [report, setReport] = useState<InstantiationReport | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [target, setTarget] = useState<Target>('julia')
  const [code, setCode] = useState<CodeOut | null>(null)
  const [busy, setBusy] = useState(false)
  const lab = useLabel(report)

  useEffect(() => {
    loadReport().then(setReport).catch((e) => setErr(String(e)))
  }, [])

  const generate = useCallback(async () => {
    setBusy(true)
    try {
      setCode(await generateCode(target))
    } catch (e) {
      setCode({ ok: false, target, source: '', error: String(e), problems: [] })
    } finally {
      setBusy(false)
    }
  }, [target])

  const copy = useCallback(() => {
    if (code?.source) navigator.clipboard.writeText(code.source)
  }, [code])

  const download = useCallback(() => {
    if (!code?.source) return
    const ext = { python: 'py', julia: 'jl', matlab: 'm' }[code.target] || 'txt'
    const a = document.createElement('a')
    a.href = URL.createObjectURL(
      new Blob([code.source], { type: 'text/plain' }))
    a.download = `derivative.${ext}`
    a.click()
    URL.revokeObjectURL(a.href)
  }, [code])

  return (
    <div style={S.app}>
      <header style={S.header}>
        <span style={S.title}>Instantiation</span>
        <span style={S.meta}>
          {GRAPH_IRI || 'default model'}
          {VARS_IRI ? ` · vars ${VARS_IRI}` : ''}
        </span>
        {dirty && <span style={S.badge('#f59e0b')}>● unsaved</span>}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <select
            style={S.select}
            value={target}
            onChange={(e) => setTarget(e.target.value as Target)}
          >
            {TARGETS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button style={S.btn(true)} onClick={generate} disabled={busy}>
            {busy ? '…' : 'Generate code'}
          </button>
          <button style={S.btn(false)} onClick={() => saveStore()}>
            Save
          </button>
        </div>
      </header>

      <div style={S.main}>
        <div>
          {err && (
            <div style={{ ...S.card, borderColor: '#dc2626' }}>
              <h3 style={{ ...S.h3, color: '#dc2626' }}>Report failed</h3>
              <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap' }}>{err}</pre>
            </div>
          )}
          {report && <Problems report={report} />}
          {report?.entity_types.map((e) => (
            <EntityCard key={e.entity_type} e={e} lab={lab} />
          ))}
        </div>

        <div>
          {report && (
            <SolveCard report={report} lab={lab} />
          )}
          {report && (
            <ValuesCard
              report={report}
              lab={lab}
              onSaved={() => {
                loadReport().then(setReport).catch(() => {})
              }}
            />
          )}
          {report && report.ports.length > 0 && (
            <div style={S.card}>
              <h3 style={S.h3}>Ports</h3>
              <table style={S.table}>
                <thead>
                  <tr>
                    <th style={S.th}>port</th>
                    <th style={S.th}>status</th>
                    <th style={S.th}>peer</th>
                  </tr>
                </thead>
                <tbody>
                  {report.ports.map((p, i) => (
                    <tr key={i}>
                      <td style={S.td}>{lab(p.var)} @ {lab(p.node)}</td>
                      <td style={S.td}>
                        <span style={S.badge(
                          p.status === 'bound' ? '#059669' : '#dc2626')}>
                          {p.status}
                        </span>
                      </td>
                      <td style={S.td}>{lab(p.peer_var)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {report && report.schedule.levels.length > 0 && (
            <div style={S.card}>
              <h3 style={S.h3}>Schedule</h3>
              {report.schedule.levels.map((lvl, i) => (
                <div key={i} style={{ fontSize: 12, padding: '3px 0' }}>
                  <span style={{ color: '#888' }}>level {i}:</span>{' '}
                  {lvl.map((b) => (
                    <span key={b.equation} style={{ fontFamily: 'monospace' }}>
                      {lab(b.lhs)}
                      {b.loop >= 0 && (
                        <span style={S.badge('#dc2626')}> loop{b.loop}</span>
                      )}{' '}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          )}

          {code && (
            <div style={S.card}>
              <h3 style={S.h3}>
                {code.target}
                {code.ok && (
                  <span style={{ float: 'right', display: 'flex', gap: 6 }}>
                    <button style={S.btn(false)} onClick={copy}>copy</button>
                    <button style={S.btn(false)} onClick={download}>
                      download
                    </button>
                  </span>
                )}
              </h3>
              {code.ok
                ? <pre style={S.pre}>{code.source}</pre>
                : (
                  <pre style={{ ...S.pre, background: '#7f1d1d' }}>
                    {code.error}
                  </pre>
                )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
