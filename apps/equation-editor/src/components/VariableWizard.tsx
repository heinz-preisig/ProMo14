import { useEffect, useState } from 'react'
import { indexShortLabel } from '../latex'
import type { Index, NetworkTree, Variable } from '../types'
import NetworkTreeSelect from './NetworkTreeSelect'

const VARIABLE_CLASSES = ['state', 'effort', 'transport', 'frame', 'network', 'constant', 'parameter']
const UNIT_LABELS = ['time', 'length', 'amount', 'mass', 'temperature', 'current', 'light', 'nil']

type Kind = 'port' | 'dependent'

type Step = 'kind' | 'class' | 'port'

export interface VariableWizardProps {
  open: boolean
  onClose: () => void
  variables: Variable[]
  indices: Index[]
  networkTree: NetworkTree
  initialDomain?: string
  initialKind?: Kind
  initialClass?: string
  onDefaultsChange?: (domain: string, kind: Kind, variableClass: string) => void
  onAddPort: (v: Variable) => void
  onStartDependent: (domain: string, variableClass: string) => void
}

function nextInternalId(variables: Variable[]): string {
  const max = variables
    .map((v) => parseInt(v.internal_id?.replace(/^V_/, '') ?? '0', 10))
    .filter((n) => !Number.isNaN(n))
  const next = (max.length ? Math.max(...max) : 0) + 1
  return `V_${next}`
}

function Modal({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) {
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
      {children}
    </div>
  )
}

export default function VariableWizard({
  open,
  onClose,
  variables,
  indices,
  networkTree,
  initialDomain = '',
  initialKind = 'port',
  initialClass = '',
  onDefaultsChange,
  onAddPort,
  onStartDependent,
}: VariableWizardProps) {
  const [step, setStep] = useState<Step>('kind')
  const [domain, setDomain] = useState(initialDomain)
  const [kind, setKind] = useState<Kind>(initialKind)
  const [variableClass, setVariableClass] = useState(initialClass)

  const [portName, setPortName] = useState('')
  const [portLatex, setPortLatex] = useState('')
  const [units, setUnits] = useState<number[]>([0, 0, 0, 0, 0, 0, 0, 0])
  const [selectedIndices, setSelectedIndices] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (open) {
      setStep('kind')
      setDomain(initialDomain)
      setKind(initialKind)
      setVariableClass(initialClass)
      setPortName('')
      setPortLatex('')
      setUnits([0, 0, 0, 0, 0, 0, 0, 0])
      setSelectedIndices(new Set())
    }
  }, [open])

  useEffect(() => {
    onDefaultsChange?.(domain, kind, variableClass)
  }, [domain, kind, variableClass])

  const toggleIndex = (iri: string) => {
    setSelectedIndices((prev) => {
      const next = new Set(prev)
      if (next.has(iri)) next.delete(iri)
      else next.add(iri)
      return next
    })
  }

  const handleAddPort = () => {
    const trimmed = portName.trim()
    if (!trimmed || !domain || !variableClass) return
    const v: Variable = {
      iri: `promo:${trimmed.toLowerCase()}`,
      label: trimmed,
      network: domain,
      type: variableClass,
      units: [...units],
      index_structures: Array.from(selectedIndices),
      internal_id: nextInternalId(variables),
      port_variable: true,
      aliases: portLatex.trim() ? { latex: portLatex.trim() } : {},
      doc: 'Port variable',
    }
    onAddPort(v)
    onClose()
  }

  const canProceedFromKind = domain && kind
  const canProceedFromClass = variableClass

  const renderKindStep = () => (
    <div style={{ width: 420, fontSize: 13 }}>
      <h3 style={{ margin: '0 0 16px' }}>New variable</h3>
      <p style={{ margin: '0 0 12px', color: '#555' }}>
        Select a domain and the kind of variable you want to define.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          Domain / network <span style={{ color: '#c62828' }}>*</span>
          <NetworkTreeSelect tree={networkTree} selected={domain} onSelect={setDomain} />
        </label>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span>Kind <span style={{ color: '#c62828' }}>*</span></span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={() => setKind('port')}
              style={{
                flex: 1,
                padding: 12,
                border: kind === 'port' ? '2px solid #1976d2' : '1px solid #ccc',
                background: kind === 'port' ? '#e3f2fd' : '#fff',
                fontWeight: kind === 'port' ? 'bold' : 'normal',
              }}
            >
              Port variable
            </button>
            <button
              type="button"
              onClick={() => setKind('dependent')}
              style={{
                flex: 1,
                padding: 12,
                border: kind === 'dependent' ? '2px solid #1976d2' : '1px solid #ccc',
                background: kind === 'dependent' ? '#e3f2fd' : '#fff',
                fontWeight: kind === 'dependent' ? 'bold' : 'normal',
              }}
            >
              Dependent variable
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="button" onClick={() => setStep('class')} disabled={!canProceedFromKind}>
            Next
          </button>
        </div>
      </div>
    </div>
  )

  const renderClassStep = () => (
    <div style={{ width: 420, fontSize: 13 }}>
      <h3 style={{ margin: '0 0 16px' }}>Variable class</h3>
      <div style={{ margin: '0 0 12px', color: '#555' }}>
        <strong>Domain:</strong> {domain || '—'} · <strong>Kind:</strong> {kind}
      </div>

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

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button type="button" onClick={() => setStep('kind')}>
          Back
        </button>
        <button
          type="button"
          onClick={() => {
            if (kind === 'dependent') {
              onStartDependent(domain, variableClass)
              onClose()
            } else {
              setStep('port')
            }
          }}
          disabled={!canProceedFromClass}
        >
          Next
        </button>
      </div>
    </div>
  )

  const renderPortStep = () => (
    <div style={{ width: 460, maxHeight: '90vh', overflowY: 'auto', fontSize: 13 }}>
      <h3 style={{ margin: '0 0 16px' }}>New port variable</h3>
      <div style={{ margin: '0 0 12px', color: '#555' }}>
        <strong>Domain:</strong> {domain} · <strong>Class:</strong> {variableClass}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          Name <span style={{ color: '#c62828' }}>*</span>
          <input
            type="text"
            value={portName}
            onChange={(e) => setPortName(e.target.value)}
            placeholder="e.g. rho"
          />
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          LaTeX symbol
          <input
            type="text"
            value={portLatex}
            onChange={(e) => setPortLatex(e.target.value)}
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
                <span title={`${i.iri}${i.aliases?.internal_code ? ' / ' + i.aliases.internal_code : ''}`}>
                  {indexShortLabel(i)} ({i.label})
                </span>
              </label>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="button" onClick={() => setStep('class')}>
            Back
          </button>
          <button type="button" onClick={handleAddPort} disabled={!portName.trim()}>
            Add variable
          </button>
        </div>
      </div>
    </div>
  )

  const content =
    step === 'kind'
      ? renderKindStep()
      : step === 'class'
      ? renderClassStep()
      : renderPortStep()

  return (
    <Modal open={open} onClose={onClose}>
      <div
        style={{
          background: '#fff',
          borderRadius: 6,
          padding: 20,
          boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
        }}
      >
        {content}
      </div>
    </Modal>
  )
}
