import { useCallback, useEffect, useState } from 'react'
import { demoIndices, demoNetworkTree } from './demoContext'
import { deleteVariable, documentUrl, listTokens, loadContext, saveOntology, saveVariable } from './api'
import { useStoreDirty } from '@promo/ui'
import type { ClassificationAxis, Domain, EquationClass, EquationRecord, Index, NetworkTree, SavedEquation, TokenRecord, Variable } from './types'
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
  const [axes, setAxes] = useState<ClassificationAxis[]>([])
  const [domains, setDomains] = useState<Domain[]>([])
  const [equationClasses, setEquationClasses] = useState<EquationClass[]>([])
  const [tokenCatalogue, setTokenCatalogue] = useState<TokenRecord[]>([])
  const [expressionNetwork, setExpressionNetwork] = useState('root')

  const [equations, setEquations] = useState<SavedEquation[]>([])

  const [portOpen, setPortOpen] = useState(false)
  const [dependentOpen, setDependentOpen] = useState(false)
  // Set when the equation editor attaches to an existing variable
  // ("Add equation…" in the detail dialog) instead of minting a new one.
  const [dependentEditing, setDependentEditing] = useState<Variable | null>(null)
  // Set when a stored equation is being rewritten — the editor updates
  // the equations entry instead of appending one.
  const [editingEquation, setEditingEquation] = useState<{ id: string; record: EquationRecord } | null>(null)
  // Last domain/classifications picked in either variable editor —
  // offered as defaults the next time one is opened.
  const [lastDomain, setLastDomain] = useState('')
  const [lastClassifications, setLastClassifications] = useState<Record<string, string>>({})

  const [deleteTarget, setDeleteTarget] = useState<Variable | null>(null)
  const [selectedVariable, setSelectedVariable] = useState<Variable | null>(null)
  const [debugOpen, setDebugOpen] = useState(false)
  const { dirty: storeDirty, refresh: refreshDirty } = useStoreDirty()
  const [saveMsg, setSaveMsg] = useState('')
  // Async save/load failures — stays up until dismissed (unlike saveMsg
  // which auto-clears); without this a failed POST is invisible.
  const [saveErr, setSaveErr] = useState('')
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
        setAxes(ctx.axes ?? [])
        setDomains(ctx.domains ?? [])
        setEquationClasses(ctx.equation_classes ?? [])
        setPdfCapable(ctx.capabilities?.pdf ?? false)
        listTokens().then(setTokenCatalogue).catch(() => {})
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
      .catch((err) => {
        console.error('Failed to load context:', err)
        setSaveErr(`Failed to load context: ${err}`)
      })
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
    setAxes(ctx.axes ?? [])
    setDomains(ctx.domains ?? [])
    setEquationClasses(ctx.equation_classes ?? [])
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
    setDependentEditing((prev) =>
      prev?.iri === v.iri
        ? (ctx.variables.find((x) => x.iri === v.iri) ?? prev)
        : prev,
    )
    refreshDirty()
  }, [refreshDirty, variables])

  // Equation editor accept — covers both "new dependent variable" and
  // "add equation to existing variable" (editing mode).
  const acceptDependent = useCallback((v: Variable, eq: SavedEquation) => {
    saveEditedVariable(v, eq).catch((err) => {
      console.error('Failed to save variable:', err)
      setSaveErr(`Failed to save variable: ${err}`)
    })
  }, [saveEditedVariable])

  // Variable-only save from the equation editor (e.g. a LaTeX-symbol
  // edit while attaching an equation) — no new equation appended.
  const saveOnlyVariable = useCallback((v: Variable) => {
    saveEditedVariable(v).catch((err) => {
      console.error('Failed to save variable:', err)
      setSaveErr(`Failed to save variable: ${err}`)
    })
  }, [saveEditedVariable])

  const addPortVariable = useCallback((v: Variable) => {
    saveEditedVariable(v).catch((err) => {
      console.error('Failed to save variable:', err)
      setSaveErr(`Failed to save variable: ${err}`)
    })
  }, [saveEditedVariable])

  const removeEquation = useCallback((id: string) => {
    setEquations((prev) => prev.filter((eq) => eq.id !== id))
  }, [])

  // Open the equation editor on an existing stored equation — the
  // variable is the owner found via the equations dict key.
  const openEquationEditor = useCallback((v: Variable, eqId: string) => {
    const record = v.equations?.[eqId]
    if (!record) return
    setDependentEditing(v)
    setEditingEquation({ id: eqId, record })
    setDependentOpen(true)
  }, [])

  const selectEquation = useCallback((eq: SavedEquation) => {
    const owner = variables.find((v) => v.equations && eq.id in v.equations)
    if (owner) openEquationEditor(owner, eq.id)
  }, [variables, openEquationEditor])

  const removeVariable = useCallback(async (impact: DeleteImpact) => {
    // Brutal delete: one backend call removes the whole dependency cone
    // (the dialog's impact list is the same cone, computed client-side).
    // 409s surface in the banner — nothing is deleted or unfrozen.
    try {
      await deleteVariable(impact.target.iri, true)
    } catch (err) {
      console.error('Failed to delete variable:', impact.target.iri, err)
      setSaveErr(`Failed to delete variable: ${err}`)
      setDeleteTarget(null)
      return
    }
    // Rebuild from reloaded truth — the cascade can reach variables the
    // client-side impact didn't predict (e.g. foreign-graph refs).
    const ctx = await loadContext()
    setVariables(ctx.variables)
    const saved: SavedEquation[] = []
    for (const v of ctx.variables) {
      if (v.equations) {
        for (const [eqId, eq] of Object.entries(v.equations)) {
          saved.push({ id: eqId, lhs: v.label, text: eq.rhs, ast: null, check: null })
        }
      }
    }
    setEquations(saved)
    refreshDirty()
    setDeleteTarget(null)
  }, [refreshDirty])

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
          {saveErr && (
            <span style={{ fontSize: 12, color: '#c62828', whiteSpace: 'nowrap' }}>
              {saveErr}
              <button
                type="button"
                onClick={() => setSaveErr('')}
                style={{ marginLeft: 6, fontSize: 11 }}
                title="Dismiss"
              >
                ×
              </button>
            </span>
          )}
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
                setEditingEquation(null)
                setDependentOpen(true)
              }}
            >
              New dependent variable…
            </button>
          </div>
          <VariablePalette
            variables={variables}
            indices={indices}
            onDelete={setDeleteTarget}
            onSelect={setSelectedVariable}
          />
          <EquationList
            equations={equations}
            onSelect={selectEquation}
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
            axes={axes}
            equationClasses={equationClasses}
            onSelect={setSelectedVariable}
            onEditEquation={openEquationEditor}
            onSave={saveEditedVariable}
          />
        </div>
      </div>

      {selectedVariable && (
        <VariableDetailDialog
          variable={selectedVariable}
          indices={indices}
          networkTree={networkTree}
          axes={axes}
          domains={domains}
          equationClasses={equationClasses}
          tokenCatalogue={tokenCatalogue}
          onSave={saveEditedVariable}
          onAddEquation={(v) => {
            setDependentEditing(v)
            setEditingEquation(null)
            setDependentOpen(true)
          }}
          onEditEquation={(v, eqId) => {
            setSelectedVariable(null)
            openEquationEditor(v, eqId)
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
        axes={axes}
        domains={domains}
        initialDomain={lastDomain}
        initialClassifications={lastClassifications}
        onDefaultsChange={(d, c) => {
          setLastDomain(d)
          setLastClassifications(c)
        }}
        onAccept={addPortVariable}
      />

      <DeleteVariableDialog
        open={!!deleteTarget}
        target={deleteTarget}
        variables={variables}
        equations={equations}
        indices={indices}
        onClose={() => setDeleteTarget(null)}
        onConfirm={removeVariable}
      />

      <DependentVariableEditor
        open={dependentOpen}
        onClose={() => {
          setDependentOpen(false)
          setDependentEditing(null)
          setEditingEquation(null)
        }}
        variables={variables}
        indices={indices}
        networkTree={networkTree}
        axes={axes}
        domains={domains}
        equationClasses={equationClasses}
        initialDomain={lastDomain}
        initialClassifications={lastClassifications}
        editing={dependentEditing}
        editingEquation={editingEquation}
        onDefaultsChange={(d, c) => {
          setLastDomain(d)
          setLastClassifications(c)
        }}
        onAccept={acceptDependent}
        onSaveVariable={saveOnlyVariable}
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
