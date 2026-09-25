import { useMemo, useState } from 'react'
import type { NetworkTree, Variable } from '../types'

/** Map of network → steps above ``from`` in the domain tree
 *  (0 = ``from`` itself).  Networks not on the ancestor chain are
 *  absent — they sort last.  Mirrors the distance measure in the
 *  checker's ``CompileSpace._nearest_accessible``. */
function ancestorDistances(tree: NetworkTree, from: string): Map<string, number> {
  const parentOf = new Map<string, string>()
  for (const [parent, kids] of Object.entries(tree)) {
    for (const k of kids) if (!parentOf.has(k)) parentOf.set(k, parent)
  }
  const out = new Map<string, number>()
  let cur = from
  let d = 0
  while (cur && !out.has(cur)) {
    out.set(cur, d)
    const parent = parentOf.get(cur)
    if (parent === undefined) break
    cur = parent
    d++
  }
  return out
}

export interface VariablePaletteProps {
  variables: Variable[]
  expressionNetwork?: string
  networkTree?: NetworkTree
  onInsert?: (label: string) => void
  onDelete?: (v: Variable) => void
  onSelect?: (v: Variable) => void
}

export default function VariablePalette({
  variables,
  expressionNetwork = '',
  networkTree = {},
  onInsert,
  onDelete,
  onSelect,
}: VariablePaletteProps) {
  const [filter, setFilter] = useState('')
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const filtering = filter.trim().length > 0

  const grouped = useMemo(() => {
    const q = filter.trim().toLowerCase()
    const acc: Record<string, Variable[]> = {}
    for (const v of variables) {
      if (
        q &&
        !v.label.toLowerCase().includes(q) &&
        !(v.doc ?? '').toLowerCase().includes(q) &&
        !(v.type ?? '').toLowerCase().includes(q) &&
        !(v.network ?? '').toLowerCase().includes(q) &&
        !v.iri.toLowerCase().includes(q)
      ) {
        continue
      }
      const net = v.network ?? 'root'
      ;(acc[net] ??= []).push(v)
    }
    for (const vars of Object.values(acc)) {
      vars.sort((a, b) => a.label.localeCompare(b.label))
    }
    return acc
  }, [variables, filter])

  const shown = Object.values(grouped).reduce((n, vars) => n + vars.length, 0)
  const activeNetwork = expressionNetwork || ''
  const interactive = !!onInsert
  // Groups ordered by relevance: expression domain first, then its
  // ancestors (nearest first), then everything else alphabetically —
  // the variables likeliest to be referenced land on top.
  const distances = useMemo(
    () => ancestorDistances(networkTree, activeNetwork),
    [networkTree, activeNetwork],
  )

  const toggleGroup = (net: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(net)) next.delete(net)
      else next.add(net)
      return next
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <strong style={{ fontSize: 13 }}>
        Variables ({filtering ? `${shown}/${variables.length}` : variables.length})
      </strong>
      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter variables…"
        style={{
          fontSize: 12,
          padding: '4px 6px',
          border: '1px solid #bbb',
          borderRadius: 4,
        }}
      />
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          maxHeight: 300,
          overflowY: 'auto',
          padding: 4,
          border: '1px solid #ccc',
          borderRadius: 4,
          background: '#fff',
        }}
      >
        {Object.keys(grouped).length === 0 ? (
          <div style={{ fontSize: 11, color: '#888', padding: 8 }}>
            {filtering ? (
              'No variables match the filter.'
            ) : (
              <>
                No variables yet. Use the <strong>New variable</strong> form above
                to define one.
              </>
            )}
          </div>
        ) : (
          Object.entries(grouped)
            .sort(([a], [b]) => {
              const da = distances.get(a) ?? Infinity
              const db = distances.get(b) ?? Infinity
              return da !== db ? da - db : a.localeCompare(b)
            })
            .map(([network, vars]) => {
              const isCollapsed = collapsed.has(network) && !filtering
              return (
            <div key={network}>
              <div
                onClick={() => toggleGroup(network)}
                title={isCollapsed ? 'Expand group' : 'Collapse group'}
                style={{
                  fontSize: 11,
                  color: '#444',
                  fontWeight: 'bold',
                  marginBottom: 2,
                  cursor: 'pointer',
                  userSelect: 'none',
                }}
              >
                {isCollapsed ? '▶' : '▼'} {network} ({vars.length})
                {network === activeNetwork && (
                  <span style={{ color: '#1565c0' }} title="expression domain"> ●</span>
                )}
              </div>
              {!isCollapsed && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {vars.map((v) => {
                  // Chips sit under their network group header — show
                  // the bare label.  Insert pins the source: the
                  // palette knows each chip's network, so foreign
                  // variables are qualified — the stored text cannot
                  // rebind if a nearer same-label variable appears
                  // later.  Local names stay bare: labels are unique
                  // within a domain and the local match always wins.
                  const label = v.label
                  const insert =
                    activeNetwork && v.network === activeNetwork
                      ? v.label
                      : `${v.network ?? 'root'}!${v.label}`
                  // Pre-bound value (universal constants, ADR-008): show
                  // the value badge and never offer delete — they are
                  // permanent fixtures of the ontology.
                  const bound = v.value != null && v.value !== ''
                  const display = bound ? `${label}=${v.value}` : label
                  const title = `${v.iri}${v.type ? ' — class: ' + v.type : ''}${bound ? ' — value: ' + v.value : ''}${v.doc ? ' — ' + v.doc : ''}${insert !== label ? ' — inserts as ' + insert : ''}`
                  const style = {
                    fontSize: 12,
                    padding: '3px 6px',
                    cursor: interactive ? 'pointer' : 'default',
                    background: activeNetwork && v.network === activeNetwork ? '#e8f4fd' : '#fff',
                    border: '1px solid #bbb',
                    borderRadius: 4,
                  }
                  const selectStyle = {
                    ...style,
                    cursor: onSelect || interactive ? 'pointer' : 'default',
                  }
                  return interactive ? (
                    <button
                      key={v.iri}
                      type="button"
                      onClick={() => onInsert?.(insert)}
                      title={title}
                      style={style as React.CSSProperties}
                    >
                      {display}
                    </button>
                  ) : onDelete ? (
                    <div key={v.iri} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span
                        title={title}
                        style={selectStyle as React.CSSProperties}
                        onClick={() => onSelect?.(v)}
                      >
                        {display}
                      </span>
                      {!bound && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            onDelete(v)
                          }}
                          title={`Delete ${label}`}
                          style={{
                            fontSize: 11,
                            color: '#c62828',
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '0 2px',
                          }}
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ) : (
                    <span
                      key={v.iri}
                      title={title}
                      style={selectStyle as React.CSSProperties}
                      onClick={() => onSelect?.(v)}
                    >
                      {display}
                    </span>
                  )
                })}
              </div>
              )}
            </div>
            )
          })
        )}
      </div>
    </div>
  )
}
