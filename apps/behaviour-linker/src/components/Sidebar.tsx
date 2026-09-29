import type { Assignment, EntityType } from '../types'

interface SidebarProps {
  orderedTypes: { t: EntityType; depth: number }[]
  selected: string | null
  onSelect: (iri: string) => void
  filter: string
  onFilterChange: (value: string) => void
  assignmentByType: Map<string, Assignment>
}

export function Sidebar({
  orderedTypes,
  selected,
  onSelect,
  filter,
  onFilterChange,
  assignmentByType,
}: SidebarProps) {
  const visible = filter
    ? orderedTypes
        .filter(({ t }) => t.label.toLowerCase().includes(filter.toLowerCase()))
        .map(({ t }) => ({ t, depth: 0 }))
    : orderedTypes

  return (
    <aside
      style={{
        width: 240,
        borderRight: '1px solid #ddd',
        background: '#fafafa',
        overflowY: 'auto',
        padding: 8,
      }}
    >
      <div style={{ fontSize: 12, color: '#888', margin: '4px 4px 8px' }}>
        ENTITY TYPES
      </div>
      <input
        placeholder="filter…"
        value={filter}
        onChange={(e) => onFilterChange(e.target.value)}
        style={{
          width: '100%',
          boxSizing: 'border-box',
          fontSize: 13,
          padding: '3px 6px',
          marginBottom: 6,
          border: '1px solid #ccc',
          borderRadius: 4,
        }}
      />
      {visible.map(({ t, depth }) => {
        const a = assignmentByType.get(t.iri)
        const active = t.iri === selected
        return (
          <div
            key={t.iri}
            onClick={() => onSelect(t.iri)}
            style={{
              padding: '6px 8px',
              paddingLeft: 8 + depth * 14,
              marginBottom: 2,
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: 13,
              background: active ? '#e3ecff' : 'transparent',
              display: 'flex',
              justifyContent: 'space-between',
              gap: 8,
            }}
          >
            <span>{t.label}</span>
            {a && (
              <span
                style={{
                  fontSize: 12,
                  color: a.closed ? '#0a7' : '#c80',
                }}
              >
                {a.closed ? 'closed' : 'wip'}
              </span>
            )}
          </div>
        )
      })}
    </aside>
  )
}
