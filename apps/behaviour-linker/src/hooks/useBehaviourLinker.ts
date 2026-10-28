import { renderToString } from 'katex'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  applyMove,
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
  Move,
  Selection,
} from '../types'
import { buildPrintableLatex, escapeHtml } from '../utils/latex'
import { frag } from '../utils/iri'
import { useStoreDirty } from '@promo/ui'

type EndpointRole = 'instantiated' | 'ports' | 'outputs'

export interface BehaviourLinkerState {
  ctx: BehaviourContext | null
  entityType: string | null
  sequence: string[]
  baseEquation: string | null
  baseMode: 'state' | 'stateless'
  instantiated: string[]
  ports: string[]
  outputs: string[]
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
  mark: (varIri: string, role: EndpointRole) => void
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
  const [outputs, setOutputs] = useState<string[]>([])
  const [report, setReport] = useState<EvaluateReport | null>(null)
  const [labels, setLabels] = useState<Record<string, string>>({})
  const [saveMsg, setSaveMsg] = useState('')
  const [copied, setCopied] = useState(false)
  const [showSource, setShowSource] = useState(false)
  const [typeFilter, setTypeFilter] = useState('')
  const [dragIri, setDragIri] = useState<string | null>(null)
  const [dropTarget, setDropTarget] = useState<string | null>(null)
  const { dirty, refresh } = useStoreDirty()
  // Moves are serialized — each posts the state the previous move
  // produced, so rapid clicks cannot interleave.
  const moveChain = useRef<Promise<void>>(Promise.resolve())

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

  const selRef = useRef<Selection>({
    entity_type: '',
    sequence: [],
    base_equation: null,
    instantiated: [],
    ports: [],
    outputs: [],
  })
  selRef.current = {
    entity_type: entityType ?? '',
    sequence,
    base_equation: baseEquation,
    instantiated,
    ports,
    outputs,
  }

  const applySelection = useCallback(
    (a: Assignment, syncMode = false) => {
      setSequence(a.sequence)
      setBaseEquation(a.base_equation)
      // Move responses keep the user's picker mode unless they carry
      // a base — loading an artefact resets it authoritatively.
      if (a.base_equation || syncMode) {
        setBaseMode(a.base_equation ? 'state' : 'stateless')
      }
      setInstantiated(a.instantiated)
      setPorts(a.ports)
      setOutputs(a.outputs ?? [])
    },
    [],
  )

  // -- data loading --------------------------------------------------------

  useEffect(() => {
    loadContext().then(setCtx).catch(() => setCtx(null))
    listAssignments().then(setAssignments).catch(() => {})
  }, [])

  // Selecting an entity type loads its stored assignment (if any), then
  // sends a `reorder` move with the stored order — the engine returns
  // the canonical §21 selection (pruned + topologically ordered) plus
  // the report in one roundtrip.  Falls back to plain evaluate if the
  // move channel is unavailable.
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
        outputs: [],
        closed: false,
      }
      applyMove({
        ...assignment,
        kind: 'reorder',
        sequence: assignment.sequence,
      })
        .then((r) => {
          applySelection(r.selection, true)
          setReport(r.report)
          setLabels((prev) => ({ ...prev, ...r.report.labels }))
          // The saved snapshot follows the reclosed form — a legacy
          // artefact shows "modified" iff the engine changed anything.
          setLastSaved(
            a
              ? {
                  ...a,
                  sequence: r.selection.sequence,
                  base_equation: r.selection.base_equation,
                  instantiated: r.selection.instantiated,
                  ports: r.selection.ports,
                  outputs: r.selection.outputs,
                }
              : null,
          )
        })
        .catch(() => {
          applySelection(assignment, true)
          setLastSaved(assignment)
          evaluate(assignment)
            .then((r) => {
              setReport(r)
              setLabels((prev) => ({ ...prev, ...r.labels }))
            })
            .catch(() => setReport(null))
        })
    })
  }, [entityType, applySelection])

  // -- §21 moves -----------------------------------------------------------

  const flash = useCallback((pulled: string[], pruned: string[]) => {
    const bits: string[] = []
    if (pulled.length)
      bits.push(`pulled ${pulled.map((e) => frag(e)).join(', ')}`)
    if (pruned.length)
      bits.push(`pruned ${pruned.map((e) => frag(e)).join(', ')}`)
    if (bits.length) {
      setSaveMsg(bits.join(' · '))
      setTimeout(() => setSaveMsg(''), 4000)
    }
  }, [])

  const queueMove = useCallback(
    (patch: Partial<Move> & Pick<Move, 'kind'>) => {
      moveChain.current = moveChain.current.then(async () => {
        try {
          const r = await applyMove({ ...selRef.current, ...patch })
          applySelection(r.selection)
          setReport(r.report)
          setLabels((prev) => ({ ...prev, ...r.report.labels }))
          flash(r.pulled, r.pruned)
        } catch {
          setSaveMsg('move rejected')
          setTimeout(() => setSaveMsg(''), 3000)
        }
      })
    },
    [applySelection, flash],
  )

  const pickBase = (eqIri: string | null) =>
    queueMove({ kind: 'pick_base', equation: eqIri })

  const resolveWith = (varIri: string, eqIri: string) =>
    queueMove({ kind: 'pick', variable: varIri, equation: eqIri })

  const removeEq = (eqIri: string) =>
    queueMove({ kind: 'delete', equation: eqIri })

  const move = (eqIri: string, dir: -1 | 1) => {
    const s = selRef.current.sequence
    const i = s.indexOf(eqIri)
    const j = i + dir
    if (i < 0 || j < 0 || j >= s.length) return
    const desired = [...s]
    ;[desired[i], desired[j]] = [desired[j], desired[i]]
    queueMove({ kind: 'reorder', sequence: desired })
  }

  const dropOn = (target: string) => {
    const s = selRef.current.sequence
    if (!dragIri || dragIri === target) return
    const from = s.indexOf(dragIri)
    const to = s.indexOf(target)
    if (from < 0 || to < 0) return
    const desired = s.filter((e) => e !== dragIri)
    desired.splice(desired.indexOf(target), 0, dragIri)
    queueMove({ kind: 'reorder', sequence: desired })
  }

  const mark = (varIri: string, role: EndpointRole) =>
    queueMove({ kind: 'mark', variable: varIri, role })

  const unmark = (varIri: string) =>
    queueMove({ kind: 'unmark', variable: varIri })

  // -- persistence ---------------------------------------------------------

  const save = async () => {
    if (!entityType) return
    if (
      sequence.length === 0 &&
      !baseEquation &&
      instantiated.length === 0 &&
      ports.length === 0 &&
      outputs.length === 0
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
        outputs,
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
    setOutputs([])
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
        ports.length > 0 ||
        outputs.length > 0
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
    if (!eqSet(lastSaved.outputs ?? [], outputs)) return true
    return false
  }, [
    entityType,
    lastSaved,
    sequence,
    baseEquation,
    instantiated,
    ports,
    outputs,
  ])

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
        outputs,
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
    outputs,
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
    outputs,
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
