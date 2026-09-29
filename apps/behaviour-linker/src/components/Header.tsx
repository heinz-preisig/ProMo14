import { btn } from '../styles'
import type { EvaluateReport } from '../types'

interface HeaderProps {
  title: string
  report: EvaluateReport | null
  entityType: string | null
  dirty: boolean
  hasUnsavedChanges: boolean
  saveMsg: string
  onSave: () => void
  onDelete: () => void
}

export function Header({
  title,
  report,
  entityType,
  dirty,
  hasUnsavedChanges,
  saveMsg,
  onSave,
  onDelete,
}: HeaderProps) {
  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        flexWrap: 'wrap',
        minHeight: 44,
        padding: '0 16px',
        background: '#fff',
        borderBottom: '1px solid #ddd',
      }}
    >
      <strong
        style={{
          fontSize: 14,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {title}
      </strong>
      <div
        style={{
          marginLeft: 'auto',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        {report && entityType && (
          <span
            style={{
              fontSize: 13,
              color: report.closed ? '#0a7' : '#c80',
              fontWeight: 600,
            }}
          >
            {report.closed ? 'closed' : 'open'}
          </span>
        )}
        {dirty && (
          <span style={{ fontSize: 13, color: '#c80' }}>● unsaved</span>
        )}
        {hasUnsavedChanges && (
          <span style={{ fontSize: 13, color: '#c00' }}>● modified</span>
        )}
        {saveMsg && <span style={{ fontSize: 13 }}>{saveMsg}</span>}
        <button style={btn} onClick={onSave} disabled={!entityType}>
          Save
        </button>
        <button style={btn} onClick={onDelete} disabled={!entityType}>
          Delete
        </button>
      </div>
    </header>
  )
}
