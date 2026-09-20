import { Fragment, useMemo, useState } from 'react'
import { indexShortLabel } from '../latex'
import type { Index, Variable } from '../types'

/** SI symbols matching UNIT_LABELS in the editors:
 *  time, length, amount, mass, temperature, current, light, nil. */
const UNIT_SYMBOLS = ['s', 'm', 'mol', 'kg', 'K', 'A', 'cd', 'nil']

function formatUnits(units?: number[]): string {
  if (!units || units.every((e) => !e)) return '—'
  return units
    .map((e, i) => (e ? `${UNIT_SYMBOLS[i]}${e !== 1 ? `^${e}` : ''}` : ''))
    .filter(Boolean)
    .join('·')
}

type SortKey = 'label' | 'type' | 'network' | 'eqs'

export interface VariableTableProps {
  variables: Variable[]
  indices: Index[]
  onSelect?: (v: Variable) => void
}

/** Repository browser: sortable/filterable table of all variables with
 *  per-variable expandable equation rows. */
export default function VariableTable({ variables, indices, onSelect }: VariableTableProps) {
  const [filter, setFilter] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('label')
  const [sortAsc, setSortAsc] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const eqCount = (v: Variable) => Object.keys(v.equations ?? {}).length

  const rows = useMemo(() => {
    const q = filter.trim().toLowerCase()
    const filtered = q
      ? variables.filter(
          (v) =>
            v.label.toLowerCase().includes(q) ||
            (v.doc ?? '').toLowerCase().includes(q) ||
            (v.type ?? '').toLowerCase().includes(q) ||
            (v.network ?? '').toLowerCase().includes(q),
        )
      : [...variables]
    const key = (v: Variable): string | number =>
      sortKey === 'eqs' ? eqCount(v) : ((v[sortKey] as string | undefined) ?? '')
    filtered.sort((a, b) => {
      const ka = key(a)
      const kb = key(b)
      const c =
        typeof ka === 'number' && typeof kb === 'number'
          ? ka - kb
          : String(ka).localeCompare(String(kb))
      return sortAsc ? c : -c
    })
    return filtered
  }, [variables, filter, sortKey, sortAsc])

  const header = (label: string, key: SortKey) => (
    <th
      onClick={() => {
        if (sortKey === key) setSortAsc(!sortAsc)
        else {
          setSortKey(key)
          setSortAsc(true)
        }
      }}
      style={{
        textAlign: 'left',
        padding: '4px 8px',
        cursor: 'pointer',
        userSelect: 'none',
        whiteSpace: 'nowrap',
        borderBottom: '1px solid #ccc',
        background: '#f0f0f0',
        position: 'sticky',
        top: 0,
      }}
    >
      {label}
      {sortKey === key ? (sortAsc ? ' ▲' : ' ▼') : ''}
    </th>
  )

  const toggleExpand = (iri: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(iri)) next.delete(iri)
      else next.add(iri)
      return next
    })
  }

  const indexLabel = (iri: string) => {
    const idx = indices.find((i) => i.iri === iri)
    return idx ? indexShortLabel(idx) || idx.label : iri
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0, flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <strong style={{ fontSize: 13 }}>Repository</strong>
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name, doc, class, network…"
          style={{
            fontSize: 12,
            padding: '4px 6px',
            border: '1px solid #bbb',
            borderRadius: 4,
            width: 260,
          }}
        />
        <span style={{ fontSize: 11, color: '#888' }}>
          {rows.length} of {variables.length} variables
        </span>
      </div>
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          border: '1px solid #ccc',
          borderRadius: 4,
          background: '#fff',
          minHeight: 0,
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              <th style={{ width: 24, borderBottom: '1px solid #ccc', background: '#f0f0f0', position: 'sticky', top: 0 }} />
              {header('Name', 'label')}
              {header('Class', 'type')}
              {header('Network', 'network')}
              <th style={{ textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #ccc', background: '#f0f0f0', position: 'sticky', top: 0 }}>
                Indices
              </th>
              <th style={{ textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #ccc', background: '#f0f0f0', position: 'sticky', top: 0 }}>
                Units
              </th>
              {header('Eqs', 'eqs')}
              <th style={{ textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #ccc', background: '#f0f0f0', position: 'sticky', top: 0 }}>
                Doc
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: 12, color: '#888' }}>
                  {variables.length === 0
                    ? 'No variables yet — use the sidebar buttons to define one.'
                    : 'No variables match the filter.'}
                </td>
              </tr>
            ) : (
              rows.map((v) => {
                const eqs = Object.entries(v.equations ?? {})
                const open = expanded.has(v.iri)
                return (
                  <Fragment key={v.iri}>
                    <tr
                      onClick={() => onSelect?.(v)}
                      style={{ cursor: onSelect ? 'pointer' : 'default' }}
                      title={v.iri}
                    >
                      <td style={{ padding: '4px 4px 4px 8px', borderBottom: '1px solid #eee' }}>
                        {eqs.length > 0 && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              toggleExpand(v.iri)
                            }}
                            title={open ? 'Hide equations' : 'Show equations'}
                            style={{
                              fontSize: 10,
                              background: 'none',
                              border: 'none',
                              cursor: 'pointer',
                              padding: 0,
                              color: '#555',
                            }}
                          >
                            {open ? '▼' : '▶'}
                          </button>
                        )}
                      </td>
                      <td style={{ padding: '4px 8px', borderBottom: '1px solid #eee', fontWeight: 500 }}>
                        {v.label}
                        {v.value != null && v.value !== '' && (
                          <span style={{ color: '#888', fontWeight: 400 }}> = {v.value}</span>
                        )}
                      </td>
                      <td style={{ padding: '4px 8px', borderBottom: '1px solid #eee', color: '#555' }}>
                        {v.type ?? '—'}
                      </td>
                      <td style={{ padding: '4px 8px', borderBottom: '1px solid #eee', color: '#555' }}>
                        {v.network}
                      </td>
                      <td style={{ padding: '4px 8px', borderBottom: '1px solid #eee' }}>
                        {v.index_structures?.length
                          ? v.index_structures.map(indexLabel).join(', ')
                          : 'scalar'}
                      </td>
                      <td style={{ padding: '4px 8px', borderBottom: '1px solid #eee' }}>
                        {formatUnits(v.units)}
                      </td>
                      <td style={{ padding: '4px 8px', borderBottom: '1px solid #eee', textAlign: 'center' }}>
                        {eqs.length || ''}
                      </td>
                      <td
                        style={{
                          padding: '4px 8px',
                          borderBottom: '1px solid #eee',
                          color: '#777',
                          maxWidth: 220,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {v.doc ?? ''}
                      </td>
                    </tr>
                    {open &&
                      eqs.map(([eqId, eq]) => (
                        <tr key={eqId} style={{ background: '#fafafa' }}>
                          <td style={{ borderBottom: '1px solid #f0f0f0' }} />
                          <td
                            colSpan={7}
                            style={{ padding: '3px 8px', borderBottom: '1px solid #f0f0f0' }}
                          >
                            <code style={{ fontSize: 11 }}>
                              {eq.internal_id ?? eqId}: {v.label} := {eq.rhs}
                            </code>
                            {eq.equation_class && (
                              <span style={{ fontSize: 10, color: '#888', marginLeft: 8 }}>
                                [{eq.equation_class}]
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                  </Fragment>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
