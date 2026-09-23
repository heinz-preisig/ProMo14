import { useCallback, useEffect, useState } from 'react'
import {
  fetchSpecies,
  graphParam,
  saveSpecies,
  saveStore,
} from './api'
import { useStoreDirty } from './useStoreDirty'
import type {
  AllocationDoc,
  ComponentDoc,
  ReactionDoc,
  SpeciesDocument,
} from './types'

const frag = (iri: string) =>
  iri.split('#').pop()?.split('/').pop() ?? iri

/** Mint a fresh member IRI under the artefact graph. */
const mint = (graph: string | undefined, kind: string) =>
  `${(graph ?? 'species').replace(/[#/]$/, '')}/${kind}_${Date.now().toString(36)}`

const S: Record<string, React.CSSProperties> = {
  app: { display: 'flex', flexDirection: 'column', height: '100%' },
  header: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
    background: '#1f2937', color: '#f9fafb', flexWrap: 'wrap',
  },
  title: { fontSize: 16, fontWeight: 600 },
  iri: { fontSize: 11, opacity: 0.7, fontFamily: 'monospace' },
  dirty: { color: '#fbbf24', fontSize: 12, fontWeight: 600 },
  body: { display: 'flex', gap: 12, padding: 12, flex: 1, minHeight: 0 },
  col: {
    flex: 1, minWidth: 0, background: '#fff', borderRadius: 8,
    border: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column',
    overflow: 'hidden',
  },
  colHead: {
    padding: '10px 12px', borderBottom: '1px solid #e5e7eb',
    fontWeight: 600, fontSize: 13, background: '#f9fafb',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  list: { overflowY: 'auto', padding: 8, flex: 1 },
  card: {
    border: '1px solid #e5e7eb', borderRadius: 6, padding: 8,
    marginBottom: 8, fontSize: 12,
  },
  row: { display: 'flex', alignItems: 'center', gap: 6 },
  input: {
    flex: 1, minWidth: 0, padding: '3px 6px', fontSize: 12,
    border: '1px solid #d1d5db', borderRadius: 4,
  },
  btn: {
    padding: '3px 8px', fontSize: 11, border: '1px solid #d1d5db',
    borderRadius: 4, background: '#fff', cursor: 'pointer',
  },
  primary: {
    padding: '5px 14px', fontSize: 12, border: 'none', borderRadius: 5,
    background: '#2563eb', color: '#fff', cursor: 'pointer', fontWeight: 600,
  },
  check: { display: 'inline-flex', alignItems: 'center', gap: 4,
           marginRight: 10, fontSize: 11, cursor: 'pointer' },
  muted: { fontSize: 11, color: '#9ca3af' },
  err: { padding: 12, color: '#b91c1c', fontSize: 12 },
  coeff: { width: 34, fontSize: 10, padding: '0 2px', marginLeft: 2,
           border: '1px solid #d1d5db', borderRadius: 3 },
}

function CheckList({
  options, selected, onToggle, coeffs, onCoeff,
}: {
  options: ComponentDoc[]
  selected: string[]
  onToggle: (iri: string) => void
  /** §20 stoichiometry slots — shown on checked members when given. */
  coeffs?: Record<string, number>
  onCoeff?: (iri: string, v: number | null) => void
}) {
  return (
    <div>
      {options.map((c) => {
        const on = selected.includes(c.iri)
        return (
          <label key={c.iri} style={S.check}>
            <input
              type="checkbox"
              checked={on}
              onChange={() => onToggle(c.iri)}
            />
            {c.label || frag(c.iri)}
            {on && onCoeff && (
              <input
                type="number" min="0" step="any" style={S.coeff}
                title="stoichiometric coefficient (default 1)"
                placeholder="1"
                value={coeffs?.[c.iri] ?? ''}
                onChange={(e) =>
                  onCoeff(c.iri,
                    e.target.value === '' ? null : Number(e.target.value))
                }
              />
            )}
          </label>
        )
      })}
    </div>
  )
}

export default function App() {
  const graph = graphParam()
  const dirty = useStoreDirty()
  const [doc, setDoc] = useState<SpeciesDocument>({
    components: [], allocations: [], reactions: [],
  })
  const [err, setErr] = useState('')
  const [newLabel, setNewLabel] = useState('')

  useEffect(() => {
    fetchSpecies(graph)
      .then(setDoc)
      .catch((e) => setErr(String(e)))
  }, [graph])

  const save = useCallback(async () => {
    try {
      await saveSpecies(doc, graph)
      await saveStore()
    } catch (e) {
      setErr(String(e))
    }
  }, [doc, graph])

  const toggle = (
    list: 'members' | 'reactants' | 'products',
    coll: 'allocations' | 'reactions',
    iri: string,
    comp: string,
  ) =>
    setDoc((d) => ({
      ...d,
      [coll]: d[coll].map((x: any) => {
        if (x.iri !== iri) return x
        const removing = x[list].includes(comp)
        const next = {
          ...x,
          [list]: removing
            ? x[list].filter((m: string) => m !== comp)
            : [...x[list], comp],
        }
        // stoichiometry keys are members only — prune on uncheck.
        if (removing && coll === 'reactions' && next.stoichiometry) {
          next.stoichiometry = { ...next.stoichiometry }
          delete next.stoichiometry[comp]
        }
        return next
      }),
    }))

  const setCoeff = (iri: string, comp: string, v: number | null) =>
    setDoc((d) => ({
      ...d,
      reactions: d.reactions.map((x) => {
        if (x.iri !== iri) return x
        const stoichiometry = { ...(x.stoichiometry ?? {}) }
        if (v === null || v === 1) delete stoichiometry[comp]
        else stoichiometry[comp] = v
        return { ...x, stoichiometry }
      }),
    }))

  const addComponent = () => {
    const label = newLabel.trim()
    if (!label) return
    setDoc((d) => ({
      ...d,
      components: [
        ...d.components,
        { iri: mint(graph, 'Component'), label },
      ],
    }))
    setNewLabel('')
  }

  const addAllocation = () =>
    setDoc((d) => ({
      ...d,
      allocations: [
        ...d.allocations,
        { iri: mint(graph, 'Allocation'), label: 'allocation', members: [] },
      ],
    }))

  const addReaction = () =>
    setDoc((d) => ({
      ...d,
      reactions: [
        ...d.reactions,
        {
          iri: mint(graph, 'Reaction'),
          label: 'reaction',
          reactants: [],
          products: [],
        },
      ],
    }))

  const remove = (coll: keyof SpeciesDocument, iri: string) =>
    setDoc((d) => ({
      ...d,
      [coll]: (d[coll] as { iri: string }[]).filter((x) => x.iri !== iri),
    }))

  const relabel = (coll: keyof SpeciesDocument, iri: string, label: string) =>
    setDoc((d) => ({
      ...d,
      [coll]: (d[coll] as { iri: string; label: string }[]).map((x) =>
        x.iri === iri ? { ...x, label } : x,
      ),
    }))

  return (
    <div style={S.app}>
      <div style={S.header}>
        <span style={S.title}>Species &amp; Reactions</span>
        <span style={S.iri}>{graph ?? '(no graph)'}</span>
        {dirty && <span style={S.dirty}>● unsaved</span>}
        <span style={{ marginLeft: 'auto' }}>
          <button style={S.primary} onClick={save}>Save</button>
        </span>
      </div>
      {err && <div style={S.err}>{err}</div>}
      <div style={S.body}>
        {/* Components */}
        <div style={S.col}>
          <div style={S.colHead}>
            Components
            <span style={S.muted}>{doc.components.length}</span>
          </div>
          <div style={S.list}>
            {doc.components.map((c) => (
              <div key={c.iri} style={{ ...S.card, ...S.row }}>
                <input
                  style={S.input}
                  value={c.label}
                  onChange={(e) =>
                    relabel('components', c.iri, e.target.value)
                  }
                />
                <button style={S.btn}
                        onClick={() => remove('components', c.iri)}>
                  ×
                </button>
              </div>
            ))}
            <div style={S.row}>
              <input
                style={S.input}
                placeholder="new species label"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addComponent()}
              />
              <button style={S.btn} onClick={addComponent}>+ add</button>
            </div>
          </div>
        </div>

        {/* Allocations */}
        <div style={S.col}>
          <div style={S.colHead}>
            Allocations
            <button style={S.btn} onClick={addAllocation}>+ add</button>
          </div>
          <div style={S.list}>
            {doc.allocations.map((a: AllocationDoc) => (
              <div key={a.iri} style={S.card}>
                <div style={S.row}>
                  <input
                    style={S.input}
                    value={a.label}
                    onChange={(e) =>
                      relabel('allocations', a.iri, e.target.value)
                    }
                  />
                  <button style={S.btn}
                          onClick={() => remove('allocations', a.iri)}>
                    ×
                  </button>
                </div>
                <CheckList
                  options={doc.components}
                  selected={a.members}
                  onToggle={(c) => toggle('members', 'allocations', a.iri, c)}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Reactions */}
        <div style={S.col}>
          <div style={S.colHead}>
            Reactions
            <button style={S.btn} onClick={addReaction}>+ add</button>
          </div>
          <div style={S.list}>
            {doc.reactions.map((r: ReactionDoc) => (
              <div key={r.iri} style={S.card}>
                <div style={S.row}>
                  <input
                    style={S.input}
                    value={r.label}
                    onChange={(e) =>
                      relabel('reactions', r.iri, e.target.value)
                    }
                  />
                  <button style={S.btn}
                          onClick={() => remove('reactions', r.iri)}>
                    ×
                  </button>
                </div>
                <div style={S.muted}>reactants</div>
                <CheckList
                  options={doc.components}
                  selected={r.reactants}
                  onToggle={(c) => toggle('reactants', 'reactions', r.iri, c)}
                  coeffs={r.stoichiometry}
                  onCoeff={(c, v) => setCoeff(r.iri, c, v)}
                />
                <div style={S.muted}>products</div>
                <CheckList
                  options={doc.components}
                  selected={r.products}
                  onToggle={(c) => toggle('products', 'reactions', r.iri, c)}
                  coeffs={r.stoichiometry}
                  onCoeff={(c, v) => setCoeff(r.iri, c, v)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
