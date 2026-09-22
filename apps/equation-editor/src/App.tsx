import { useCallback, useEffect, useState } from 'react'
import { demoIndices, demoNetworkTree } from './demoContext'
import { deleteVariable, documentUrl, loadContext, saveOntology, saveVariable } from './api'
import { useStoreDirty } from './useStoreDirty'
import type { Index, NetworkTree, SavedEquation, Variable } from './types'
import ContextEditor from './components/ContextEditor'
import DeleteVariableDialog, { type DeleteImpact } from './components/DeleteVariableDialog'
import DependentVariableEditor from './components/DependentVariableEditor'
import EquationList from './components/EquationList'
import PortVariableEditor from './components/PortVariableEditor'
import VariableDetailDialog from './components/VariableDetailDialog'
import VariablePalette from './components/VariablePalette'
import VariableTable from './components/VariableTable'

export default function App() {
  const [variables, setVariables] = useState<Variable[]>([])
  const [indices, setIndices] = useState<Index[]>(demoIndices)
  const [networkTree, setNetworkTree] = useState<NetworkTree>(demoNetworkTree)
  const [expressionNetwork, setExpressionNetwork] = useState('root')

  const [equations, setEquations] = useState<SavedEquation[]>([])

  const [portOpen, setPortOpen] = useState(false)
  const [dependentOpen, setDependentOpen] = useState(false)
  // Set when the equation editor attaches to an existing variable
  // ("Add equation…" in the detail dialog) instead of minting a new one.
  const [dependentEditing, setDependentEditing] = useState<Variable | null>(null)
  // Last domain/class picked in either variable editor — offered as
  // defaults the next time one is opened.
  const [lastDomain, setLastDomain] = useState('')
  const [lastClass, setLastClass] = useState('')

  const [deleteTarget, setDeleteTarget] = useState<Variable | null>(null)
  const [selectedVariable, setSelectedVariable] = useState<Variable | null>(null)
  const [debugOpen, setDebugOpen] = useState(false)
  const { dirty: storeDirty, refresh: refreshDirty } = useStoreDirty()
  const [saveMsg, setSaveMsg] = useState('')
  // Host capability from /context — false when the backend has no TeX
  // toolchain (e.g. default Docker image); gates the PDF doc link.
  const [pdfCapable, setPdfCapable] = useState(false)

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
        setPdfCapable(ctx.capabilities?.pdf ?? false)
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

  // Persist an edited variable (detail dialog + inline table edits);
  // an optional equation is appended to the variable's equations.
  // Errors propagate so the caller can show the 409 lock message.
  const saveEditedVariable = useCallback(async (v: Variable, eq?: SavedEquation) => {
    await saveVariable(v, eq, variables)
    const ctx = await loadContext()
    setVariables(ctx.variables)
    setIndices(ctx.indices)
    setNetworkTree(ctx.network_tree)
    // A rename changes the displayed lhs of the variable's equations —
    // refresh them from the reloaded records (keeps session ast/check).
    const eqIds = new Set(Object.keys(v.equations ?? {}))
    setEquations((prev) => [
      ...prev.map((e) => (eqIds.has(e.id) ? { ...e, lhs: v.label } : e)),
      ...(eq ? [eq] : []),
    ])
    setSelectedVariable((prev) =>
      prev?.iri === v.iri
        ? (ctx.variables.find((x) => x.iri === v.iri) ?? prev)
        : prev,
    )
    refreshDirty()
  }, [refreshDirty, variables])

  // Equation editor accept — covers both "new dependent variable" and
  // "add equation to existing variable" (editing mode).
  const acceptDependent = useCallback((v: Variable, eq: SavedEquation) => {
    saveEditedVariable(v, eq).catch((err) =>
      console.error('Failed to save variable:', err),
    )
  }, [saveEditedVariable])

  const addPortVariable = useCallback((v: Variable) => {
    saveEditedVariable(v).catch((err) =>
      console.error('Failed to save variable:', err),
    )
  }, [saveEditedVariable])

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
          minHeight: 44,
          padding: '4px 16px',
          background: '#e0e0e0',
          display: 'flex',
          alignItems: 'center',
          columnGap: 16,
          rowGap: 4,
          flexWrap: 'wrap',
          borderBottom: '1px solid #ccc',
        }}
      >
        <strong
          style={{
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            minWidth: 0,
          }}
        >
          ProMo14 — Equation Editor
        </strong>
        <div
          style={{
            marginLeft: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            flexShrink: 0,
          }}
        >
          {storeDirty && (
            <span style={{ fontSize: 12, color: '#b8860b', whiteSpace: 'nowrap' }} title="Unsaved changes in the store">
              ● unsaved
            </span>
          )}
          {saveMsg && <span style={{ fontSize: 12, color: '#2e8b57', whiteSpace: 'nowrap' }}>{saveMsg}</span>}
          {pdfCapable && (
            <a
              href={documentUrl('pdf')}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: 12, whiteSpace: 'nowrap' }}
              title="Open the printable document as PDF (variables & equations)"
            >
              PDF doc
            </a>
          )}
          <a
            href={documentUrl('tex')}
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: 12, whiteSpace: 'nowrap' }}
            title="Open the LaTeX source (variables & equations)"
          >
            .tex
          </a>
          <button type="button" onClick={onSave} style={{ fontSize: 12 }}>
            Save
          </button>
        </div>
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
            <button
              type="button"
              onClick={() => {
                setDependentEditing(null)
                setDependentOpen(true)
              }}
            >
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 12, color: '#666' }}>
              {variables.length} variables ·{' '}
              {variables.reduce((n, v) => n + Object.keys(v.equations ?? {}).length, 0)}{' '}
              equations
            </span>
            <div style={{ flex: 1 }} />
            <button
              type="button"
              onClick={() => setDebugOpen(true)}
              style={{ fontSize: 12 }}
            >
              Debug equation context (JSON)…
            </button>
          </div>

          <VariableTable
            variables={variables}
            indices={indices}
            onSelect={setSelectedVariable}
            onSave={saveEditedVariable}
          />
        </div>
      </div>

      {selectedVariable && (
        <VariableDetailDialog
          variable={selectedVariable}
          indices={indices}
          networkTree={networkTree}
          onSave={saveEditedVariable}
          onAddEquation={(v) => {
            setDependentEditing(v)
            setDependentOpen(true)
          }}
          onClose={() => setSelectedVariable(null)}
        />
      )}

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
        onClose={() => {
          setDependentOpen(false)
          setDependentEditing(null)
        }}
        variables={variables}
        indices={indices}
        networkTree={networkTree}
        initialDomain={lastDomain}
        initialClass={lastClass}
        editing={dependentEditing}
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

    </div>
  )
}
