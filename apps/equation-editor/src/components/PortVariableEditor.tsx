import { useEffect, useState } from 'react'
import { indexShortLabel } from '../latex'
import type { ClassificationAxis, Domain, Index, NetworkTree, Variable } from '../types'
import AxisClassifications, {
  applicableAxes,
  deriveType,
  findTermIri,
} from '../axisClassifications'
import {
  findNameCollision,
  isValidVariableName,
  VARIABLE_CLASSES,
  VARIABLE_NAME_HINT,
} from '../validation'
import { nextInternalId } from '../variableUtils'
import NetworkTreeSelect from './NetworkTreeSelect'

const UNIT_LABELS = ['time', 'length', 'amount', 'mass', 'temperature', 'current', 'light', 'nil']

export interface PortVariableEditorProps {
  open: boolean
  onClose: () => void
  variables: Variable[]
  indices: Index[]
  networkTree: NetworkTree
  axes: ClassificationAxis[]
  domains: Domain[]
  initialDomain?: string
  initialClassifications?: Record<string, string>
  onDefaultsChange?: (domain: string, classifications: Record<string, string>) => void
  onAccept: (v: Variable) => void
}

/** Single-dialog port variable definition — same header widgets as the
 *  dependent editor (domain tree + class + name + LaTeX), plus the SI
 *  unit vector and index-structure pickers in the body. */
export default function PortVariableEditor({
  open,
  onClose,
  variables,
  indices,
  networkTree,
  axes,
  domains,
  initialDomain = '',
  initialClassifications = {},
  onDefaultsChange,
  onAccept,
}: PortVariableEditorProps) {
  const [domain, setDomain] = useState(initialDomain)
  const [classifications, setClassifications] = useState<Record<string, string>>({})
  const [variableClass, setVariableClass] = useState('')
  const [name, setName] = useState('')
  const [latexSym, setLatexSym] = useState('')
  const [units, setUnits] = useState<number[]>([0, 0, 0, 0, 0, 0, 0, 0])
  const [selectedIndices, setSelectedIndices] = useState<Set<string>>(new Set())
  const [doc, setDoc] = useState('')

  useEffect(() => {
    if (open) {
      // Port variables are boundary positions — pre-fill
      // determination=port when the axis applies.
      const cls = { ...initialClassifications }
      const port = findTermIri(axes, 'determination', 'port')
      if (port) cls[port.axisIri] = cls[port.axisIri] ?? port.termIri
      setDomain(initialDomain)
      setClassifications(cls)
      setVariableClass(deriveType(axes, cls))
      setName('')
      setLatexSym('')
      setUnits([0, 0, 0, 0, 0, 0, 0, 0])
      setSelectedIndices(new Set())
      setDoc('')
    }
  }, [open])

  // Report the current domain/classifications so the app can offer
  // them as defaults next time either variable editor is opened.
  useEffect(() => {
    onDefaultsChange?.(domain, classifications)
  }, [domain, classifications])

  const toggleIndex = (iri: string) => {
    setSelectedIndices((prev) => {
      const next = new Set(prev)
      if (next.has(iri)) next.delete(iri)
      else next.add(iri)
      return next
    })
  }

  // Base requirements: a port variable needs a valid name, a domain
  // and a class.  Units default to dimensionless and indices to
  // scalar — both are legitimate values, so they don't gate accept.
  const nameValid = isValidVariableName(name)
  const collision = findNameCollision(variables, name)
  const canAccept = nameValid && !!domain && !!variableClass

  const handleAccept = () => {
    if (!canAccept) return
    const trimmed = name.trim()
    const v: Variable = {
      // Case-sensitive IRI: the language treats `rho` and `Rho` as
      // distinct identifiers, so the IRI must preserve case too.
      iri: `promo:${trimmed}`,
      label: trimmed,
      network: domain,
      type: variableClass,
      units: [...units],
      index_structures: Array.from(selectedIndices),
      internal_id: nextInternalId(variables),
      port_variable: true,
      classifications,
      aliases: latexSym.trim() ? { latex: latexSym.trim() } : {},
      doc: doc.trim(),
    }
    onAccept(v)
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
          width: 560,
          maxHeight: '90vh',
          background: '#fff',
          borderRadius: 6,
          padding: 20,
          boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          fontSize: 13,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            marginBottom: 16,
            paddingBottom: 12,
            borderBottom: '1px solid #ccc',
            flexWrap: 'wrap',
          }}
        >
          <h3 style={{ margin: 0 }}>New port variable</h3>

          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Domain:
            <NetworkTreeSelect tree={networkTree} selected={domain} onSelect={setDomain} />
          </label>

          {applicableAxes(axes, domain, domains).length ? (
            <AxisClassifications
              axes={axes}
              domain={domain}
              domains={domains}
              value={classifications}
              onChange={(next) => {
                setClassifications(next)
                setVariableClass(deriveType(axes, next))
              }}
            />
          ) : (
            <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              Class:
              <select value={variableClass} onChange={(e) => setVariableClass(e.target.value)}>
                <option value="">Select…</option>
                {VARIABLE_CLASSES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Name:
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. rho"
              title={VARIABLE_NAME_HINT}
              style={{
                width: 120,
                borderColor: name.trim() && !nameValid ? '#c62828' : undefined,
              }}
            />
            {name.trim() && !nameValid && (
              <span style={{ fontSize: 11, color: '#c62828' }}>{VARIABLE_NAME_HINT}</span>
            )}
            {nameValid && collision === 'exact' && (
              <span style={{ fontSize: 11, color: '#c62828' }}>
                A variable named {name.trim()} already exists — saving overwrites it
              </span>
            )}
            {nameValid && collision === 'similar' && (
              <span style={{ fontSize: 11, color: '#b8860b' }}>
                Differs only by case from an existing variable — names are case-sensitive
              </span>
            )}
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            LaTeX:
            <input
              type="text"
              value={latexSym}
              onChange={(e) => setLatexSym(e.target.value)}
              placeholder="e.g. \\rho — defaults to name"
              style={{ width: 140 }}
            />
          </label>

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="button" onClick={handleAccept} disabled={!canAccept}>
              Add variable
            </button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span>Units (SI vector)</span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
              {UNIT_LABELS.map((label, i) => (
                <label key={label} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontSize: 10, color: '#666' }}>{label}</span>
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
                maxHeight: 140,
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

          <label style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}>
            Documentation
            <textarea
              value={doc}
              onChange={(e) => setDoc(e.target.value)}
              placeholder="Add a description for this variable…"
              style={{ width: '100%', minHeight: 60, fontSize: 13, padding: 8 }}
            />
          </label>
        </div>
      </div>
    </div>
  )
}
