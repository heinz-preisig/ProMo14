import 'katex/dist/katex.min.css'
import { renderToString } from 'katex'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  deleteAssignment,
  evaluate,
  listAssignments,
  loadAssignment,
  loadContext,
  saveAssignment,
  saveStore,
} from './api'
import type {
  Assignment,
  BehaviourContext,
  Equation,
  EvaluateReport,
} from './types'
import { useStoreDirty } from '@promo/ui'

/** Short display form of an IRI: fragment after # or last /. */
function frag(iri: string): string {
  const h = iri.split('#')
  if (h.length > 1) return h[h.length - 1]
  const s = iri.split('/')
  return s[s.length - 1]
}

const btn: React.CSSProperties = {
  fontSize: 12,
  padding: '2px 8px',
  border: '1px solid #bbb',
  borderRadius: 4,
  background: '#fff',
  cursor: 'pointer',
}

const card: React.CSSProperties = {
  background: '#fff',
  border: '1px solid #ddd',
  borderRadius: 6,
  padding: '10px 14px',
  marginBottom: 12,
}

/** Inline KaTeX; falls back to monospace text when no latex is stored
 *  or rendering fails. */
function Tex({ latex, fallback }: { latex?: string | null; fallback: string }) {
  const html = useMemo(() => {
    if (!latex) return null
    try {
      return renderToString(latex, { throwOnError: true, displayMode: false })
    } catch {
      return null
    }
  }, [latex])
  if (html === null) return <code>{fallback}</code>
  return <span dangerouslySetInnerHTML={{ __html: html }} />
}

/** ``E_n: lhs := rhs`` — math when the backend supplied latex, else text. */
function EqLine({ eq, lhsLabel }: { eq: Equation; lhsLabel: string }) {
  return (
    <span>
      <Tex latex={eq.lhs_latex} fallback={lhsLabel} />
      {' := '}
      <Tex latex={eq.rhs_latex} fallback={eq.rhs} />
    </span>
  )
}

export default function App() {
  const [ctx, setCtx] = useState<BehaviourContext | null>(null)
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [entityType, setEntityType] = useState<string | null>(null)
  const [sequence, setSequence] = useState<string[]>([])
  const [baseEquation, setBaseEquation] = useState<string | null>(null)
  const [instantiated, setInstantiated] = useState<string[]>([])
  const [ports, setPorts] = useState<string[]>([])
  const [report, setReport] = useState<EvaluateReport | null>(null)
  const [labels, setLabels] = useState<Record<string, string>>({})
  const [saveMsg, setSaveMsg] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [dragIri, setDragIri] = useState<string | null>(null)
  const [dropTarget, setDropTarget] = useState<string | null>(null)
  const { dirty, refresh } = useStoreDirty()
  const evalTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const eqs = useMemo(() => {
    const m = new Map<string, Equation>()
    for (const e of ctx?.equations ?? []) m.set(e.iri, e)
    return m
  }, [ctx])

  const lab = useCallback(
    (iri: string | null | undefined) =>
      iri ? labels[iri] ?? frag(iri) : '—',
    [labels],
  )

  const eqName = useCallback(
    (iri: string) => {
      const e = eqs.get(iri)
      return e?.internal_id ?? frag(iri)
    },
    [eqs],
  )

  // -- data loading --------------------------------------------------------

  useEffect(() => {
    loadContext().then(setCtx).catch(() => setCtx(null))
    listAssignments().then(setAssignments).catch(() => {})
  }, [])

  // Selecting an entity type loads its stored assignment (if any).
  useEffect(() => {
    if (!entityType) return
    loadAssignment(entityType).then((a) => {
      setSequence(a?.sequence ?? [])
      setBaseEquation(a?.base_equation ?? null)
      setInstantiated(a?.instantiated ?? [])
      setPorts(a?.ports ?? [])
    })
  }, [entityType])

  // Every selection change re-evaluates (debounced) — the report drives
  // the whole UI: unresolved inputs, problems, closed flag.
  useEffect(() => {
    if (!entityType) return
    if (evalTimer.current) clearTimeout(evalTimer.current)
    evalTimer.current = setTimeout(() => {
      evaluate({
        entity_type: entityType,
        sequence,
        base_equation: baseEquation,
        instantiated,
        ports,
      })
        .then((r) => {
          setReport(r)
          setLabels((prev) => ({ ...prev, ...r.labels }))
        })
        .catch(() => setReport(null))
    }, 250)
    return () => {
      if (evalTimer.current) clearTimeout(evalTimer.current)
    }
  }, [entityType, sequence, baseEquation, instantiated, ports])

  // -- selection mutations ---------------------------------------------------

  /** Insert position for a resolver equation: just before its earliest
   *  non-base consumer (the base equation is exempt — §13). */
  const insertPos = useCallback(
    (forVar: string | null): number => {
      if (!forVar) return sequence.length
      let earliest = -1
      sequence.forEach((eqIri, i) => {
        if (eqIri === baseEquation) return
        const eq = eqs.get(eqIri)
        if (eq?.incidence.includes(forVar) && (earliest < 0 || i < earliest))
          earliest = i
      })
      return earliest < 0 ? sequence.length : earliest
    },
    [sequence, baseEquation, eqs],
  )

  const pickBase = (eqIri: string | null) => {
    setBaseEquation(eqIri)
    if (eqIri) {
      setSequence((s) => [eqIri, ...s.filter((e) => e !== eqIri)])
    }
  }

  const resolveWith = (varIri: string, eqIri: string) => {
    setSequence((s) => {
      if (s.includes(eqIri)) return s
      const at = insertPos(varIri)
      return [...s.slice(0, at), eqIri, ...s.slice(at)]
    })
  }

  const removeEq = (eqIri: string) => {
    setSequence((s) => s.filter((e) => e !== eqIri))
    if (eqIri === baseEquation) setBaseEquation(null)
  }

  const move = (eqIri: string, dir: -1 | 1) => {
    setSequence((s) => {
      const i = s.indexOf(eqIri)
      const j = i + dir
      if (i < 0 || j < 0 || j >= s.length) return s
      const next = [...s]
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }

  /** Drop `dragIri` onto `target`'s position (insert before it). */
  const dropOn = (target: string) => {
    if (!dragIri || dragIri === target) return
    setSequence((s) => {
      const from = s.indexOf(dragIri)
      const to = s.indexOf(target)
      if (from < 0 || to < 0) return s
      const next = s.filter((e) => e !== dragIri)
      next.splice(next.indexOf(target), 0, dragIri)
      return next
    })
  }

  const mark = (varIri: string, role: 'instantiated' | 'ports') => {
    const set = role === 'instantiated' ? setInstantiated : setPorts
    const other = role === 'instantiated' ? setPorts : setInstantiated
    set((s) => (s.includes(varIri) ? s : [...s, varIri]))
    other((s) => s.filter((v) => v !== varIri))
  }

  const unmark = (varIri: string) => {
    setInstantiated((s) => s.filter((v) => v !== varIri))
    setPorts((s) => s.filter((v) => v !== varIri))
  }

  // -- persistence -----------------------------------------------------------

  const save = async () => {
    if (!entityType) return
    try {
      await saveAssignment({
        entity_type: entityType,
        sequence,
        base_equation: baseEquation,
        instantiated,
        ports,
      })
      await saveStore()
      setSaveMsg('saved')
      refresh()
      listAssignments().then(setAssignments).catch(() => {})
    } catch (e) {
      setSaveMsg(`save failed: ${e}`)
    }
    setTimeout(() => setSaveMsg(''), 3000)
  }

  const remove = async () => {
    if (!entityType) return
    await deleteAssignment(entityType)
    setSequence([])
    setBaseEquation(null)
    setInstantiated([])
    setPorts([])
    listAssignments().then(setAssignments).catch(() => {})
    refresh()
  }

  // -- render ----------------------------------------------------------------

  const assignmentByType = useMemo(() => {
    const m = new Map<string, Assignment>()
    for (const a of assignments) m.set(a.entity_type, a)
    return m
  }, [assignments])

  const selectedType = ctx?.entity_types.find((t) => t.iri === entityType)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
          minHeight: 44,
          padding: '0 16px',
          background: '#fff',
          borderBottom: '1px solid #ddd',
        }}
      >
        <strong
          style={{
            fontSize: 14,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          Behaviour Linker
          {selectedType ? ` — ${selectedType.label}` : ''}
        </strong>
        <div
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          {report && entityType && (
            <span
              style={{
                fontSize: 12,
                color: report.closed ? '#0a7' : '#c80',
                fontWeight: 600,
              }}
            >
              {report.closed ? 'closed' : 'open'}
            </span>
          )}
          {dirty && (
            <span style={{ fontSize: 12, color: '#c80' }}>● unsaved</span>
          )}
          {saveMsg && <span style={{ fontSize: 12 }}>{saveMsg}</span>}
          <button style={btn} onClick={save} disabled={!entityType}>
            Save
          </button>
          <button style={btn} onClick={remove} disabled={!entityType}>
            Delete
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <aside
          style={{
            width: 240,
            borderRight: '1px solid #ddd',
            background: '#fafafa',
            overflowY: 'auto',
            padding: 8,
          }}
        >
          <div style={{ fontSize: 11, color: '#888', margin: '4px 4px 8px' }}>
            ENTITY TYPES
          </div>
          <input
            placeholder="filter…"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              fontSize: 12,
              padding: '3px 6px',
              marginBottom: 6,
              border: '1px solid #ccc',
              borderRadius: 4,
            }}
          />
          {(ctx?.entity_types ?? [])
            .filter(
              (t) =>
                !typeFilter ||
                t.label.toLowerCase().includes(typeFilter.toLowerCase()),
            )
            .map((t) => {
            const a = assignmentByType.get(t.iri)
            const active = t.iri === entityType
            return (
              <div
                key={t.iri}
                onClick={() => setEntityType(t.iri)}
                style={{
                  padding: '6px 8px',
                  marginBottom: 2,
                  borderRadius: 4,
                  cursor: 'pointer',
                  fontSize: 13,
                  background: active ? '#e3ecff' : 'transparent',
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 8,
                }}
              >
                <span>{t.label}</span>
                {a && (
                  <span
                    style={{
                      fontSize: 11,
                      color: a.closed ? '#0a7' : '#c80',
                    }}
                  >
                    {a.closed ? 'closed' : 'wip'}
                  </span>
                )}
              </div>
            )
          })}
        </aside>

        <main style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {!entityType && (
            <div style={{ color: '#888', fontSize: 13 }}>
              Select an entity type to link its behaviour.
            </div>
          )}

          {entityType && (
            <>
              {/* Base equation ------------------------------------------- */}
              <div style={card}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                  Base equation (state-defining)
                </div>
                <label
                  style={{ display: 'block', fontSize: 12, padding: '2px 0' }}
                >
                  <input
                    type="radio"
                    checked={baseEquation === null}
                    onChange={() => pickBase(null)}
                  />{' '}
                  <em>none — stateless entity (e.g. transport system)</em>
                </label>
                {(ctx?.equations ?? []).map((e) => (
                  <label
                    key={e.iri}
                    style={{
                      display: 'block',
                      fontSize: 12,
                      padding: '2px 0',
                    }}
                  >
                    <input
                      type="radio"
                      checked={baseEquation === e.iri}
                      onChange={() => pickBase(e.iri)}
                    />{' '}
                    <code>{eqName(e.iri)}</code>:{' '}
                    <EqLine eq={e} lhsLabel={lab(e.lhs)} />
                  </label>
                ))}
              </div>

              {/* Computation sequence ------------------------------------ */}
              <div style={card}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                  Computation sequence
                  {report?.state_variable && (
                    <span style={{ fontWeight: 400, color: '#666' }}>
                      {' '}
                      — state: {lab(report.state_variable)}
                    </span>
                  )}
                </div>
                {sequence.length === 0 && (
                  <div style={{ fontSize: 12, color: '#888' }}>
                    No equations selected yet.
                  </div>
                )}
                {sequence.map((eqIri, i) => {
                  const e = eqs.get(eqIri)
                  return (
                    <div
                      key={eqIri}
                      draggable
                      onDragStart={() => setDragIri(eqIri)}
                      onDragOver={(ev) => {
                        ev.preventDefault()
                        setDropTarget(eqIri)
                      }}
                      onDragLeave={() =>
                        setDropTarget((d) => (d === eqIri ? null : d))
                      }
                      onDrop={() => {
                        dropOn(eqIri)
                        setDragIri(null)
                        setDropTarget(null)
                      }}
                      onDragEnd={() => {
                        setDragIri(null)
                        setDropTarget(null)
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        fontSize: 12,
                        padding: '2px 4px',
                        cursor: 'grab',
                        borderTop:
                          dropTarget === eqIri && dragIri !== eqIri
                            ? '2px solid #06c'
                            : '2px solid transparent',
                        opacity: dragIri === eqIri ? 0.4 : 1,
                      }}
                    >
                      <span style={{ color: '#999', width: 18 }}>{i}</span>
                      <span style={{ flex: 1 }}>
                        <code>{eqName(eqIri)}</code>:{' '}
                        {e ? <EqLine eq={e} lhsLabel={lab(e.lhs)} /> : '?'}
                        {eqIri === baseEquation && (
                          <span style={{ color: '#06c' }}> (base)</span>
                        )}
                      </span>
                      <button style={btn} onClick={() => move(eqIri, -1)}>
                        ↑
                      </button>
                      <button style={btn} onClick={() => move(eqIri, 1)}>
                        ↓
                      </button>
                      <button style={btn} onClick={() => removeEq(eqIri)}>
                        ✕
                      </button>
                    </div>
                  )
                })}
              </div>

              {/* Unresolved inputs ---------------------------------------- */}
              <div style={card}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                  Unresolved inputs ({report?.unresolved.length ?? 0})
                </div>
                {(report?.unresolved ?? []).map((u) => (
                  <div
                    key={u.variable}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      flexWrap: 'wrap',
                      fontSize: 12,
                      padding: '3px 0',
                    }}
                  >
                    <code style={{ minWidth: 90 }}>{lab(u.variable)}</code>
                    {u.candidates.map((c) => {
                      const cand = eqs.get(c)
                      return (
                        <button
                          key={c}
                          style={btn}
                          title={cand?.rhs}
                          onClick={() => resolveWith(u.variable, c)}
                        >
                          + {eqName(c)}
                          {cand?.rhs_latex && (
                            <span style={{ marginLeft: 4, color: '#666' }}>
                              <Tex latex={cand.rhs_latex} fallback="" />
                            </span>
                          )}
                        </button>
                      )
                    })}
                    {u.candidates.length === 0 && (
                      <span style={{ color: '#999' }}>no defining eq</span>
                    )}
                    <button
                      style={btn}
                      onClick={() => mark(u.variable, 'instantiated')}
                    >
                      instantiate
                    </button>
                    <button
                      style={btn}
                      onClick={() => mark(u.variable, 'ports')}
                    >
                      port
                    </button>
                  </div>
                ))}
                {report && report.unresolved.length === 0 && (
                  <div style={{ fontSize: 12, color: '#0a7' }}>
                    all inputs resolved
                  </div>
                )}
              </div>

              {/* Roles ----------------------------------------------------- */}
              <div style={card}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                  Roles
                </div>
                <div style={{ fontSize: 12 }}>
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
                          onClick={() => unmark(v)}
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
                          onClick={() => unmark(v)}
                        >
                          ✕
                        </a>
                      </span>
                    ))}
                    {instantiated.length === 0 && '—'}
                  </div>
                  {(report?.auto_instantiated.length ?? 0) > 0 && (
                    <div>
                      <b>constants/parameters:</b>{' '}
                      {report!.auto_instantiated.map((u) => (
                        <span key={u.variable} style={{ marginRight: 8 }}>
                          <code>{lab(u.variable)}</code>
                          {u.candidates.map((c) => (
                            <button
                              key={c}
                              style={{ ...btn, marginLeft: 4 }}
                              title={`override: define via ${eqName(c)} — ${eqs.get(c)?.rhs ?? ''}`}
                              onClick={() => resolveWith(u.variable, c)}
                            >
                              + {eqName(c)}
                            </button>
                          ))}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Problems --------------------------------------------------- */}
              {report &&
                (report.cycles.length > 0 ||
                  report.conflicts.length > 0 ||
                  report.order_violations.length > 0 ||
                  report.warnings.length > 0) && (
                  <div style={{ ...card, borderColor: '#e0b0b0' }}>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        marginBottom: 6,
                        color: '#a00',
                      }}
                    >
                      Problems
                    </div>
                    {report.cycles.map((c, i) => (
                      <div key={i} style={{ fontSize: 12, color: '#a00' }}>
                        cycle: {c.map(eqName).join(' → ')}
                      </div>
                    ))}
                    {report.conflicts.map((c, i) => (
                      <div key={i} style={{ fontSize: 12, color: '#a00' }}>
                        {c.kind}: {lab(c.variable)} {c.detail}
                      </div>
                    ))}
                    {report.order_violations.map((v, i) => (
                      <div key={i} style={{ fontSize: 12, color: '#a00' }}>
                        order: {eqName(v.equation)} uses {lab(v.variable)}{' '}
                        defined later by {eqName(v.defined_by)}
                      </div>
                    ))}
                    {report.warnings.map((w, i) => (
                      <div key={i} style={{ fontSize: 12, color: '#c80' }}>
                        {w}
                      </div>
                    ))}
                  </div>
                )}
            </>
          )}
        </main>
      </div>
    </div>
  )
}
