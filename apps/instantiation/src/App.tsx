import { useCallback, useEffect, useState } from 'react'
import {
  generateCode,
  GRAPH_IRI,
  loadReport,
  saveStore,
  VARS_IRI,
} from './api'
import type {
  CodeOut,
  EntityInstantiation,
  InstantiationReport,
} from './types'
import { useStoreDirty } from './useStoreDirty'

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
                  .map(([i, els]) => `${lab(i)}[${els.length}]`)
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
