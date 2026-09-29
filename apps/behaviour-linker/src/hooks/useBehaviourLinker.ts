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
} from '../api'
import type {
  Assignment,
  BehaviourContext,
  EntityType,
  Equation,
  EvaluateReport,
} from '../types'
import { buildPrintableLatex, escapeHtml } from '../utils/latex'
import { frag } from '../utils/iri'
import { useStoreDirty } from '@promo/ui'

export interface BehaviourLinkerState {
  ctx: BehaviourContext | null
  entityType: string | null
  sequence: string[]
  baseEquation: string | null
  baseMode: 'state' | 'stateless'
  instantiated: string[]
  ports: string[]
  report: EvaluateReport | null
  saveMsg: string
  copied: boolean
  showSource: boolean
  typeFilter: string
  dragIri: string | null
  dropTarget: string | null
  dirty: boolean
  hasUnsavedChanges: boolean
  title: string
  orderedTypes: { t: EntityType; depth: number }[]
  assignmentByType: Map<string, Assignment>
  previewHtml: string
  printableLatex: string
  eqs: Map<string, Equation>
  lab: (iri: string | null | undefined) => string
  eqLhs: (iri: string) => string
  setEntityType: (iri: string) => void
  setTypeFilter: (value: string) => void
  setDragIri: React.Dispatch<React.SetStateAction<string | null>>
  setDropTarget: React.Dispatch<React.SetStateAction<string | null>>
  setShowSource: React.Dispatch<React.SetStateAction<boolean>>
  setBaseMode: React.Dispatch<React.SetStateAction<'state' | 'stateless'>>
  pickBase: (eqIri: string | null) => void
  resolveWith: (varIri: string, eqIri: string) => void
  removeEq: (eqIri: string) => void
  move: (eqIri: string, dir: -1 | 1) => void
  dropOn: (target: string) => void
  mark: (varIri: string, role: 'instantiated' | 'ports') => void
  unmark: (varIri: string) => void
  save: () => Promise<void>
  remove: () => Promise<void>
  copyLatex: () => Promise<void>
  printRepresentation: () => void
}

export function useBehaviourLinker(): BehaviourLinkerState {
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

  // Selecting an entity type loads its stored assignment (if any) and
  // normalises the base equation to the end of the sequence.
  useEffect(() => {
    if (!entityType) return
    loadAssignment(entityType).then((a) => {
      let assignment = a ?? {
        entity_type: entityType,
        sequence: [],
        base_equation: null,
        state_variable: null,
        instantiated: [],
        ports: [],
        closed: false,
      }
      if (
        assignment.base_equation &&
        assignment.sequence.indexOf(assignment.base_equation) !==
          assignment.sequence.length - 1
      ) {
        assignment = {
          ...assignment,
          sequence: [
            ...assignment.sequence.filter((e) => e !== assignment.base_equation),
            assignment.base_equation,
          ],
        }
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

  // Every selection change re-evaluates (debounced).
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

  // -- selection mutations -------------------------------------------------

  const insertPos = useCallback(
    (forVar: string | null): number => {
      if (!forVar) return sequence.length
      const baseIdx = baseEquation ? sequence.indexOf(baseEquation) : -1
      if (
        baseIdx >= 0 &&
        baseEquation &&
        eqs.get(baseEquation)?.incidence.includes(forVar)
      ) {
        return baseIdx
      }
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
      setSequence((s) => [...s.filter((e) => e !== eqIri), eqIri])
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

  // -- persistence ---------------------------------------------------------

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

  // -- derived state -------------------------------------------------------

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

  const printableLatex = useMemo(() => {
    if (!entityType || !report) return ''
    return buildPrintableLatex({
      entityType,
      entityLabel: selectedType?.label ?? null,
      report,
      assignment: {
        sequence,
        base_equation: baseEquation,
        instantiated,
        ports,
      },
      eqs,
      lab,
    })
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
    const safeTitle = escapeHtml(title)
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
    <title>Behaviour Linker — ${safeTitle}</title>
    ${styles}
    <style>
      body { font-family: sans-serif; padding: 24px; }
      pre { white-space: pre-wrap; background: #f5f5f5; padding: 12px; border-radius: 4px; }
    </style>
  </head>
  <body>
    <h1>${safeTitle}</h1>
    <div>${previewHtml}</div>
    <h2>LaTeX source</h2>
    <pre>${escapeHtml(printableLatex)}</pre>
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

  const orderedTypes = useMemo(() => {
    const all = ctx?.entity_types ?? []
    const byParent = new Map<string | null, EntityType[]>()
    for (const t of all) {
      const p =
        t.parent && all.some((x) => x.iri === t.parent) ? t.parent : null
      byParent.set(p, [...(byParent.get(p) ?? []), t])
    }
    const key = (t: EntityType) => `${t.branch}\n${t.label.toLowerCase()}`
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

  const title = `Behaviour Linker${selectedType ? ` — ${selectedType.label}` : ''}`

  return {
    ctx,
    entityType,
    sequence,
    baseEquation,
    baseMode,
    instantiated,
    ports,
    report,
    saveMsg,
    copied,
    showSource,
    typeFilter,
    dragIri,
    dropTarget,
    dirty,
    hasUnsavedChanges,
    title,
    orderedTypes,
    assignmentByType,
    previewHtml,
    printableLatex,
    eqs,
    lab,
    eqLhs,
    setEntityType,
    setTypeFilter,
    setDragIri,
    setDropTarget,
    setShowSource,
    setBaseMode,
    pickBase,
    resolveWith,
    removeEq,
    move,
    dropOn,
    mark,
    unmark,
    save,
    remove,
    copyLatex,
    printRepresentation,
  }
}
