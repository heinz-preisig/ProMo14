import type { Variable } from '../types'

export interface VariablePaletteProps {
  variables: Variable[]
  expressionNetwork?: string
  onInsert?: (label: string) => void
  onDelete?: (v: Variable) => void
  onSelect?: (v: Variable) => void
}

export default function VariablePalette({
  variables,
  expressionNetwork = '',
  onInsert,
  onDelete,
  onSelect,
}: VariablePaletteProps) {
  const grouped = variables.reduce<Record<string, Variable[]>>((acc, v) => {
    const net = v.network ?? 'root'
    ;(acc[net] ??= []).push(v)
    return acc
  }, {})

  const activeNetwork = expressionNetwork || ''
  const interactive = !!onInsert

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <strong style={{ fontSize: 13 }}>Variables</strong>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          maxHeight: 220,
          overflowY: 'auto',
          padding: 4,
          border: '1px solid #ccc',
          borderRadius: 4,
          background: '#fff',
        }}
      >
        {Object.keys(grouped).length === 0 ? (
          <div style={{ fontSize: 11, color: '#888', padding: 8 }}>
            No variables yet. Use the <strong>New variable</strong> form above to
            define one.
          </div>
        ) : (
          Object.entries(grouped).map(([network, vars]) => (
            <div key={network}>
              <div style={{ fontSize: 11, color: '#444', fontWeight: 'bold', marginBottom: 2 }}>
                {network}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {vars.map((v) => {
                  const label =
                    activeNetwork && v.network !== activeNetwork
                      ? `${v.network}!${v.label}`
                      : v.label
                  const title = `${v.iri}${v.type ? ' — class: ' + v.type : ''}${v.doc ? ' — ' + v.doc : ''}`
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
                      onClick={() => onInsert?.(label)}
                      title={title}
                      style={style as React.CSSProperties}
                    >
                      {label}
                    </button>
                  ) : onDelete ? (
                    <div key={v.iri} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span
                        title={title}
                        style={selectStyle as React.CSSProperties}
                        onClick={() => onSelect?.(v)}
                      >
                        {label}
                      </span>
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
                    </div>
                  ) : (
                    <span
                      key={v.iri}
                      title={title}
                      style={selectStyle as React.CSSProperties}
                      onClick={() => onSelect?.(v)}
                    >
                      {label}
                    </span>
                  )
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
