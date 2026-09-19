import { useCallback, useEffect, useState } from 'react'
import { demoIndices, demoNetworkTree } from './demoContext'
import { indexShortLabel } from './latex'
import { deleteVariable, documentUrl, loadContext, saveOntology, saveVariable } from './api'
import { useStoreDirty } from './useStoreDirty'
import type { Index, NetworkTree, Variable } from './types'
import ContextEditor from './components/ContextEditor'
import DeleteVariableDialog, { type DeleteImpact } from './components/DeleteVariableDialog'
import DependentVariableEditor from './components/DependentVariableEditor'
import EquationList, { type SavedEquation } from './components/EquationList'
import PortVariableEditor from './components/PortVariableEditor'
import VariablePalette from './components/VariablePalette'

export default function App() {
  const [variables, setVariables] = useState<Variable[]>([])
  const [indices, setIndices] = useState<Index[]>(demoIndices)
  const [networkTree, setNetworkTree] = useState<NetworkTree>(demoNetworkTree)
  const [expressionNetwork, setExpressionNetwork] = useState('root')

  const [equations, setEquations] = useState<SavedEquation[]>([])

  const [portOpen, setPortOpen] = useState(false)
  const [dependentOpen, setDependentOpen] = useState(false)
  // Last domain/class picked in either variable editor — offered as
  // defaults the next time one is opened.
  const [lastDomain, setLastDomain] = useState('')
  const [lastClass, setLastClass] = useState('')

  const [deleteTarget, setDeleteTarget] = useState<Variable | null>(null)
  const [selectedVariable, setSelectedVariable] = useState<Variable | null>(null)
  const [latexDraft, setLatexDraft] = useState('')
  const [latexMsg, setLatexMsg] = useState('')
  const [debugOpen, setDebugOpen] = useState(false)
  const { dirty: storeDirty, refresh: refreshDirty } = useStoreDirty()
  const [saveMsg, setSaveMsg] = useState('')

  const onSave = useCallback(async () => {
    try {
      await saveOntology()
      refreshDirty()
      setSaveMsg('Saved')
      setTimeout(() => setSaveMsg(''), 3000)
    } catch (err) {
      setSaveMsg(`Save failed: ${err}`)
    }
  }, [refreshDirty])

  useEffect(() => {
    loadContext()
      .then((ctx) => {
        setVariables(ctx.variables)
        setIndices(ctx.indices)
        setNetworkTree(ctx.network_tree)
        // Rebuild SavedEquation list from persisted equations
        const saved: SavedEquation[] = []
        for (const v of ctx.variables) {
          if (v.equations) {
            for (const [eqId, eq] of Object.entries(v.equations)) {
              saved.push({
                id: eqId,
                lhs: v.label,
                text: eq.rhs,
                ast: null,
                check: null,
              })
            }
          }
        }
        if (saved.length > 0) {
          setEquations(saved)
        }
      })
      .catch((err) => console.error('Failed to load context:', err))
  }, [])

  const addPortVariable = useCallback(async (v: Variable) => {
    try {
      await saveVariable(v)
      const ctx = await loadContext()
      setVariables(ctx.variables)
      setIndices(ctx.indices)
      setNetworkTree(ctx.network_tree)
    } catch (err) {
      console.error('Failed to save variable:', err)
    }
  }, [])

  const acceptDependent = useCallback(async (v: Variable, eq: SavedEquation) => {
    try {
      await saveVariable(v, eq)
      const ctx = await loadContext()
      setVariables(ctx.variables)
      setIndices(ctx.indices)
      setNetworkTree(ctx.network_tree)
    } catch (err) {
      console.error('Failed to save variable:', err)
    }
    setEquations((prev) => [...prev, eq])
  }, [])

  const removeEquation = useCallback((id: string) => {
    setEquations((prev) => prev.filter((eq) => eq.id !== id))
  }, [])

  const removeVariable = useCallback(async (impact: DeleteImpact) => {
    for (const iri of impact.variableIris) {
      try {
        await deleteVariable(iri)
      } catch (err) {
        console.error('Failed to delete variable:', iri, err)
      }
    }
    setVariables((prev) => prev.filter((v) => !impact.variableIris.includes(v.iri)))
    setEquations((prev) => prev.filter((eq) => !impact.equationIds.includes(eq.id)))
    setDeleteTarget(null)
  }, [])

  // Sync the LaTeX draft field whenever a different variable is opened.
  useEffect(() => {
    setLatexDraft(selectedVariable?.aliases?.latex ?? '')
    setLatexMsg('')
  }, [selectedVariable])

  const saveLatexAlias = useCallback(async () => {
    if (!selectedVariable) return
    const aliases = { ...(selectedVariable.aliases ?? {}) }
    if (latexDraft.trim()) aliases.latex = latexDraft.trim()
    else delete aliases.latex
    try {
      await saveVariable({ ...selectedVariable, aliases })
      const ctx = await loadContext()
      setVariables(ctx.variables)
      setIndices(ctx.indices)
      setNetworkTree(ctx.network_tree)
      setSelectedVariable((prev) => (prev ? { ...prev, aliases } : prev))
      setLatexMsg('Saved')
      setTimeout(() => setLatexMsg(''), 3000)
    } catch (err) {
      setLatexMsg(`Save failed: ${err}`)
    }
  }, [selectedVariable, latexDraft])

  const updateContext = useCallback((ctx: {
    variables: Variable[]
    indices: Index[]
    networkTree: NetworkTree
    expressionNetwork: string
  }) => {
    setVariables(ctx.variables)
    setIndices(ctx.indices)
    setNetworkTree(ctx.networkTree)
    setExpressionNetwork(ctx.expressionNetwork)
  }, [])

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
      }}
    >
      <div
        style={{
          height: 44,
          padding: '0 16px',
          background: '#e0e0e0',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          borderBottom: '1px solid #ccc',
        }}
      >
        <strong>ProMo14 — Equation Editor</strong>
        <div style={{ flex: 1 }} />
        {storeDirty && (
          <span style={{ fontSize: 12, color: '#b8860b' }} title="Unsaved changes in the store">
            ● unsaved
          </span>
        )}
        {saveMsg && <span style={{ fontSize: 12, color: '#2e8b57' }}>{saveMsg}</span>}
        <a
          href={documentUrl()}
          target="_blank"
          rel="noreferrer"
          style={{ fontSize: 12 }}
          title="Open the printable LaTeX document (variables & equations)"
        >
          LaTeX doc
        </a>
        <button type="button" onClick={onSave} style={{ fontSize: 12 }}>
          Save
        </button>
      </div>

      <div
        style={{
          flex: 1,
          display: 'flex',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: 260,
            padding: 12,
            background: '#f0f0f0',
            borderRight: '1px solid #ccc',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignSelf: 'stretch' }}>
            <button type="button" onClick={() => setPortOpen(true)}>
              New port variable…
            </button>
            <button type="button" onClick={() => setDependentOpen(true)}>
              New dependent variable…
            </button>
          </div>
          <VariablePalette
            variables={variables}
            onDelete={setDeleteTarget}
            onSelect={setSelectedVariable}
          />
          <EquationList
            equations={equations}
            onSelect={() => {}}
            onRemove={removeEquation}
          />
        </div>

        <div
          style={{
            flex: 1,
            padding: 16,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          <div
            style={{
              padding: 12,
              background: '#e8f4fd',
              border: '1px solid #b3d9f7',
              borderRadius: 4,
              fontSize: 13,
              color: '#0d47a1',
            }}
          >
            This is the repository view. Use the sidebar buttons to define a
            <strong>port variable</strong> (foundation: name, units, index
            structure) or a <strong>dependent variable</strong> (defined by a
            checked RHS expression). Click a variable to see its details.
          </div>

          <button
            type="button"
            onClick={() => setDebugOpen(true)}
            style={{ alignSelf: 'flex-start', fontSize: 12 }}
          >
            Debug equation context (JSON)…
          </button>
        </div>
      </div>

      <PortVariableEditor
        open={portOpen}
        onClose={() => setPortOpen(false)}
        variables={variables}
        indices={indices}
        networkTree={networkTree}
        initialDomain={lastDomain}
        initialClass={lastClass}
        onDefaultsChange={(d, c) => {
          setLastDomain(d)
          setLastClass(c)
        }}
        onAccept={addPortVariable}
      />

      <DeleteVariableDialog
        open={!!deleteTarget}
        target={deleteTarget}
        variables={variables}
        equations={equations}
        onClose={() => setDeleteTarget(null)}
        onConfirm={removeVariable}
      />

      <DependentVariableEditor
        open={dependentOpen}
        onClose={() => setDependentOpen(false)}
        variables={variables}
        indices={indices}
        networkTree={networkTree}
        initialDomain={lastDomain}
        initialClass={lastClass}
        onDefaultsChange={(d, c) => {
          setLastDomain(d)
          setLastClass(c)
        }}
        onAccept={acceptDependent}
      />

      {debugOpen && (
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
            if (e.target === e.currentTarget) setDebugOpen(false)
          }}
        >
          <div
            style={{
              width: '70vw',
              height: '80vh',
              background: '#fff',
              borderRadius: 6,
              padding: 20,
              boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0 }}>Debug equation context</h3>
              <button type="button" onClick={() => setDebugOpen(false)}>
                Close
              </button>
            </div>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <ContextEditor
                variables={variables}
                indices={indices}
                networkTree={networkTree}
                expressionNetwork={expressionNetwork}
                onChange={updateContext}
              />
            </div>
          </div>
        </div>
      )}

      {selectedVariable && (
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
            if (e.target === e.currentTarget) setSelectedVariable(null)
          }}
        >
          <div
            style={{
              width: 480,
              maxHeight: '80vh',
              background: '#fff',
              borderRadius: 6,
              padding: 20,
              boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
              overflowY: 'auto',
            }}
          >
            <h3 style={{ margin: 0 }}>{selectedVariable.label}</h3>
            <div style={{ fontSize: 13, color: '#555' }}>
              <strong>IRI:</strong> {selectedVariable.iri} <br />
              <strong>Network:</strong> {selectedVariable.network} <br />
              <strong>Class:</strong> {selectedVariable.type ?? '—'} <br />
              <strong>Port variable:</strong> {selectedVariable.port_variable ? 'yes' : 'no'} <br />
              <strong>Index structures:</strong>{' '}
              {selectedVariable.index_structures
                ?.map((iri) => {
                  const idx = indices.find((i) => i.iri === iri)
                  return idx
                    ? `${indexShortLabel(idx)} (${idx.label})`
                    : iri
                })
                .join(', ') ?? '—'} <br />
              <strong>Units:</strong> {JSON.stringify(selectedVariable.units)} <br />
              <strong>LaTeX symbol:</strong>{' '}
              <input
                type="text"
                value={latexDraft}
                onChange={(e) => setLatexDraft(e.target.value)}
                placeholder="e.g. \\rho — defaults to label"
                style={{ width: 160, fontSize: 12 }}
              />{' '}
              <button type="button" onClick={saveLatexAlias} style={{ fontSize: 12 }}>
                Save
              </button>{' '}
              {latexMsg && <span style={{ fontSize: 12, color: '#2e8b57' }}>{latexMsg}</span>}
              <br />
              {selectedVariable.doc && (
                <>
                  <strong>Doc:</strong> {selectedVariable.doc}
                </>
              )}
            </div>

            {(() => {
              const eq = equations.find((e) => e.lhs === selectedVariable.label)
              if (!eq) return null
              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <strong style={{ fontSize: 13 }}>Defining equation</strong>
                  <code style={{ fontSize: 12, background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
                    {eq.text}
                  </code>
                  <div style={{ fontSize: 12, color: '#666' }}>
                    Units: {eq.check?.units_pretty ?? '—'} | Indices: {eq.check?.indices?.join(', ') ?? '—'}
                  </div>
                </div>
              )
            })()}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
              <button type="button" onClick={() => setSelectedVariable(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
