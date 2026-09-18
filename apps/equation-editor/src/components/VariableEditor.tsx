import { useEffect, useState } from 'react'
import type { Index, NetworkTree, Variable } from '../types'
import NetworkTreeSelect from './NetworkTreeSelect'

const VARIABLE_CLASSES = ['state', 'effort', 'transport', 'frame', 'network', 'constant', 'parameter']
const UNIT_LABELS = ['time', 'length', 'amount', 'mass', 'temperature', 'current', 'light', 'nil']

export interface VariableEditorProps {
  open: boolean
  onClose: () => void
  variables: Variable[]
  indices: Index[]
  networkTree: NetworkTree
  onAdd: (v: Variable) => void
}

function nextInternalId(variables: Variable[]): string {
  const max = variables
    .map((v) => parseInt(v.internal_id?.replace(/^V_/, '') ?? '0', 10))
    .filter((n) => !Number.isNaN(n))
  const next = (max.length ? Math.max(...max) : 0) + 1
  return `V_${next}`
}

export default function VariableEditor({
  open,
  onClose,
  variables,
  indices,
  networkTree,
  onAdd,
}: VariableEditorProps) {
  const [label, setLabel] = useState('')
  const [latexSym, setLatexSym] = useState('')
  const [network, setNetwork] = useState('')
  const [variableClass, setVariableClass] = useState('')
  const [units, setUnits] = useState<number[]>([0, 0, 0, 0, 0, 0, 0, 0])
  const [selectedIndices, setSelectedIndices] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (open) {
      setLabel('')
      setLatexSym('')
      setNetwork('')
      setVariableClass('')
      setUnits([0, 0, 0, 0, 0, 0, 0, 0])
      setSelectedIndices(new Set())
    }
  }, [open])

  const canAdd = label.trim() && network && variableClass

  const toggleIndex = (iri: string) => {
    setSelectedIndices((prev) => {
      const next = new Set(prev)
      if (next.has(iri)) next.delete(iri)
      else next.add(iri)
      return next
    })
  }

  const handleAdd = () => {
    if (!canAdd) return
    const trimmed = label.trim()
    const v: Variable = {
      iri: `promo:${trimmed.toLowerCase()}`,
      label: trimmed,
      network,
      type: variableClass,
      units: [...units],
      index_structures: Array.from(selectedIndices),
      internal_id: nextInternalId(variables),
      port_variable: true,
      aliases: latexSym.trim() ? { latex: latexSym.trim() } : {},
      doc: 'Port variable',
    }
    onAdd(v)
    onClose()
  }

  if (!open) return null

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
          maxHeight: '90vh',
          overflowY: 'auto',
          background: '#fff',
          borderRadius: 6,
          padding: 20,
          boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
          fontSize: 13,
        }}
      >
        <h3 style={{ margin: '0 0 16px' }}>New port variable</h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            Domain / network <span style={{ color: '#c62828' }}>*</span>
            <NetworkTreeSelect tree={networkTree} selected={network} onSelect={setNetwork} />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            Variable class <span style={{ color: '#c62828' }}>*</span>
            <select
              value={variableClass}
              onChange={(e) => setVariableClass(e.target.value)}
            >
              <option value="">Select a class…</option>
              {VARIABLE_CLASSES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            Name <span style={{ color: '#c62828' }}>*</span>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. rho"
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            LaTeX symbol
            <input
              type="text"
              value={latexSym}
              onChange={(e) => setLatexSym(e.target.value)}
              placeholder="e.g. \\rho or \\dot{m} — defaults to the name"
            />
          </label>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span>Units (SI vector)</span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
              {UNIT_LABELS.map((name, i) => (
                <label key={name} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontSize: 10, color: '#666' }}>{name}</span>
                  <input
                    type="number"
                    step="1"
                    value={units[i]}
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

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
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
                    onChange={() => toggleIndex(i.iri)}
                  />
                  <span>
                    {i.label} ({i.aliases?.internal_code ?? i.iri})
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="button" onClick={handleAdd} disabled={!canAdd}>
              Add variable
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
