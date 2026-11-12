import 'katex/dist/katex.min.css'
import { useEffect, useState } from 'react'
import type { ClassificationAxis, Domain, EquationClass, Index, NetworkTree, TokenRecord, Variable } from '../types'
import { equationClassLabel, referenceDisplay } from '../variableUtils'
import TokenSection from './TokenSection'
import { astToLatex, indexShortLabel, renderLatex, suggestLatexAlias, validateLatexAlias } from '../latex'
import { useVariableLock } from '../useVariableLock'
import AxisClassifications, { applicableAxes, kindTag } from '../axisClassifications'
import NetworkTreeSelect from './NetworkTreeSelect'

const UNIT_LABELS = ['time', 'length', 'amount', 'mass', 'temperature', 'current', 'light', 'nil']

export interface VariableDetailDialogProps {
  variable: Variable
  /** All variables — resolves §18 reference entries to the variable
   *  that owns each referencing equation. */
  variables?: Variable[]
  indices: Index[]
  networkTree: NetworkTree
  axes: ClassificationAxis[]
  domains: Domain[]
  /** EquationClass nodes — maps stored class IRIs to labels. */
  equationClasses?: EquationClass[]
  /** promo:Token catalogue for the carriesToken/tokenVector pickers. */
  tokenCatalogue?: TokenRecord[]
  /** Persist the edited variable (POST /variables). Throws on failure. */
  onSave: (v: Variable) => Promise<void>
  /** Open the equation editor to attach another equation (§18). */
  onAddEquation?: (v: Variable) => void
  /** Open the equation editor to rewrite a stored equation. */
  onEditEquation?: (v: Variable, eqId: string) => void
  onClose: () => void
}

/** Variable detail + edit dialog.
 *
 *  Mutability policy (design doc §18): label, LaTeX alias, doc and role
 *  classifications remain editable; domain is editable while references are
 *  only this variable's own definitions. Units and index structures lock
 *  while referenced. The backend enforces the same field-level policy. */
export default function VariableDetailDialog({
  variable,
  variables = [],
  indices,
  networkTree,
  axes,
  domains,
  equationClasses = [],
  tokenCatalogue = [],
  onSave,
  onAddEquation,
  onEditEquation,
  onClose,
}: VariableDetailDialogProps) {
  const [label, setLabel] = useState(variable.label)
  const [latexSym, setLatexSym] = useState(variable.aliases?.latex ?? '')
  const [doc, setDoc] = useState(variable.doc ?? '')
  const [network, setNetwork] = useState(variable.network)
  const [classifications, setClassifications] = useState<Record<string, string>>(
    variable.classifications ?? {},
  )
  const [units, setUnits] = useState<number[]>(variable.units ?? [0, 0, 0, 0, 0, 0, 0, 0])
  const [selectedIndices, setSelectedIndices] = useState<Set<string>>(
    new Set(variable.index_structures ?? []),
  )
  // §24 token declarations: carriesToken (network membership, port
  // licensing) and tokenVector (algebraic signature, exponent map).
  const [carriesTokens, setCarriesTokens] = useState<Set<string>>(
    new Set(variable.tokens ?? []),
  )
  const [msg, setMsg] = useState('')
  // §18 usage lock — units and index structures remain locked while used;
  // domain moves are planned atomically by the backend and may qualify
  // editable references to preserve their variable IRI bindings.
  const { references } = useVariableLock(variable.iri)

  // Reinitialise + refresh the usage lock whenever another variable is shown.
  useEffect(() => {
    setLabel(variable.label)
    setLatexSym(variable.aliases?.latex ?? '')
    setDoc(variable.doc ?? '')
    setNetwork(variable.network)
    setClassifications(variable.classifications ?? {})
    setUnits(variable.units ?? [0, 0, 0, 0, 0, 0, 0, 0])
    setSelectedIndices(new Set(variable.index_structures ?? []))
    setCarriesTokens(new Set(variable.tokens ?? []))
    setMsg('')
  }, [variable])

  const foreignRefCount = references.filter((ref) => ref.via !== 'lhs').length
  // §18: only foreign references lock — own defining equations (lhs)
  // are the definition itself and do not block redefinition.
  const locked = foreignRefCount > 0
  const latexSuggestion = label.trim() ? suggestLatexAlias(label) : ''
  const latexError = validateLatexAlias(latexSym)
  const canSave = label.trim() && network && !latexError

  const toggleIndex = (iri: string) => {
    setSelectedIndices((prev) => {
      const next = new Set(prev)
      if (next.has(iri)) next.delete(iri)
      else next.add(iri)
      return next
    })
  }

  const toggleToken = (iri: string) => {
    setCarriesTokens((prev) => {
      const next = new Set(prev)
      if (next.has(iri)) next.delete(iri)
      else next.add(iri)
      return next
    })
  }

  const selectedDomainIri = domains.find((item) => item.name === network)?.iri ?? null

  /** The variable as currently edited — shared by Save, the equation
   *  check and Add equation so all see the same record. */
  const draftVariable = (): Variable => {
    const aliases = { ...(variable.aliases ?? {}) }
    if (latexSym.trim()) aliases.latex = latexSym.trim()
    else delete aliases.latex
    const equations = Object.fromEntries(
      Object.entries(variable.equations ?? {}).map(([key, equation]) => [
        key,
        network !== variable.network
          ? { ...equation, network, domain_iri: selectedDomainIri }
          : equation,
      ]),
    )
    return {
      ...variable,
      label: label.trim(),
      network,
      domain_iri: selectedDomainIri,
      classifications,
      units: [...units],
      index_structures: Array.from(selectedIndices),
      aliases,
      doc: doc.trim(),
      tokens: Array.from(carriesTokens),
      equations,
    }
  }

  const handleSave = async () => {
    if (!canSave) return
    try {
      await onSave(draftVariable())
      setMsg('Saved')
      setTimeout(onClose, 600)
    } catch (err) {
      setMsg(`Save failed: ${err instanceof Error ? err.message : err}`)
    }
  }

  const storedEqs = Object.entries(variable.equations ?? {})

  // Live-rendered symbol — the edited alias + currently selected index
  // structures, matching how expressions render this variable.
  const symbolPreviewHtml = (() => {
    const pv: Variable = {
      ...variable,
      label: label.trim() || variable.label,
      aliases: latexSym.trim()
        ? { ...(variable.aliases ?? {}), latex: latexSym.trim() }
        : variable.aliases,
      index_structures: Array.from(selectedIndices),
    }
    return renderLatex(
      astToLatex({ type: 'Var', name: pv.label }, { variables: [pv], indices }),
      false,
    )
  })()

  // ``lhs = rhs`` for stored equations — the persisted rhs_latex is the
  // render truth; raw text fallback for older records.
  const storedEqHtml = (v: Variable, rhsLatex: string) => {
    const lhs = astToLatex({ type: 'Var', name: v.label }, { variables: [v], indices })
    return renderLatex(`${lhs} = ${rhsLatex}`, false)
  }

  // Units and index structures remain locked while referenced.  Domain
  // has its own narrower lock; role/classification remains editable.
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
          width: 880,
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
            Referenced by {foreignRefCount} foreign equation(s) — role and domain remain editable.
            {' '}A domain move qualifies editable references when safe. Units and index structures remain locked.
            <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
              {references.map((ref) => {
                const { eqId, ownerLabel } = referenceDisplay(ref, variables)
                return (
                  <li key={`${ref.graph}#${eqId}`}>
                    <code>{eqId}</code>
                    {ref.via === 'lhs'
                      ? ' — defines this variable'
                      : ` — used in the rhs of ${ownerLabel ?? 'another variable'}`}
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '0 20px',
          }}
        >
          {/* left column — identity */}
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
              style={{ borderColor: latexError ? '#c62828' : undefined }}
            />
            {latexSuggestion && latexSym.trim() !== latexSuggestion && (
              <button type="button" onClick={() => setLatexSym(latexSuggestion)} style={{ alignSelf: 'flex-start' }}>
                Use {latexSuggestion}
              </button>
            )}
            <span
              style={{ padding: '4px 0' }}
              dangerouslySetInnerHTML={{ __html: symbolPreviewHtml }}
            />
            {latexError && <span style={{ color: '#c62828', fontSize: 11 }}>{latexError}</span>}
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

          <div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              Domain / network <span style={{ color: '#c62828' }}>*</span>
              <NetworkTreeSelect
                selected={network}
                tree={networkTree}
                onSelect={setNetwork}
              />
              {foreignRefCount > 0 && network !== variable.network && (
                <span style={{ color: '#8a5a00', fontSize: 11 }}>
                  {foreignRefCount} referencing equation{foreignRefCount === 1 ? '' : 's'} will be qualified automatically when safe.
                </span>
              )}
            </label>
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

          {/* right column — structure */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            {applicableAxes(axes, network, domains).length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span>
                  Classification <span style={{ color: '#c62828' }}>*</span>
                </span>
                {Object.keys(classifications).length === 0 && (
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
                    No classifications are stored for this variable — kind reads
                    “{kindTag(axes, classifications) || 'unclassified'}”;
                    pick terms below to give it a physical nature.
                  </div>
                )}
                <AxisClassifications
                  axes={axes}
                  domain={network}
                  domains={domains}
                  value={classifications}
                  hiddenAxes={variable.port_variable ? ['determination'] : undefined}
                  onChange={setClassifications}
                />
                <span style={{ fontSize: 12, color: '#555' }}>
                  kind: {kindTag(axes, classifications) || 'unclassified'}
                </span>
              </div>
            ) : (
              <span style={{ fontSize: 12, color: '#8d6e00' }}>
                No classification axes apply in this domain.
              </span>
            )}
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

          <TokenSection
            tokenCatalogue={tokenCatalogue}
            carriesTokens={carriesTokens}
            onToggleToken={toggleToken}
          />
          </div>
        </div>

        {storedEqs.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <strong style={{ fontSize: 13 }}>Equations</strong>
            {storedEqs.map(([eqId, eq]) => (
              <div
                key={eqId}
                style={{ fontSize: 12, background: '#f5f5f5', padding: 8, borderRadius: 4, overflowX: 'auto' }}
              >
                {eq.rhs_latex ? (
                  <span dangerouslySetInnerHTML={{ __html: storedEqHtml(variable, eq.rhs_latex) }} />
                ) : (
                  <code>
                    {variable.label} := {eq.rhs}
                  </code>
                )}
                {eq.equation_class && (
                  <span style={{ color: '#888' }}> [{equationClassLabel(eq.equation_class, equationClasses)}]</span>
                )}
                {onEditEquation && (
                  <button
                    type="button"
                    onClick={() => onEditEquation(variable, eqId)}
                    style={{ marginLeft: 8, fontSize: 11 }}
                    title={`Edit equation ${eqId}`}
                  >
                    Edit…
                  </button>
                )}
              </div>
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
