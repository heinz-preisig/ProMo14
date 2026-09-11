import { useCallback, useEffect, useState } from 'react'
import { demoIndices, demoNetworkTree } from './demoContext'
import { indexShortLabel } from './latex'
import { loadContext } from './api'
import type { Index, NetworkTree, Variable } from './types'
import ContextEditor from './components/ContextEditor'
import DeleteVariableDialog, { type DeleteImpact } from './components/DeleteVariableDialog'
import DependentVariableEditor from './components/DependentVariableEditor'
import EquationList, { type SavedEquation } from './components/EquationList'
import VariablePalette from './components/VariablePalette'
import VariableWizard from './components/VariableWizard'

export default function App() {
  const [variables, setVariables] = useState<Variable[]>([])
  const [indices, setIndices] = useState<Index[]>(demoIndices)
  const [networkTree, setNetworkTree] = useState<NetworkTree>(demoNetworkTree)
  const [expressionNetwork, setExpressionNetwork] = useState('root')

  const [equations, setEquations] = useState<SavedEquation[]>([])

  const [wizardOpen, setWizardOpen] = useState(false)
  const [wizardDomain, setWizardDomain] = useState('')
  const [wizardKind, setWizardKind] = useState<'port' | 'dependent'>('port')
  const [wizardClass, setWizardClass] = useState('')

  const [dependentOpen, setDependentOpen] = useState(false)
  const [dependentDomain, setDependentDomain] = useState('')
  const [dependentClass, setDependentClass] = useState('')

  const [deleteTarget, setDeleteTarget] = useState<Variable | null>(null)
  const [selectedVariable, setSelectedVariable] = useState<Variable | null>(null)
  const [debugOpen, setDebugOpen] = useState(false)

  useEffect(() => {
    loadContext()
      .then((ctx) => {
        setVariables(ctx.variables)
        setIndices(ctx.indices)
        setNetworkTree(ctx.network_tree)
      })
      .catch((err) => console.error('Failed to load context:', err))
  }, [])

  const addPortVariable = useCallback((v: Variable) => {
    setVariables((prev) => [...prev, v])
  }, [])

  const startDependent = useCallback((domain: string, variableClass: string) => {
    setDependentDomain(domain)
    setDependentClass(variableClass)
    setDependentOpen(true)
  }, [])

  const acceptDependent = useCallback((v: Variable, eq: SavedEquation) => {
    setVariables((prev) => [...prev, v])
    setEquations((prev) => [...prev, eq])
  }, [])

  const removeEquation = useCallback((id: string) => {
    setEquations((prev) => prev.filter((eq) => eq.id !== id))
  }, [])

  const removeVariable = useCallback((impact: DeleteImpact) => {
    setVariables((prev) => prev.filter((v) => !impact.variableIris.includes(v.iri)))
    setEquations((prev) => prev.filter((eq) => !impact.equationIds.includes(eq.id)))
    setDeleteTarget(null)
  }, [])

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
          <button
            type="button"
            onClick={() => setWizardOpen(true)}
            style={{ alignSelf: 'flex-start' }}
          >
            New variable…
          </button>
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
            This is the repository view. Click <strong>New variable</strong> in the
            sidebar to start the wizard and define a port or dependent variable.
            Click a variable to see its details.
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

      <VariableWizard
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        variables={variables}
        indices={indices}
        networkTree={networkTree}
        initialDomain={wizardDomain}
        initialKind={wizardKind}
        initialClass={wizardClass}
        onDefaultsChange={(d, k, c) => {
          setWizardDomain(d)
          setWizardKind(k)
          setWizardClass(c)
        }}
        onAddPort={addPortVariable}
        onStartDependent={startDependent}
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
        initialDomain={dependentDomain}
        initialClass={dependentClass}
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
