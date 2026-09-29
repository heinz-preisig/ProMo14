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
  EntityType,
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

/** Escape plain text so it is safe inside a LaTeX math \text{...} block. */
function texEscape(s: string): string {
  return s
    .replace(/\\/g, '\\textbackslash{}')
    .replace(/&/g, '\\&')
    .replace(/%/g, '\\%')
    .replace(/#/g, '\\#')
    .replace(/_/g, '\\_')
    .replace(/\{/g, '\\{')
    .replace(/\}/g, '\\}')
    .replace(/\$/g, '\\$')
    .replace(/~/g, '\\textasciitilde{}')
    .replace(/\^/g, '\\textasciicircum{}')
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
  const [baseMode, setBaseMode] = useState<'state' | 'stateless'>('stateless')
  const [lastSaved, setLastSaved] = useState<Assignment | null>(null)
  const [instantiated, setInstantiated] = useState<string[]>([])
  const [ports, setPorts] = useState<string[]>([])
  const [report, setReport] = useState<EvaluateReport | null>(null)
  const [labels, setLabels] = useState<Record<string, string>>({})
  const [saveMsg, setSaveMsg] = useState('')
  const [copied, setCopied] = useState(false)
  const [showSource, setShowSource] = useState(false)
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

  /** Readable handle for an equation in problem messages: the label of
   *  the variable it defines (internal ids are bookkeeping, not shown). */
  const eqLhs = useCallback(
    (iri: string) => {
      const e = eqs.get(iri)
      return e ? lab(e.lhs) : frag(iri)
    },
    [eqs, lab],
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
      const assignment = a ?? {
        entity_type: entityType,
        sequence: [],
        base_equation: null,
        state_variable: null,
        instantiated: [],
        ports: [],
        closed: false,
      }
      setSequence(assignment.sequence)
      setBaseEquation(assignment.base_equation)
      setBaseMode(assignment.base_equation ? 'state' : 'stateless')
      setInstantiated(assignment.instantiated)
      setPorts(assignment.ports)
      setLastSaved(assignment)
    })
  }, [entityType])

  // Keep the base-equation mode selector aligned with the actual selection.
  useEffect(() => {
    if (baseEquation) setBaseMode('state')
  }, [baseEquation])

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
    if (
      sequence.length === 0 &&
      !baseEquation &&
      instantiated.length === 0 &&
      ports.length === 0
    ) {
      setSaveMsg('nothing to save')
      setTimeout(() => setSaveMsg(''), 3000)
      return
    }
    try {
      const saved = await saveAssignment({
        entity_type: entityType,
        sequence,
        base_equation: baseEquation,
        instantiated,
        ports,
      })
      await saveStore()
      setLastSaved(saved)
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
    await saveStore()
    setSequence([])
    setBaseEquation(null)
    setInstantiated([])
    setPorts([])
    setLastSaved(null)
    listAssignments().then(setAssignments).catch(() => {})
    refresh()
  }

  // -- render ----------------------------------------------------------------

  const assignmentByType = useMemo(() => {
    const m = new Map<string, Assignment>()
    for (const a of assignments) m.set(a.entity_type, a)
    return m
  }, [assignments])

  const hasUnsavedChanges = useMemo(() => {
    if (!entityType) return false
    if (!lastSaved) {
      return (
        sequence.length > 0 ||
        baseEquation !== null ||
        instantiated.length > 0 ||
        ports.length > 0
      )
    }
    if (lastSaved.base_equation !== baseEquation) return true
    if (JSON.stringify(lastSaved.sequence) !== JSON.stringify(sequence))
      return true
    const eqSet = (a: string[], b: string[]) => {
      const sa = [...a].sort()
      const sb = [...b].sort()
      return JSON.stringify(sa) === JSON.stringify(sb)
    }
    if (!eqSet(lastSaved.instantiated, instantiated)) return true
    if (!eqSet(lastSaved.ports, ports)) return true
    return false
  }, [entityType, lastSaved, sequence, baseEquation, instantiated, ports])

  const selectedType = ctx?.entity_types.find((t) => t.iri === entityType)

  /** Render-ready LaTeX for the current entity assignment. */
  const printableLatex = useMemo(() => {
    if (!entityType || !report) return ''
    const esc = texEscape
    const header: string[] = []
    header.push(
      `\\text{Entity: ${esc(selectedType?.label ?? frag(entityType))}}`,
    )
    if (report.state_variable) {
      header.push(`\\text{state: } ${esc(lab(report.state_variable))}`)
    }
    const eqLines = sequence
      .map((eqIri) => {
        const e = eqs.get(eqIri)
        if (!e) return ''
        const marker = eqIri === baseEquation ? ' \\text{(base)}' : ''
        const lhs = e.lhs_latex ?? esc(lab(e.lhs))
        const rhs = e.rhs_latex ?? ''
        return `${lhs} = ${rhs}${marker}`
      })
      .filter(Boolean)
    const meta: string[] = []
    if (instantiated.length > 0) {
      meta.push(
        `\\text{instantiated: } ${instantiated
          .map((v) => esc(lab(v)))
          .join(', ')}`,
      )
    }
    if (ports.length > 0) {
      meta.push(
        `\\text{ports: } ${ports.map((v) => esc(lab(v))).join(', ')}`,
      )
    }
    const all = [...header, ...eqLines, ...meta]
    if (all.length === 0) return ''
    const eqBlockEnd = header.length + eqLines.length - 1
    return `\\begin{gathered}\n${all
      .map((l, i) => {
        const br =
          eqLines.length > 0 && meta.length > 0 && i === eqBlockEnd
            ? '\\\\[6pt]'
            : '\\\\'
        return `  ${l} ${br}`
      })
      .join('\n')}\n\\end{gathered}`
  }, [
    entityType,
    report,
    selectedType,
    baseEquation,
    sequence,
    instantiated,
    ports,
    eqs,
    lab,
  ])

  const copyLatex = async () => {
    if (!printableLatex) return
    try {
      await navigator.clipboard.writeText(printableLatex)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // ignore
    }
  }

  const printRepresentation = () => {
    if (!previewHtml || !entityType) return
    const title = selectedType?.label ?? frag(entityType)
    const w = window.open('', `print-${entityType}`, 'width=800,height=600')
    if (!w) return
    const styles = Array.from(
      document.querySelectorAll('link[rel="stylesheet"], style'),
    )
      .map((el) => el.outerHTML)
      .join('')
    w.document.write(`<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Behaviour Linker — ${title}</title>
    ${styles}
    <style>
      body { font-family: sans-serif; padding: 24px; }
      pre { white-space: pre-wrap; background: #f5f5f5; padding: 12px; border-radius: 4px; }
    </style>
  </head>
  <body>
    <h1>${title}</h1>
    <div>${previewHtml}</div>
    <h2>LaTeX source</h2>
    <pre>${printableLatex
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')}</pre>
  </body>
</html>`)
    w.document.close()
    w.focus()
    setTimeout(() => w.print(), 400)
  }

  const previewHtml = useMemo(() => {
    if (!printableLatex) return ''
    try {
      return renderToString(printableLatex, {
        displayMode: true,
        throwOnError: false,
      })
    } catch {
      return ''
    }
  }, [printableLatex])

  /** Sidebar order follows the ontology's promo:parent hierarchy —
   *  roots (sorted by branch then label) first, children indented
   *  beneath their parent.  Orphaned parents fall back to root. */
  const orderedTypes = useMemo(() => {
    const all = ctx?.entity_types ?? []
    const byParent = new Map<string | null, EntityType[]>()
    for (const t of all) {
      const p = t.parent && all.some((x) => x.iri === t.parent)
        ? t.parent
        : null
      byParent.set(p, [...(byParent.get(p) ?? []), t])
    }
    const key = (t: EntityType) =>
      `${t.branch}\n${t.label.toLowerCase()}`
    for (const l of byParent.values())
      l.sort((a, b) => key(a).localeCompare(key(b)))
    const out: { t: EntityType; depth: number }[] = []
    const visit = (p: string | null, d: number) => {
      for (const t of byParent.get(p) ?? []) {
        out.push({ t, depth: d })
        visit(t.iri, d + 1)
      }
    }
    visit(null, 0)
    return out
  }, [ctx])

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
                fontSize: 13,
                color: report.closed ? '#0a7' : '#c80',
                fontWeight: 600,
              }}
            >
              {report.closed ? 'closed' : 'open'}
            </span>
          )}
          {dirty && (
            <span style={{ fontSize: 13, color: '#c80' }}>● unsaved</span>
          )}
          {hasUnsavedChanges && (
            <span style={{ fontSize: 13, color: '#c00' }}>● modified</span>
          )}
          {saveMsg && <span style={{ fontSize: 13 }}>{saveMsg}</span>}
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
          <div style={{ fontSize: 12, color: '#888', margin: '4px 4px 8px' }}>
            ENTITY TYPES
          </div>
          <input
            placeholder="filter…"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{
              width: '100%',
              boxSizing: 'border-box',
              fontSize: 13,
              padding: '3px 6px',
              marginBottom: 6,
              border: '1px solid #ccc',
              borderRadius: 4,
            }}
          />
          {(typeFilter
            ? orderedTypes
                .filter(({ t }) =>
                  t.label
                    .toLowerCase()
                    .includes(typeFilter.toLowerCase()))
                .map(({ t }) => ({ t, depth: 0 }))
            : orderedTypes
          ).map(({ t, depth }) => {
            const a = assignmentByType.get(t.iri)
            const active = t.iri === entityType
            return (
              <div
                key={t.iri}
                onClick={() => setEntityType(t.iri)}
                style={{
                  padding: '6px 8px',
                  paddingLeft: 8 + depth * 14,
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
                      fontSize: 12,
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
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Base equation
                </div>
                {(() => {
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
                              onChange={() => pickBase(e.iri)}
                            />{' '}
                            <EqLine eq={e} lhsLabel={lab(e.lhs)} />
                          </label>
                        ))}
                      </div>
                    )
                  return (
                    <div style={{ fontSize: 13 }}>
                      <label style={{ display: 'block', padding: '2px 0' }}>
                        <input
                          type="radio"
                          checked={baseMode === 'state'}
                          disabled={allEqs.length === 0}
                          onChange={() => setBaseMode('state')}
                        />{' '}
                        with state
                      </label>
                      {baseMode === 'state' && (
                        <div style={{ marginLeft: 16 }}>
                          {renderGroup('suggested state equations', stateEqs)}
                          {renderGroup('other equations', otherEqs)}
                        </div>
                      )}
                      <label style={{ display: 'block', padding: '2px 0' }}>
                        <input
                          type="radio"
                          checked={baseMode === 'stateless'}
                          onChange={() => {
                            setBaseMode('stateless')
                            pickBase(null)
                          }}
                        />{' '}
                        without state
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
                              onChange={() => pickBase(null)}
                            />{' '}
                            <em>none — entity without state</em>
                          </label>
                        </div>
                      )}
                    </div>
                  )
                })()}
              </div>

              {/* Computation sequence ------------------------------------ */}
              <div style={card}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Computation sequence
                  {report?.state_variable && (
                    <span style={{ fontWeight: 400, color: '#666' }}>
                      {' '}
                      — state: {lab(report.state_variable)}
                    </span>
                  )}
                </div>
                {sequence.length === 0 && (
                  <div style={{ fontSize: 13, color: '#888' }}>
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
                        fontSize: 13,
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

              {/* Suggested next equations ---------------------------------- */}
              <div style={card}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Suggested next equations
                </div>
                {(report?.frontier ?? []).length === 0 && (
                  <div style={{ fontSize: 13, color: '#888' }}>
                    No further equations needed.
                  </div>
                )}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {(report?.frontier ?? []).map((eqIri) => {
                    const e = eqs.get(eqIri)
                    if (!e) return null
                    return (
                      <button
                        key={eqIri}
                        style={btn}
                        title={e.rhs}
                        onClick={() => resolveWith(e.lhs, eqIri)}
                      >
                        + <EqLine eq={e} lhsLabel={lab(e.lhs)} />
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Unresolved inputs ---------------------------------------- */}
              <div style={card}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
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
                      fontSize: 13,
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
                          +{' '}
                          {cand ? (
                            <EqLine eq={cand} lhsLabel={lab(cand.lhs)} />
                          ) : (
                            frag(c)
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
                  <div style={{ fontSize: 13, color: '#0a7' }}>
                    all inputs resolved
                  </div>
                )}
              </div>

              {/* Roles ----------------------------------------------------- */}
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
                          {u.candidates.map((c) => {
                            const cand = eqs.get(c)
                            return (
                              <button
                                key={c}
                                style={{ ...btn, marginLeft: 4 }}
                                title={`override: define via ${cand?.rhs ?? ''}`}
                                onClick={() => resolveWith(u.variable, c)}
                              >
                                +{' '}
                                {cand ? (
                                  <EqLine
                                    eq={cand}
                                    lhsLabel={lab(cand.lhs)}
                                  />
                                ) : (
                                  frag(c)
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
                        if (e.target.value)
                          mark(e.target.value, 'instantiated')
                      }}
                    >
                      <option value="">instantiate…</option>
                      {(ctx?.variables ?? []).map((v) => (
                        <option key={v.iri} value={v.iri}>
                          {v.label}
                        </option>
                      ))}
                    </select>{' '}
                    <select
                      style={{ fontSize: 13 }}
                      value=""
                      onChange={(e) => {
                        if (e.target.value) mark(e.target.value, 'ports')
                      }}
                    >
                      <option value="">port…</option>
                      {(ctx?.variables ?? []).map((v) => (
                        <option key={v.iri} value={v.iri}>
                          {v.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Printable representation ---------------------------------- */}
              {printableLatex && (
                <div style={card}>
                  <div
                    style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}
                  >
                    Printable representation
                  </div>
                  {previewHtml && (
                    <div
                      style={{ marginBottom: 8, overflowX: 'auto' }}
                      dangerouslySetInnerHTML={{ __html: previewHtml }}
                    />
                  )}
                  <div
                    style={{ display: 'flex', gap: 8, alignItems: 'center' }}
                  >
                    <button style={btn} onClick={copyLatex}>
                      Copy LaTeX
                    </button>
                    <button style={btn} onClick={printRepresentation}>
                      Print
                    </button>
                    <button
                      style={btn}
                      onClick={() => setShowSource((s) => !s)}
                    >
                      {showSource ? 'Hide source' : 'Show source'}
                    </button>
                    {copied && (
                      <span style={{ fontSize: 12, color: '#0a7' }}>
                        copied
                      </span>
                    )}
                  </div>
                  {showSource && (
                    <pre
                      style={{
                        fontSize: 12,
                        background: '#f5f5f5',
                        padding: 8,
                        borderRadius: 4,
                        overflowX: 'auto',
                        marginTop: 8,
                      }}
                    >
                      {printableLatex}
                    </pre>
                  )}
                </div>
              )}

              {/* Problems --------------------------------------------------- */}
              {report &&
                (report.cycles.length > 0 ||
                  report.conflicts.length > 0 ||
                  report.order_violations.length > 0 ||
                  report.warnings.length > 0) && (
                  <div style={{ ...card, borderColor: '#e0b0b0' }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        marginBottom: 6,
                        color: '#a00',
                      }}
                    >
                      Problems
                    </div>
                    {report.cycles.map((c, i) => (
                      <div key={i} style={{ fontSize: 13, color: '#a00' }}>
                        cycle: {c.map(eqLhs).join(' → ')}
                      </div>
                    ))}
                    {report.conflicts.map((c, i) => (
                      <div key={i} style={{ fontSize: 13, color: '#a00' }}>
                        {c.kind}: {lab(c.variable)} {c.detail}
                      </div>
                    ))}
                    {report.order_violations.map((v, i) => (
                      <div key={i} style={{ fontSize: 13, color: '#a00' }}>
                        order: {eqLhs(v.equation)} uses {lab(v.variable)}{' '}
                        defined later by {eqLhs(v.defined_by)}
                      </div>
                    ))}
                    {report.warnings.map((w, i) => (
                      <div key={i} style={{ fontSize: 13, color: '#c80' }}>
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
