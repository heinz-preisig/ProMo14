import { useEffect, useState } from 'react'
import type { Index, NetworkTree, Variable } from '../types'
import { indexShortLabel } from '../latex'
import { useVariableLock } from '../useVariableLock'
import { VARIABLE_CLASSES } from '../validation'
import NetworkTreeSelect from './NetworkTreeSelect'

const UNIT_LABELS = ['time', 'length', 'amount', 'mass', 'temperature', 'current', 'light', 'nil']

export interface VariableDetailDialogProps {
  variable: Variable
  indices: Index[]
  networkTree: NetworkTree
  /** Persist the edited variable (POST /variables). Throws on failure. */
  onSave: (v: Variable) => Promise<void>
  /** Open the equation editor to attach another equation (§18). */
  onAddEquation?: (v: Variable) => void
  onClose: () => void
}

/** Variable detail + edit dialog.
 *
 *  Mutability policy (design doc §18): label, LaTeX alias and doc are
 *  always editable; structural fields (network, class, units, index
 *  structures) are locked while an equation references the variable —
 *  the backend enforces the same rule with a 409, this lock is the
 *  proactive half. */
export default function VariableDetailDialog({
  variable,
  indices,
  networkTree,
  onSave,
  onAddEquation,
  onClose,
}: VariableDetailDialogProps) {
  const [label, setLabel] = useState(variable.label)
  const [latexSym, setLatexSym] = useState(variable.aliases?.latex ?? '')
  const [doc, setDoc] = useState(variable.doc ?? '')
  const [network, setNetwork] = useState(variable.network)
  const [variableClass, setVariableClass] = useState(variable.type ?? '')
  const [units, setUnits] = useState<number[]>(variable.units ?? [0, 0, 0, 0, 0, 0, 0, 0])
  const [selectedIndices, setSelectedIndices] = useState<Set<string>>(
    new Set(variable.index_structures ?? []),
  )
  const [msg, setMsg] = useState('')
  // §18 usage lock — structural fields grey out while referenced.
  const { count: refCount } = useVariableLock(variable.iri)

  // Reinitialise + refresh the usage lock whenever another variable is shown.
  useEffect(() => {
    setLabel(variable.label)
    setLatexSym(variable.aliases?.latex ?? '')
    setDoc(variable.doc ?? '')
    setNetwork(variable.network)
    setVariableClass(variable.type ?? '')
    setUnits(variable.units ?? [0, 0, 0, 0, 0, 0, 0, 0])
    setSelectedIndices(new Set(variable.index_structures ?? []))
    setMsg('')
  }, [variable])

  const locked = (refCount ?? 0) > 0
  const canSave = label.trim() && network && variableClass

  const toggleIndex = (iri: string) => {
    setSelectedIndices((prev) => {
      const next = new Set(prev)
      if (next.has(iri)) next.delete(iri)
      else next.add(iri)
      return next
    })
  }

  /** The variable as currently edited — shared by Save, the equation
   *  check and Add equation so all see the same record. */
  const draftVariable = (): Variable => {
    const aliases = { ...(variable.aliases ?? {}) }
    if (latexSym.trim()) aliases.latex = latexSym.trim()
    else delete aliases.latex
    return {
      ...variable,
      label: label.trim(),
      network,
      type: variableClass,
      units: [...units],
      index_structures: Array.from(selectedIndices),
      aliases,
      doc: doc.trim(),
    }
  }

  const handleSave = async () => {
    if (!canSave) return
    try {
      await onSave(draftVariable())
      setMsg('Saved')
      setTimeout(() => setMsg(''), 3000)
    } catch (err) {
      setMsg(`Save failed: ${err instanceof Error ? err.message : err}`)
    }
  }

  const storedEqs = Object.entries(variable.equations ?? {})

  // Locked structural controls: render but inert.
  const lockStyle: React.CSSProperties = locked
    ? { pointerEvents: 'none', opacity: 0.55 }
    : {}

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        style={{
          width: 480,
          maxHeight: '85vh',
          background: '#fff',
          borderRadius: 6,
          padding: 20,
          boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          overflowY: 'auto',
          fontSize: 13,
        }}
      >
        <h3 style={{ margin: 0 }}>Variable</h3>
        <div style={{ fontSize: 12, color: '#888' }}>{variable.iri}</div>

        {locked && (
          <div
            style={{
              fontSize: 12,
              color: '#8d6e00',
              background: '#fff8e1',
              border: '1px solid #ffe082',
              borderRadius: 4,
              padding: '6px 8px',
            }}
          >
            Referenced by {refCount} equation(s) — network, class, units and
            index structures are locked. Name, LaTeX and documentation stay
            editable.
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            Name <span style={{ color: '#c62828' }}>*</span>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            LaTeX symbol
            <input
              type="text"
              value={latexSym}
              onChange={(e) => setLatexSym(e.target.value)}
              placeholder="e.g. \\rho — defaults to the name"
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            Documentation
            <textarea
              value={doc}
              onChange={(e) => setDoc(e.target.value)}
              rows={3}
              style={{ resize: 'vertical', fontFamily: 'inherit' }}
            />
          </label>

          <div style={lockStyle}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              Domain / network <span style={{ color: '#c62828' }}>*</span>
              <NetworkTreeSelect tree={networkTree} selected={network} onSelect={setNetwork} />
            </label>
          </div>

          <div style={lockStyle}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              Variable class <span style={{ color: '#c62828' }}>*</span>
              <select
                value={variableClass}
                onChange={(e) => setVariableClass(e.target.value)}
                disabled={locked}
              >
                <option value="">Select a class…</option>
                {VARIABLE_CLASSES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, ...lockStyle }}>
            <span>Units (SI vector)</span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
              {UNIT_LABELS.map((name, i) => (
                <label key={name} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontSize: 10, color: '#666' }}>{name}</span>
                  <input
                    type="number"
                    step="1"
                    value={units[i]}
                    disabled={locked}
                    onChange={(e) => {
                      const next = [...units]
                      next[i] = Number(e.target.value)
                      setUnits(next)
                    }}
                    style={{ width: '100%' }}
                  />
                </label>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, ...lockStyle }}>
            <span>Index structures</span>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                maxHeight: 120,
                overflowY: 'auto',
                border: '1px solid #ccc',
                borderRadius: 4,
                padding: 8,
              }}
            >
              {indices.map((i) => (
                <label key={i.iri} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input
                    type="checkbox"
                    checked={selectedIndices.has(i.iri)}
                    disabled={locked}
                    onChange={() => toggleIndex(i.iri)}
                  />
                  <span>
                    {i.label} ({i.aliases?.internal_code ?? i.iri})
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div style={{ fontSize: 12, color: '#555' }}>
            <strong>Port variable:</strong> {variable.port_variable ? 'yes' : 'no'} ·{' '}
            <strong>Index structures:</strong>{' '}
            {variable.index_structures
              ?.map((iri) => {
                const idx = indices.find((i) => i.iri === iri)
                return idx ? `${indexShortLabel(idx)} (${idx.label})` : iri
              })
              .join(', ') || '—'}
          </div>
        </div>

        {storedEqs.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <strong style={{ fontSize: 13 }}>Equations</strong>
            {storedEqs.map(([eqId, eq]) => (
              <code
                key={eqId}
                style={{ fontSize: 12, background: '#f5f5f5', padding: 8, borderRadius: 4 }}
              >
                {eq.internal_id ?? eqId}: {variable.label} := {eq.rhs}
                {eq.equation_class && (
                  <span style={{ color: '#888' }}> [{eq.equation_class}]</span>
                )}
              </code>
            ))}
          </div>
        )}

        {onAddEquation && (
          <div>
            <button type="button" onClick={() => onAddEquation(variable)}>
              Add equation…
            </button>
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
          {msg && (
            <span
              style={{
                fontSize: 12,
                color: msg.startsWith('Save failed') ? '#c62828' : '#2e8b57',
                whiteSpace: 'pre-line',
                textAlign: 'right',
              }}
            >
              {msg}
            </span>
          )}
          <button type="button" onClick={onClose}>
            Close
          </button>
          <button type="button" onClick={handleSave} disabled={!canSave}>
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
