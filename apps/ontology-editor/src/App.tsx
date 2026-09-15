import { useEffect, useState } from 'react'
import {
  createAxis,
  createAxisTerm,
  createConnectionRule,
  createDomain,
  createEntityType,
  createIndex,
  createScaleDimension,
  createScaleValue,
  createToken,
  deleteAxis,
  deleteAxisTerm,
  deleteConnectionRule,
  deleteDomain,
  deleteEntityType,
  deleteIndex,
  deleteScaleDimension,
  deleteScaleValue,
  deleteToken,
  listScaleValues,
  listTokens,
  loadOntologyContext,
  saveOntology,
} from './api'
import type {
  AxisTermRecord,
  ClassificationAxisRecord,
  ConnectionRuleRecord,
  DomainRecord,
  EntityTypeRecord,
  IndexRecord,
  ScaleDimensionRecord,
  ScaleValueRecord,
  TokenRecord,
} from './types'

// ---------------------------------------------------------------------------
// Empty records
// ---------------------------------------------------------------------------

const EMPTY_TOKEN: TokenRecord = { iri: '', label: '', parent: null }
const EMPTY_DOMAIN: DomainRecord = { iri: '', name: '', label: null, parent: null, branch: null, children: [], tokens: [], inherited_tokens: [] }
const EMPTY_AXIS: ClassificationAxisRecord = { iri: '', domain: '', name: '', parent: null, terms: [] }
const EMPTY_AXIS_TERM: AxisTermRecord = { iri: '', axis: '', label: '', parent: null }
const EMPTY_SCALE_DIM: ScaleDimensionRecord = { iri: '', name: '', domain: '', parent: null, values: [] }
const EMPTY_SCALE_VAL: ScaleValueRecord = { iri: '', dimension: '', label: '', parent: null }
const EMPTY_ENTITY_TYPE: EntityTypeRecord = { iri: '', label: '', temporal_type: 'dynamic', spatial_type: null, spatial_size: null, branch: 'physical', scale_values: [], description: '' }
const EMPTY_INDEX: IndexRecord = { iri: '', label: '', short_name: '', network: 'root', index_class: 'index', internal_id: null, aliases: {}, token: null }
const EMPTY_RULE: ConnectionRuleRecord = { iri: '', rule_type: 'physical-same', source_domain: null, target_domain: null, shared_tokens: [], direction: 'bidirectional', carrier: 'token-flow', scope: 'same', description: '' }

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Stage = 'tokens' | 'domains' | 'axes' | 'scales' | 'entity-types' | 'indices' | 'rules'

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const S: Record<string, React.CSSProperties> = {
  app: { display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'sans-serif' },
  header: { display: 'flex', gap: 4, padding: '8px 12px', background: '#1a1a2e', color: '#fff', alignItems: 'center', flexWrap: 'wrap' },
  tab: { padding: '6px 12px', cursor: 'pointer', borderRadius: 4, border: 'none', background: '#333', color: '#ccc', fontSize: 13 },
  tabActive: { background: '#0b7cbe', color: '#fff' },
  tabDisabled: { background: '#222', color: '#555', cursor: 'not-allowed' },
  body: { display: 'flex', flex: 1, overflow: 'hidden' },
  left: { width: 280, borderRight: '1px solid #ddd', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
  leftHeader: { padding: '8px 12px', borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  leftList: { flex: 1, overflow: 'auto' },
  listItem: { padding: '6px 12px', cursor: 'pointer', borderBottom: '1px solid #f0f0f0', fontSize: 13 },
  listItemSelected: { background: '#e0f2ff' },
  right: { flex: 1, padding: 16, overflow: 'auto' },
  input: { width: '100%', marginBottom: 8, padding: 6, boxSizing: 'border-box' },
  select: { width: '100%', marginBottom: 8, padding: 6, boxSizing: 'border-box' },
  textarea: { width: '100%', marginBottom: 8, padding: 6, minHeight: 50, boxSizing: 'border-box' },
  button: { padding: '6px 14px', cursor: 'pointer', marginRight: 8, border: '1px solid #0b7cbe', background: '#0b7cbe', color: '#fff', borderRadius: 4, fontSize: 13 },
  buttonDanger: { padding: '6px 14px', cursor: 'pointer', marginRight: 8, border: '1px solid #c0392b', background: '#c0392b', color: '#fff', borderRadius: 4, fontSize: 13 },
  buttonGhost: { padding: '4px 10px', cursor: 'pointer', border: '1px solid #ccc', background: '#fff', color: '#333', borderRadius: 4, fontSize: 12 },
  label: { fontSize: 12, color: '#666', marginBottom: 2, display: 'block' },
  message: { padding: '6px 12px', background: '#fff3cd', fontSize: 13 },
  section: { marginBottom: 16 },
  h3: { margin: '0 0 8px 0', fontSize: 15 },
  indented: { marginLeft: 16 },
  muted: { color: '#999', fontSize: 11 },
  badge: { display: 'inline-block', padding: '1px 6px', borderRadius: 3, fontSize: 11, marginLeft: 4 },
}

// ---------------------------------------------------------------------------
// Helper: build tree from flat list with parent
// ---------------------------------------------------------------------------

function buildTree<T extends { iri: string; parent: string | null }>(
  items: T[],
): { item: T; children: T[]; depth: number }[] {
  const byIri = new Map(items.map((i) => [i.iri, i]))
  const result: { item: T; children: T[]; depth: number }[] = []
  const visited = new Set<string>()

  const visit = (item: T, depth: number) => {
    if (visited.has(item.iri)) return
    visited.add(item.iri)
    const children = items.filter((i) => i.parent === item.iri)
    result.push({ item, children, depth })
    for (const child of children) visit(child, depth + 1)
  }

  for (const item of items) {
    if (!item.parent || !byIri.has(item.parent)) visit(item, 0)
  }
  // Also visit orphans
  for (const item of items) {
    if (!visited.has(item.iri)) visit(item, 0)
  }

  return result
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  const [stage, setStage] = useState<Stage>('tokens')
  const [message, setMessage] = useState('')

  // Data
  const [tokens, setTokens] = useState<TokenRecord[]>([])
  const [domains, setDomains] = useState<DomainRecord[]>([])
  const [axes, setAxes] = useState<ClassificationAxisRecord[]>([])
  const [scaleDims, setScaleDims] = useState<ScaleDimensionRecord[]>([])
  const [scaleVals, setScaleVals] = useState<ScaleValueRecord[]>([])
  const [entityTypes, setEntityTypes] = useState<EntityTypeRecord[]>([])
  const [indices, setIndices] = useState<IndexRecord[]>([])
  const [rules, setRules] = useState<ConnectionRuleRecord[]>([])

  // Drafts
  const [draftToken, setDraftToken] = useState<TokenRecord>(EMPTY_TOKEN)
  const [draftDomain, setDraftDomain] = useState<DomainRecord>(EMPTY_DOMAIN)
  const [draftAxis, setDraftAxis] = useState<ClassificationAxisRecord>(EMPTY_AXIS)
  const [draftAxisTerm, setDraftAxisTerm] = useState<AxisTermRecord>(EMPTY_AXIS_TERM)
  const [draftScaleDim, setDraftScaleDim] = useState<ScaleDimensionRecord>(EMPTY_SCALE_DIM)
  const [draftScaleVal, setDraftScaleVal] = useState<ScaleValueRecord>(EMPTY_SCALE_VAL)
  const [draftEntityType, setDraftEntityType] = useState<EntityTypeRecord>(EMPTY_ENTITY_TYPE)
  const [draftIndex, setDraftIndex] = useState<IndexRecord>(EMPTY_INDEX)
  const [draftRule, setDraftRule] = useState<ConnectionRuleRecord>(EMPTY_RULE)

  // Selected items
  const [selToken, setSelToken] = useState<string | null>(null)
  const [selDomain, setSelDomain] = useState<string | null>(null)
  const [selAxis, setSelAxis] = useState<string | null>(null)
  const [selScaleDim, setSelScaleDim] = useState<string | null>(null)
  const [selEntityType, setSelEntityType] = useState<string | null>(null)
  const [selIndex, setSelIndex] = useState<string | null>(null)
  const [selRule, setSelRule] = useState<string | null>(null)

  // Stage availability
  const hasTokens = tokens.length > 0
  const hasDomains = domains.length > 0
  const hasScales = scaleDims.length > 0
  const load = async () => {
    try {
      const ctx = await loadOntologyContext()
      setIndices(ctx.indices)
      setDomains(ctx.domains || [])
      setAxes(ctx.axes || [])
      setScaleDims(ctx.scale_dimensions || [])
      setEntityTypes(ctx.entity_types || [])
      setRules(ctx.connection_rules || [])
      const toks = await listTokens()
      setTokens(toks)
      const svals = await listScaleValues()
      setScaleVals(svals)
    } catch (err) {
      setMessage(`Load failed: ${err}`)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const msg = (m: string) => { setMessage(m); setTimeout(() => setMessage(''), 3000) }

  const onSaveOntology = async () => {
    try {
      const result = await saveOntology('ontology.trig')
      msg(`Saved to ${result.saved}`)
    } catch (err) {
      msg(`Save failed: ${err}`)
    }
  }

  const onDelete = async (iri: string, fn: (iri: string) => Promise<{ deleted: string }>, name: string) => {
    try {
      await fn(iri)
      msg(`${name} deleted`)
      await load()
    } catch (err) {
      msg(`Delete failed: ${err}`)
    }
  }

  // Flatten scale values with parent labels for display
  const scaleValLabel = (iri: string): string => {
    const v = scaleVals.find((s) => s.iri === iri)
    if (!v) return iri
    if (v.parent) {
      const p = scaleVals.find((s) => s.iri === v.parent)
      return p ? `${p.label}/${v.label}` : v.label
    }
    return v.label
  }

  // Token label helper
  const domainName = (iri: string): string => domains.find((d) => d.iri === iri)?.name || iri

  // =========================================================================
  // Render: Tokens
  // =========================================================================

  const renderTokens = () => (
    <>
      <div style={S.left}>
        <div style={S.leftHeader}>
          <span style={{ fontWeight: 'bold', fontSize: 13 }}>Tokens</span>
          <button style={S.buttonGhost} onClick={() => { setSelToken(null); setDraftToken(EMPTY_TOKEN) }}>+ New</button>
        </div>
        <div style={S.leftList}>
          {buildTree(tokens).map(({ item, depth }) => (
            <div
              key={item.iri}
              style={{ ...S.listItem, paddingLeft: 12 + depth * 16, ...(selToken === item.iri ? S.listItemSelected : {}) }}
              onClick={() => { setSelToken(item.iri); setDraftToken({ ...item }) }}
            >
              <strong>{item.label}</strong>
              <button
                style={{ ...S.buttonGhost, float: 'right', padding: '2px 6px' }}
                onClick={(e) => { e.stopPropagation(); onDelete(item.iri, deleteToken, 'Token') }}
              >x</button>
            </div>
          ))}
        </div>
      </div>
      <div style={S.right}>
        <h3 style={S.h3}>{selToken ? 'Edit token' : 'New token'}</h3>
        <label style={S.label}>Label</label>
        <input style={S.input} value={draftToken.label} onChange={(e) => setDraftToken({ ...draftToken, label: e.target.value })} />
        <label style={S.label}>Parent (optional)</label>
        <select style={S.select} value={draftToken.parent || ''} onChange={(e) => setDraftToken({ ...draftToken, parent: e.target.value || null })}>
          <option value="">(none)</option>
          {tokens.filter((t) => t.iri !== draftToken.iri).map((t) => (
            <option key={t.iri} value={t.iri}>{t.label}</option>
          ))}
        </select>
        <button style={S.button} disabled={!draftToken.label.trim()} onClick={async () => {
          if (!draftToken.label.trim()) { msg('Label must not be empty'); return }
          try { await createToken(draftToken); msg('Token saved'); await load() } catch (err) { msg(`Save failed: ${err}`) }
        }}>Save</button>
      </div>
    </>
  )

  // =========================================================================
  // Render: Domains
  // =========================================================================

  const renderDomains = () => (
    <>
      <div style={S.left}>
        <div style={S.leftHeader}>
          <span style={{ fontWeight: 'bold', fontSize: 13 }}>Domains</span>
          <button style={S.buttonGhost} onClick={() => { setSelDomain(null); setDraftDomain(EMPTY_DOMAIN) }}>+ New</button>
        </div>
        <div style={S.leftList}>
          {buildTree(domains).map(({ item, depth }) => (
            <div
              key={item.iri}
              style={{ ...S.listItem, paddingLeft: 12 + depth * 16, ...(selDomain === item.iri ? S.listItemSelected : {}) }}
              onClick={() => { setSelDomain(item.iri); setDraftDomain({ ...item }) }}
            >
              <strong>{item.name}</strong>
              {item.branch && <span style={{ ...S.badge, background: '#e8f4fd' }}>{item.branch}</span>}
              {item.tokens.length > 0 && <span style={S.muted}> ({item.tokens.length} tokens)</span>}
              <button
                style={{ ...S.buttonGhost, float: 'right', padding: '2px 6px' }}
                onClick={(e) => { e.stopPropagation(); onDelete(item.iri, deleteDomain, 'Domain') }}
              >x</button>
            </div>
          ))}
        </div>
      </div>
      <div style={S.right}>
        <h3 style={S.h3}>{selDomain ? 'Edit domain' : 'New domain'}</h3>
        <label style={S.label}>Name</label>
        <input style={S.input} value={draftDomain.name} onChange={(e) => setDraftDomain({ ...draftDomain, name: e.target.value })} />
        <label style={S.label}>Parent</label>
        <select style={S.select} value={draftDomain.parent || ''} onChange={(e) => {
          const parentIri = e.target.value || null
          const parent = domains.find((d) => d.iri === parentIri)
          const inherited = parent ? [...parent.inherited_tokens, ...parent.tokens] : []
          setDraftDomain({ ...draftDomain, parent: parentIri, inherited_tokens: inherited })
        }}>
          <option value="">(none — top level)</option>
          {domains.filter((d) => d.iri !== draftDomain.iri).map((d) => (
            <option key={d.iri} value={d.iri}>{d.name}</option>
          ))}
        </select>
        <label style={S.label}>Branch (top-level only)</label>
        <select style={S.select} value={draftDomain.branch || ''} onChange={(e) => setDraftDomain({ ...draftDomain, branch: e.target.value || null })}>
          <option value="">(none)</option>
          <option value="physical">physical</option>
          <option value="information">information</option>
        </select>
        <label style={S.label}>Tokens</label>
        <div style={{ marginBottom: 8, maxHeight: 160, overflow: 'auto', border: '1px solid #ddd', padding: 4 }}>
          {tokens.map((t) => {
            const isInherited = draftDomain.inherited_tokens.includes(t.iri)
            const isOwn = draftDomain.tokens.includes(t.iri)
            return (
              <label key={t.iri} style={{ display: 'block', fontSize: 12, color: isInherited ? '#999' : undefined }}>
                <input
                  type="checkbox"
                  checked={isOwn || isInherited}
                  disabled={isInherited}
                  onChange={(e) => {
                    if (isInherited) return
                    const next = e.target.checked
                      ? [...draftDomain.tokens, t.iri]
                      : draftDomain.tokens.filter((x) => x !== t.iri)
                    setDraftDomain({ ...draftDomain, tokens: next })
                  }}
                /> {t.label}{isInherited ? ' (inherited)' : ''}
              </label>
            )
          })}
        </div>
        <button style={S.button} onClick={async () => {
          try { await createDomain(draftDomain); msg('Domain saved'); await load() } catch (err) { msg(`Save failed: ${err}`) }
        }}>Save</button>
      </div>
    </>
  )

  // =========================================================================
  // Render: Axes
  // =========================================================================

  const renderAxes = () => (
    <>
      <div style={S.left}>
        <div style={S.leftHeader}>
          <span style={{ fontWeight: 'bold', fontSize: 13 }}>Classification Axes</span>
          <button style={S.buttonGhost} onClick={() => { setSelAxis(null); setDraftAxis(EMPTY_AXIS) }}>+ New</button>
        </div>
        <div style={S.leftList}>
          {axes.map((axis) => (
            <div key={axis.iri}>
              <div
                style={{ ...S.listItem, ...(selAxis === axis.iri ? S.listItemSelected : {}) }}
                onClick={() => { setSelAxis(axis.iri); setDraftAxis({ ...axis }) }}
              >
                <strong>{axis.name}</strong>
                <span style={S.muted}> ({domainName(axis.domain)})</span>
                <button
                  style={{ ...S.buttonGhost, float: 'right', padding: '2px 6px' }}
                  onClick={(e) => { e.stopPropagation(); onDelete(axis.iri, deleteAxis, 'Axis') }}
                >x</button>
              </div>
              {buildTree(axis.terms).map(({ item: term, depth }) => (
                <div key={term.iri} style={{ ...S.listItem, paddingLeft: 20 + depth * 14, fontSize: 12, color: '#666' }}
                  onClick={() => { setDraftAxisTerm({ ...term }) }}
                >
                  {depth > 0 ? '└─ ' : '• '}{term.label}
                  <button
                    style={{ ...S.buttonGhost, float: 'right', padding: '1px 5px', fontSize: 10 }}
                    onClick={(e) => { e.stopPropagation(); onDelete(term.iri, deleteAxisTerm, 'Term') }}
                  >x</button>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div style={S.right}>
        <h3 style={S.h3}>{selAxis ? 'Edit axis' : 'New axis'}</h3>
        <label style={S.label}>Name</label>
        <input style={S.input} value={draftAxis.name} onChange={(e) => setDraftAxis({ ...draftAxis, name: e.target.value })} />
        <label style={S.label}>Domain</label>
        <select style={S.select} value={draftAxis.domain} onChange={(e) => setDraftAxis({ ...draftAxis, domain: e.target.value })}>
          <option value="">(select domain)</option>
          {domains.map((d) => (
            <option key={d.iri} value={d.iri}>{d.name}</option>
          ))}
        </select>
        <button style={S.button} onClick={async () => {
          try { await createAxis(draftAxis); msg('Axis saved'); await load() } catch (err) { msg(`Save failed: ${err}`) }
        }}>Save axis</button>

        <div style={{ ...S.section, marginTop: 24, borderTop: '1px solid #eee', paddingTop: 12 }}>
          <h3 style={S.h3}>Add term to axis</h3>
          <label style={S.label}>Axis</label>
          <select style={S.select} value={draftAxisTerm.axis} onChange={(e) => setDraftAxisTerm({ ...draftAxisTerm, axis: e.target.value, parent: null })}>
            <option value="">(select axis)</option>
            {axes.map((a) => (
              <option key={a.iri} value={a.iri}>{a.name} ({domainName(a.domain)})</option>
            ))}
          </select>
          <label style={S.label}>Label</label>
          <input style={S.input} value={draftAxisTerm.label} onChange={(e) => setDraftAxisTerm({ ...draftAxisTerm, label: e.target.value })} />
          <label style={S.label}>Parent (optional, for hierarchy)</label>
          <select style={S.select} value={draftAxisTerm.parent || ''} onChange={(e) => setDraftAxisTerm({ ...draftAxisTerm, parent: e.target.value || null })}>
            <option value="">(none — root)</option>
            {axes.flatMap((a) => a.terms).filter((t) => t.axis === draftAxisTerm.axis).map((t) => (
              <option key={t.iri} value={t.iri}>{t.label}</option>
            ))}
          </select>
          <button style={S.button} disabled={!draftAxisTerm.axis || !draftAxisTerm.label.trim()} onClick={async () => {
            if (!draftAxisTerm.axis) { msg('Select an axis first'); return }
            if (!draftAxisTerm.label.trim()) { msg('Label must not be empty'); return }
            try { await createAxisTerm(draftAxisTerm); msg('Term saved'); await load() } catch (err) { msg(`Save failed: ${err}`) }
          }}>Save term</button>
        </div>
      </div>
    </>
  )

  // =========================================================================
  // Render: Scales
  // =========================================================================

  const renderScales = () => (
    <>
      <div style={S.left}>
        <div style={S.leftHeader}>
          <span style={{ fontWeight: 'bold', fontSize: 13 }}>Scale Dimensions</span>
          <button style={S.buttonGhost} onClick={() => { setSelScaleDim(null); setDraftScaleDim(EMPTY_SCALE_DIM) }}>+ New</button>
        </div>
        <div style={S.leftList}>
          {scaleDims.map((dim) => (
            <div key={dim.iri}>
              <div
                style={{ ...S.listItem, ...(selScaleDim === dim.iri ? S.listItemSelected : {}) }}
                onClick={() => { setSelScaleDim(dim.iri); setDraftScaleDim({ ...dim }) }}
              >
                <strong>{dim.name}</strong>
                <span style={S.muted}> ({domainName(dim.domain)})</span>
                <button
                  style={{ ...S.buttonGhost, float: 'right', padding: '2px 6px' }}
                  onClick={(e) => { e.stopPropagation(); onDelete(dim.iri, deleteScaleDimension, 'Scale dimension') }}
                >x</button>
              </div>
              {buildTree(dim.values).map(({ item, depth }) => (
                <div key={item.iri} style={{ ...S.listItem, paddingLeft: 12 + depth * 16, fontSize: 12, color: '#666' }}
                  onClick={() => setDraftScaleVal({ ...item })}
                >
                  {item.parent ? '└─ ' : '• '}{item.label}
                  <button
                    style={{ ...S.buttonGhost, float: 'right', padding: '1px 5px', fontSize: 10 }}
                    onClick={(e) => { e.stopPropagation(); onDelete(item.iri, deleteScaleValue, 'Scale value') }}
                  >x</button>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div style={S.right}>
        <h3 style={S.h3}>{selScaleDim ? 'Edit scale dimension' : 'New scale dimension'}</h3>
        <label style={S.label}>Name</label>
        <input style={S.input} value={draftScaleDim.name} onChange={(e) => setDraftScaleDim({ ...draftScaleDim, name: e.target.value })} />
        <label style={S.label}>Domain</label>
        <select style={S.select} value={draftScaleDim.domain} onChange={(e) => setDraftScaleDim({ ...draftScaleDim, domain: e.target.value })}>
          <option value="">(select domain)</option>
          {domains.map((d) => (
            <option key={d.iri} value={d.iri}>{d.name}</option>
          ))}
        </select>
        <button style={S.button} onClick={async () => {
          try { await createScaleDimension(draftScaleDim); msg('Scale dimension saved'); await load() } catch (err) { msg(`Save failed: ${err}`) }
        }}>Save dimension</button>

        <div style={{ ...S.section, marginTop: 24, borderTop: '1px solid #eee', paddingTop: 12 }}>
          <h3 style={S.h3}>Add scale value</h3>
          <label style={S.label}>Dimension</label>
          <select style={S.select} value={draftScaleVal.dimension} onChange={(e) => setDraftScaleVal({ ...draftScaleVal, dimension: e.target.value })}>
            <option value="">(select dimension)</option>
            {scaleDims.map((d) => (
              <option key={d.iri} value={d.iri}>{d.name}</option>
            ))}
          </select>
          <label style={S.label}>Label</label>
          <input style={S.input} value={draftScaleVal.label} onChange={(e) => setDraftScaleVal({ ...draftScaleVal, label: e.target.value })} />
          <label style={S.label}>Parent (optional, for hierarchy — e.g. triple domain children)</label>
          <select style={S.select} value={draftScaleVal.parent || ''} onChange={(e) => setDraftScaleVal({ ...draftScaleVal, parent: e.target.value || null })}>
            <option value="">(none — root level)</option>
            {scaleVals.filter((v) => v.dimension === draftScaleVal.dimension && v.iri !== draftScaleVal.iri).map((v) => (
              <option key={v.iri} value={v.iri}>{scaleValLabel(v.iri)}</option>
            ))}
          </select>
          <button style={S.button} onClick={async () => {
            try { await createScaleValue(draftScaleVal); msg('Scale value saved'); await load() } catch (err) { msg(`Save failed: ${err}`) }
          }}>Save value</button>
        </div>
      </div>
    </>
  )

  // =========================================================================
  // Render: Entity Types
  // =========================================================================

  const renderEntityTypes = () => (
    <>
      <div style={S.left}>
        <div style={S.leftHeader}>
          <span style={{ fontWeight: 'bold', fontSize: 13 }}>Entity Types</span>
          <button style={S.buttonGhost} onClick={() => { setSelEntityType(null); setDraftEntityType(EMPTY_ENTITY_TYPE) }}>+ New</button>
        </div>
        <div style={S.leftList}>
          {entityTypes.map((et) => (
            <div
              key={et.iri}
              style={{ ...S.listItem, ...(selEntityType === et.iri ? S.listItemSelected : {}) }}
              onClick={() => { setSelEntityType(et.iri); setDraftEntityType({ ...et }) }}
            >
              <strong>{et.label}</strong>
              <span style={S.muted}> [{et.branch}]</span>
              <button
                style={{ ...S.buttonGhost, float: 'right', padding: '2px 6px' }}
                onClick={(e) => { e.stopPropagation(); onDelete(et.iri, deleteEntityType, 'Entity type') }}
              >x</button>
              {et.scale_values.length > 0 && (
                <div style={S.muted}>
                  {et.scale_values.map((sv) => scaleValLabel(sv)).join(' + ')}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      <div style={S.right}>
        <h3 style={S.h3}>{selEntityType ? 'Edit entity type' : 'New entity type'}</h3>
        <label style={S.label}>Label</label>
        <input style={S.input} value={draftEntityType.label} onChange={(e) => setDraftEntityType({ ...draftEntityType, label: e.target.value })} />
        <label style={S.label}>Branch</label>
        <select style={S.select} value={draftEntityType.branch} onChange={(e) => setDraftEntityType({ ...draftEntityType, branch: e.target.value })}>
          <option value="physical">physical</option>
          <option value="information">information</option>
        </select>
        <label style={S.label}>Temporal type (legacy)</label>
        <select style={S.select} value={draftEntityType.temporal_type} onChange={(e) => setDraftEntityType({ ...draftEntityType, temporal_type: e.target.value })}>
          <option value="constant">constant</option>
          <option value="dynamic">dynamic</option>
          <option value="event-dynamic">event-dynamic</option>
        </select>
        <label style={S.label}>Spatial type (legacy, physical only)</label>
        <select style={S.select} value={draftEntityType.spatial_type || ''} onChange={(e) => setDraftEntityType({ ...draftEntityType, spatial_type: e.target.value || null })}>
          <option value="">(none)</option>
          <option value="uniform">uniform</option>
          <option value="distributed">distributed</option>
        </select>
        <label style={S.label}>Spatial size (legacy, physical only)</label>
        <select style={S.select} value={draftEntityType.spatial_size || ''} onChange={(e) => setDraftEntityType({ ...draftEntityType, spatial_size: e.target.value || null })}>
          <option value="">(none)</option>
          <option value="infinite">infinite</option>
          <option value="finite">finite</option>
          <option value="infinitesimal">infinitesimal</option>
        </select>
        <label style={S.label}>Scale values (canonical definition)</label>
        <div style={{ marginBottom: 8, maxHeight: 150, overflow: 'auto', border: '1px solid #ddd', padding: 4 }}>
          {scaleVals.map((sv) => (
            <label key={sv.iri} style={{ display: 'block', fontSize: 12 }}>
              <input
                type="checkbox"
                checked={draftEntityType.scale_values.includes(sv.iri)}
                onChange={(e) => {
                  const next = e.target.checked
                    ? [...draftEntityType.scale_values, sv.iri]
                    : draftEntityType.scale_values.filter((x) => x !== sv.iri)
                  setDraftEntityType({ ...draftEntityType, scale_values: next })
                }}
              /> {scaleValLabel(sv.iri)}
            </label>
          ))}
        </div>
        <label style={S.label}>Description</label>
        <textarea style={S.textarea} value={draftEntityType.description} onChange={(e) => setDraftEntityType({ ...draftEntityType, description: e.target.value })} />
        <button style={S.button} onClick={async () => {
          try { await createEntityType(draftEntityType); msg('Entity type saved'); await load() } catch (err) { msg(`Save failed: ${err}`) }
        }}>Save</button>
      </div>
    </>
  )

  // =========================================================================
  // Render: Indices
  // =========================================================================

  const renderIndices = () => (
    <>
      <div style={S.left}>
        <div style={S.leftHeader}>
          <span style={{ fontWeight: 'bold', fontSize: 13 }}>Indices</span>
          <button style={S.buttonGhost} onClick={() => { setSelIndex(null); setDraftIndex(EMPTY_INDEX) }}>+ New</button>
        </div>
        <div style={S.leftList}>
          {indices.map((i) => (
            <div
              key={i.iri}
              style={{ ...S.listItem, ...(selIndex === i.iri ? S.listItemSelected : {}) }}
              onClick={() => { setSelIndex(i.iri); setDraftIndex({ ...i }) }}
            >
              <strong>{i.label}</strong>
              <span style={S.muted}> ({i.network})</span>
              <button
                style={{ ...S.buttonGhost, float: 'right', padding: '2px 6px' }}
                onClick={(e) => { e.stopPropagation(); onDelete(i.iri, deleteIndex, 'Index') }}
              >x</button>
            </div>
          ))}
        </div>
      </div>
      <div style={S.right}>
        <h3 style={S.h3}>{selIndex ? 'Edit index' : 'New index'}</h3>
        <label style={S.label}>Label</label>
        <input style={S.input} value={draftIndex.label} onChange={(e) => setDraftIndex({ ...draftIndex, label: e.target.value })} />
        <label style={S.label}>Short name</label>
        <input style={S.input} value={draftIndex.short_name || ''} onChange={(e) => setDraftIndex({ ...draftIndex, short_name: e.target.value || null })} />
        <label style={S.label}>Network</label>
        <select style={S.select} value={draftIndex.network} onChange={(e) => setDraftIndex({ ...draftIndex, network: e.target.value })}>
          {domains.map((d) => (
            <option key={d.iri} value={d.name}>{d.name}</option>
          ))}
        </select>
        <label style={S.label}>Token binding (optional)</label>
        <select style={S.select} value={draftIndex.token || ''} onChange={(e) => setDraftIndex({ ...draftIndex, token: e.target.value || null })}>
          <option value="">(none)</option>
          {tokens.map((t) => (
            <option key={t.iri} value={t.iri}>{t.label}</option>
          ))}
        </select>
        <button style={S.button} onClick={async () => {
          try { await createIndex(draftIndex); msg('Index saved'); await load() } catch (err) { msg(`Save failed: ${err}`) }
        }}>Save</button>
      </div>
    </>
  )

  // =========================================================================
  // Render: Connection Rules
  // =========================================================================

  const renderRules = () => (
    <>
      <div style={S.left}>
        <div style={S.leftHeader}>
          <span style={{ fontWeight: 'bold', fontSize: 13 }}>Connection Rules</span>
          <button style={S.buttonGhost} onClick={() => { setSelRule(null); setDraftRule(EMPTY_RULE) }}>+ New</button>
        </div>
        <div style={S.leftList}>
          {rules.map((r) => (
            <div
              key={r.iri}
              style={{ ...S.listItem, ...(selRule === r.iri ? S.listItemSelected : {}) }}
              onClick={() => { setSelRule(r.iri); setDraftRule({ ...r }) }}
            >
              <strong>{r.rule_type}</strong>
              <span style={S.muted}> [{r.direction}]</span>
              <button
                style={{ ...S.buttonGhost, float: 'right', padding: '2px 6px' }}
                onClick={(e) => { e.stopPropagation(); onDelete(r.iri, deleteConnectionRule, 'Rule') }}
              >x</button>
              {r.description && <div style={S.muted}>{r.description}</div>}
            </div>
          ))}
        </div>
      </div>
      <div style={S.right}>
        <h3 style={S.h3}>{selRule ? 'Edit rule' : 'New rule'}</h3>
        <label style={S.label}>Rule type</label>
        <select style={S.select} value={draftRule.rule_type} onChange={(e) => setDraftRule({ ...draftRule, rule_type: e.target.value })}>
          <option value="physical-same">physical-same (same domain, shared tokens)</option>
          <option value="physical-cross">physical-cross (different domains, shared tokens)</option>
          <option value="signal">signal (information arc, unidirectional)</option>
        </select>
        <label style={S.label}>Direction</label>
        <select style={S.select} value={draftRule.direction || ''} onChange={(e) => setDraftRule({ ...draftRule, direction: e.target.value || null })}>
          <option value="bidirectional">bidirectional</option>
          <option value="unidirectional">unidirectional</option>
        </select>
        <label style={S.label}>Carrier</label>
        <select style={S.select} value={draftRule.carrier || ''} onChange={(e) => setDraftRule({ ...draftRule, carrier: e.target.value || null })}>
          <option value="token-flow">token-flow (continuity arc)</option>
          <option value="reference">reference (accessibility arc)</option>
        </select>
        <label style={S.label}>Scope</label>
        <select style={S.select} value={draftRule.scope || ''} onChange={(e) => setDraftRule({ ...draftRule, scope: e.target.value || null })}>
          <option value="same">same (shared ancestor domain)</option>
          <option value="cross">cross (no shared ancestor)</option>
          <option value="any">any</option>
        </select>
        <label style={S.label}>Source domain (for physical-cross)</label>
        <select style={S.select} value={draftRule.source_domain || ''} onChange={(e) => setDraftRule({ ...draftRule, source_domain: e.target.value || null })}>
          <option value="">(any)</option>
          {domains.map((d) => (
            <option key={d.iri} value={d.iri}>{d.name}</option>
          ))}
        </select>
        <label style={S.label}>Target domain (for physical-cross)</label>
        <select style={S.select} value={draftRule.target_domain || ''} onChange={(e) => setDraftRule({ ...draftRule, target_domain: e.target.value || null })}>
          <option value="">(any)</option>
          {domains.map((d) => (
            <option key={d.iri} value={d.iri}>{d.name}</option>
          ))}
        </select>
        <label style={S.label}>Shared tokens</label>
        <div style={{ marginBottom: 8, maxHeight: 100, overflow: 'auto', border: '1px solid #ddd', padding: 4 }}>
          {tokens.map((t) => (
            <label key={t.iri} style={{ display: 'block', fontSize: 12 }}>
              <input
                type="checkbox"
                checked={draftRule.shared_tokens.includes(t.iri)}
                onChange={(e) => {
                  const next = e.target.checked
                    ? [...draftRule.shared_tokens, t.iri]
                    : draftRule.shared_tokens.filter((x) => x !== t.iri)
                  setDraftRule({ ...draftRule, shared_tokens: next })
                }}
              /> {t.label}
            </label>
          ))}
        </div>
        <label style={S.label}>Description</label>
        <textarea style={S.textarea} value={draftRule.description} onChange={(e) => setDraftRule({ ...draftRule, description: e.target.value })} />
        <button style={S.button} onClick={async () => {
          try { await createConnectionRule(draftRule); msg('Rule saved'); await load() } catch (err) { msg(`Save failed: ${err}`) }
        }}>Save</button>
      </div>
    </>
  )

  // =========================================================================
  // Stage tabs
  // =========================================================================

  const stages: { key: Stage; label: string; enabled: boolean }[] = [
    { key: 'tokens', label: '1. Tokens', enabled: true },
    { key: 'domains', label: '2. Domains', enabled: true },
    { key: 'axes', label: '3. Axes', enabled: hasDomains },
    { key: 'scales', label: '4. Scales', enabled: hasDomains },
    { key: 'entity-types', label: '5. Entity Types', enabled: hasScales },
    { key: 'indices', label: '6. Indices', enabled: hasTokens },
    { key: 'rules', label: '7. Rules', enabled: hasDomains },
  ]

  return (
    <div style={S.app}>
      <div style={S.header}>
        <span style={{ fontWeight: 'bold', marginRight: 12, fontSize: 14 }}>ProMo14 Ontology Editor</span>
        {stages.map((s) => (
          <button
            key={s.key}
            style={{ ...S.tab, ...(stage === s.key ? S.tabActive : {}), ...(!s.enabled ? S.tabDisabled : {}) }}
            disabled={!s.enabled}
            onClick={() => s.enabled && setStage(s.key)}
          >
            {s.label}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button style={{ ...S.tab, background: '#0b7cbe' }} onClick={onSaveOntology}>
          Save ontology
        </button>
      </div>
      <div style={S.body}>
        {stage === 'tokens' && renderTokens()}
        {stage === 'domains' && renderDomains()}
        {stage === 'axes' && renderAxes()}
        {stage === 'scales' && renderScales()}
        {stage === 'entity-types' && renderEntityTypes()}
        {stage === 'indices' && renderIndices()}
        {stage === 'rules' && renderRules()}
      </div>
      {message && <div style={{ ...S.message, position: 'fixed', bottom: 0, left: 0, right: 0, textAlign: 'center' }}>{message}</div>}
    </div>
  )
}
