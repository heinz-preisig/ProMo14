import { useEffect, useState } from 'react'
import type { NetworkTree, Variable } from '../types'
import NetworkTreeSelect from './NetworkTreeSelect'

const VARIABLE_CLASSES = ['state', 'effort', 'transport', 'frame', 'network', 'constant', 'parameter']

export interface DependentVariableDialogProps {
  open: boolean
  onClose: () => void
  variables: Variable[]
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

export default function DependentVariableDialog({
  open,
  onClose,
  variables,
  networkTree,
  onAdd,
}: DependentVariableDialogProps) {
  const [label, setLabel] = useState('')
  const [network, setNetwork] = useState('')
  const [variableClass, setVariableClass] = useState('')

  useEffect(() => {
    if (open) {
      setLabel('')
      setNetwork('')
      setVariableClass('')
    }
  }, [open])

  const canAdd = label.trim() && network && variableClass

  const handleAdd = () => {
    if (!canAdd) return
    const trimmed = label.trim()
    const v: Variable = {
      iri: `promo:${trimmed.toLowerCase()}`,
      label: trimmed,
      network,
      type: variableClass,
      units: [0, 0, 0, 0, 0, 0, 0, 0],
      index_structures: [],
      internal_id: nextInternalId(variables),
      port_variable: false,
      doc: '',
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
          width: 420,
          maxHeight: '90vh',
          overflowY: 'auto',
          background: '#fff',
          borderRadius: 6,
          padding: 20,
          boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
          fontSize: 13,
        }}
      >
        <h3 style={{ margin: '0 0 16px' }}>New dependent variable</h3>
        <p style={{ margin: '0 0 16px', color: '#555' }}>
          Define the left-hand side variable. Its right-hand side expression will be
          written and checked in the main editor.
        </p>

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
              placeholder="e.g. kinetic_energy"
            />
          </label>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="button" onClick={handleAdd} disabled={!canAdd}>
              Define LHS
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
