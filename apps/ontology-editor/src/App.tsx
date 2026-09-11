import { useEffect, useMemo, useState } from 'react'
import {
  createIndex,
  createNetwork,
  createVariable,
  listEquations,
  listNetworks,
  listTokens,
  loadOntologyContext,
  saveOntology,
  updateVariable,
} from './api'
import type {
  EquationRecord,
  IndexRecord,
  NetworkRecord,
  TokenRecord,
  VariableRecord,
} from './types'

const EMPTY_VARIABLE: VariableRecord = {
  iri: '',
  label: '',
  network: 'root',
  variable_class: 'state',
  units: [0, 0, 0, 0, 0, 0, 0, 0],
  index_structures: [],
  internal_id: '',
  aliases: {},
  doc: '',
  port_variable: false,
  tokens: [],
}

const EMPTY_INDEX: IndexRecord = {
  iri: '',
  label: '',
  short_name: '',
  network: 'root',
  index_class: 'index',
  internal_id: null,
  aliases: {},
  token: null,
}

const EMPTY_NETWORK: NetworkRecord = {
  iri: '',
  name: '',
  parent: null,
  children: [],
}

function collectNetworks(tree: Record<string, string[]>): string[] {
  const seen = new Set<string>()
  const visit = (name: string) => {
    if (seen.has(name)) return
    seen.add(name)
    for (const child of tree[name] || []) visit(child)
  }
  for (const root of Object.keys(tree)) visit(root)
  return Array.from(seen)
}

function descendants(tree: Record<string, string[]>, name: string): string[] {
  const result: string[] = []
  const visit = (n: string) => {
    result.push(n)
    for (const child of tree[n] || []) visit(child)
  }
  visit(name)
  return result
}

function buildParentMap(tree: Record<string, string[]>): Record<string, string> {
  const map: Record<string, string> = {}
  for (const [parent, children] of Object.entries(tree)) {
    for (const child of children) map[child] = parent
  }
  return map
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'variables' | 'indices' | 'networks' | 'tokens' | 'equations'>('variables')
  const [tree, setTree] = useState<Record<string, string[]>>({})
  const [selectedNetwork, setSelectedNetwork] = useState<string>('root')
  const [selectedVariable, setSelectedVariable] = useState<VariableRecord | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<IndexRecord | null>(null)
  const [draft, setDraft] = useState<VariableRecord>(EMPTY_VARIABLE)
  const [draftIndex, setDraftIndex] = useState<IndexRecord>(EMPTY_INDEX)
  const [draftNetwork, setDraftNetwork] = useState<NetworkRecord>(EMPTY_NETWORK)
  const [message, setMessage] = useState<string>('')

  const [networks, setNetworks] = useState<NetworkRecord[]>([])
  const [variables, setVariables] = useState<VariableRecord[]>([])
  const [indices, setIndices] = useState<IndexRecord[]>([])
  const [tokens, setTokens] = useState<TokenRecord[]>([])
  const [equations, setEquations] = useState<EquationRecord[]>([])

  const parentMap = useMemo(() => buildParentMap(tree), [tree])
  const networkNames = useMemo(() => collectNetworks(tree), [tree])

  const load = async () => {
    try {
      const ctx = await loadOntologyContext()
      setTree(ctx.network_tree)
      setVariables(ctx.variables)
      setIndices(ctx.indices)
      const nets = await listNetworks()
      setNetworks(nets)
      const toks = await listTokens()
      setTokens(toks)
      const eqs = await listEquations()
      setEquations(eqs)
    } catch (err) {
      setMessage(`Load failed: ${err}`)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const visibleVariables = useMemo(() => {
    if (selectedNetwork === 'all') return variables
    if (selectedNetwork === 'root') return variables
    const nets = new Set(descendants(tree, selectedNetwork))
    return variables.filter((v) => nets.has(v.network))
  }, [variables, selectedNetwork, tree])

  const onSelectVariable = (v: VariableRecord) => {
    setSelectedVariable(v)
    setDraft({ ...v })
  }

  const onNewVariable = () => {
    const v: VariableRecord = {
      ...EMPTY_VARIABLE,
      network: selectedNetwork === 'all' ? 'root' : selectedNetwork,
    }
    setSelectedVariable(null)
    setDraft(v)
  }

  const onSaveVariable = async () => {
    try {
      if (draft.iri) {
        await updateVariable(draft.iri, draft)
      } else {
        await createVariable(draft)
      }
      setMessage('Variable saved')
      await load()
    } catch (err) {
      setMessage(`Save failed: ${err}`)
    }
  }

  const onNewIndex = () => {
    setSelectedIndex(null)
    setDraftIndex({ ...EMPTY_INDEX, network: selectedNetwork === 'all' ? 'root' : selectedNetwork })
  }

  const onSaveIndex = async () => {
    try {
      await createIndex(draftIndex)
      setMessage('Index saved')
      await load()
    } catch (err) {
      setMessage(`Save failed: ${err}`)
    }
  }

  const onNewNetwork = () => {
    setDraftNetwork({ ...EMPTY_NETWORK })
  }

  const onSaveNetwork = async () => {
    try {
      await createNetwork(draftNetwork)
      setMessage('Network saved')
      await load()
    } catch (err) {
      setMessage(`Save failed: ${err}`)
    }
  }

  const onSaveOntology = async () => {
    try {
      const result = await saveOntology('ontology.trig')
      setMessage(`Saved ontology to ${result.saved}`)
    } catch (err) {
      setMessage(`Save failed: ${err}`)
    }
  }

  const styles: Record<string, React.CSSProperties> = {
    app: { display: 'flex', flexDirection: 'column', height: '100vh' },
    header: { display: 'flex', gap: 8, padding: 12, background: '#222', color: '#fff' },
    tab: { padding: '6px 12px', cursor: 'pointer', borderRadius: 4, border: 'none', background: '#444', color: '#fff' },
    activeTab: { background: '#0b7cbe' },
    body: { display: 'flex', flex: 1, overflow: 'hidden' },
    left: { width: 220, borderRight: '1px solid #ccc', background: '#fff', overflow: 'auto' },
    mid: { flex: 1, borderRight: '1px solid #ccc', background: '#fff', overflow: 'auto' },
    right: { width: 360, background: '#fafafa', overflow: 'auto', padding: 16 },
    listItem: { padding: '6px 12px', cursor: 'pointer', borderBottom: '1px solid #eee' },
    selected: { background: '#e0f2ff' },
    input: { width: '100%', marginBottom: 8, padding: 6 },
    textarea: { width: '100%', marginBottom: 8, padding: 6, minHeight: 60 },
    button: { padding: '8px 16px', cursor: 'pointer', marginRight: 8 },
    message: { padding: 8, background: '#fff3cd' },
  }

  const renderNetworkTree = () => (
    <div>
      {tree.root && (
        <div
          style={{ ...styles.listItem, ...(selectedNetwork === 'root' ? styles.selected : {}) }}
          onClick={() => setSelectedNetwork('root')}
        >
          root
        </div>
      )}
      {networkNames
        .filter((n) => n !== 'root')
        .sort()
        .map((n) => (
          <div
            key={n}
            style={{
              ...styles.listItem,
              paddingLeft: `${12 + (parentMap[n] ? 12 + (parentMap[parentMap[n]] ? 12 : 0) : 0)}px`,
              ...(selectedNetwork === n ? styles.selected : {}),
            }}
            onClick={() => setSelectedNetwork(n)}
          >
            {n}
          </div>
        ))}
    </div>
  )

  const renderVariables = () => (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: 12, borderBottom: '1px solid #ccc' }}>
        <button style={styles.button} onClick={onNewVariable}>
          New variable
        </button>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {visibleVariables.map((v) => (
          <div
            key={v.iri}
            style={{ ...styles.listItem, ...(selectedVariable?.iri === v.iri ? styles.selected : {}) }}
            onClick={() => onSelectVariable(v)}
          >
            <strong>{v.label}</strong> <span style={{ color: '#666' }}>({v.network})</span>
          </div>
        ))}
      </div>
    </div>
  )

  const renderVariableEditor = () => (
    <div>
      <h3>{selectedVariable ? 'Edit variable' : 'New variable'}</h3>
      <label>Label</label>
      <input style={styles.input} value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} />
      <label>Network</label>
      <select style={styles.input} value={draft.network} onChange={(e) => setDraft({ ...draft, network: e.target.value })}>
        {networkNames.map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
      <label>Class</label>
      <input style={styles.input} value={draft.variable_class} onChange={(e) => setDraft({ ...draft, variable_class: e.target.value })} />
      <label>Internal ID</label>
      <input style={styles.input} value={draft.internal_id} onChange={(e) => setDraft({ ...draft, internal_id: e.target.value })} />
      <label>Doc</label>
      <textarea style={styles.textarea} value={draft.doc} onChange={(e) => setDraft({ ...draft, doc: e.target.value })} />
      <label>Port variable</label>
      <input
        type="checkbox"
        checked={draft.port_variable}
        onChange={(e) => setDraft({ ...draft, port_variable: e.target.checked })}
      />
      <div style={{ marginTop: 12 }}>
        <button style={styles.button} onClick={onSaveVariable}>
          Save
        </button>
      </div>
    </div>
  )

  const renderIndices = () => (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: 12, borderBottom: '1px solid #ccc' }}>
        <button style={styles.button} onClick={onNewIndex}>
          New index
        </button>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {indices.map((i) => (
          <div key={i.iri} style={styles.listItem} onClick={() => { setSelectedIndex(i); setDraftIndex({ ...i }) }}>
            <strong>{i.label}</strong> <span style={{ color: '#666' }}>({i.network})</span>
          </div>
        ))}
      </div>
      <div style={{ padding: 12, borderTop: '1px solid #ccc' }}>
        <h3>{selectedIndex ? 'Edit index' : 'New index'}</h3>
        <label>Label</label>
        <input style={styles.input} value={draftIndex.label} onChange={(e) => setDraftIndex({ ...draftIndex, label: e.target.value })} />
        <label>Short name</label>
        <input style={styles.input} value={draftIndex.short_name} onChange={(e) => setDraftIndex({ ...draftIndex, short_name: e.target.value })} />
        <label>Network</label>
        <select style={styles.input} value={draftIndex.network} onChange={(e) => setDraftIndex({ ...draftIndex, network: e.target.value })}>
          {networkNames.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <button style={styles.button} onClick={onSaveIndex}>Save</button>
      </div>
    </div>
  )

  const renderNetworks = () => (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: 12, borderBottom: '1px solid #ccc' }}>
        <button style={styles.button} onClick={onNewNetwork}>
          New network
        </button>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {networks.map((n) => (
          <div key={n.iri} style={styles.listItem}>
            <strong>{n.name}</strong>
            {n.parent && <span style={{ color: '#666' }}> ← {n.parent}</span>}
          </div>
        ))}
      </div>
      <div style={{ padding: 12, borderTop: '1px solid #ccc' }}>
        <h3>New network</h3>
        <label>Name</label>
        <input style={styles.input} value={draftNetwork.name} onChange={(e) => setDraftNetwork({ ...draftNetwork, name: e.target.value })} />
        <label>Parent</label>
        <select style={styles.input} value={draftNetwork.parent || ''} onChange={(e) => setDraftNetwork({ ...draftNetwork, parent: e.target.value || null })}>
          <option value="">(none)</option>
          {networkNames.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <button style={styles.button} onClick={onSaveNetwork}>Save</button>
      </div>
    </div>
  )

  const renderTokens = () => (
    <div style={{ padding: 12 }}>
      <h3>Tokens</h3>
      {tokens.map((t) => (
        <div key={t.iri} style={styles.listItem}>
          <strong>{t.label}</strong> {t.parent && <span style={{ color: '#666' }}> → {t.parent}</span>}
        </div>
      ))}
    </div>
  )

  const renderEquations = () => (
    <div style={{ padding: 12 }}>
      <h3>Equations</h3>
      {equations.map((e) => (
        <div key={e.iri} style={styles.listItem}>
          <strong>{e.label}</strong> <span style={{ color: '#666' }}>({e.network})</span>
        </div>
      ))}
    </div>
  )

  return (
    <div style={styles.app}>
      <div style={styles.header}>
        <span style={{ fontWeight: 'bold', marginRight: 12 }}>ProMo14 Ontology Editor</span>
        <button style={{ ...styles.tab, ...(activeTab === 'variables' ? styles.activeTab : {}) }} onClick={() => setActiveTab('variables')}>
          Variables
        </button>
        <button style={{ ...styles.tab, ...(activeTab === 'indices' ? styles.activeTab : {}) }} onClick={() => setActiveTab('indices')}>
          Indices
        </button>
        <button style={{ ...styles.tab, ...(activeTab === 'networks' ? styles.activeTab : {}) }} onClick={() => setActiveTab('networks')}>
          Networks
        </button>
        <button style={{ ...styles.tab, ...(activeTab === 'tokens' ? styles.activeTab : {}) }} onClick={() => setActiveTab('tokens')}>
          Tokens
        </button>
        <button style={{ ...styles.tab, ...(activeTab === 'equations' ? styles.activeTab : {}) }} onClick={() => setActiveTab('equations')}>
          Equations
        </button>
        <div style={{ flex: 1 }} />
        <button style={{ ...styles.tab, background: '#0b7cbe' }} onClick={onSaveOntology}>
          Save ontology
        </button>
      </div>
      {message && <div style={styles.message}>{message}</div>}
      <div style={styles.body}>
        {activeTab === 'variables' && (
          <>
            <div style={styles.left}>{renderNetworkTree()}</div>
            <div style={styles.mid}>{renderVariables()}</div>
            <div style={styles.right}>{renderVariableEditor()}</div>
          </>
        )}
        {activeTab === 'indices' && <div style={{ flex: 1, display: 'flex' }}>{renderIndices()}</div>}
        {activeTab === 'networks' && <div style={{ flex: 1, display: 'flex' }}>{renderNetworks()}</div>}
        {activeTab === 'tokens' && <div style={{ flex: 1, display: 'flex' }}>{renderTokens()}</div>}
        {activeTab === 'equations' && <div style={{ flex: 1, display: 'flex' }}>{renderEquations()}</div>}
      </div>
    </div>
  )
}
