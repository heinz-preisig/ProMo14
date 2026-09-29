import { btn, card } from '../../styles'

interface PrintablePanelProps {
  previewHtml: string
  source: string
  copied: boolean
  showSource: boolean
  onToggleSource: () => void
  onCopy: () => void
  onPrint: () => void
}

export function PrintablePanel({
  previewHtml,
  source,
  copied,
  showSource,
  onToggleSource,
  onCopy,
  onPrint,
}: PrintablePanelProps) {
  if (!source) return null
  return (
    <div style={card}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        Printable representation
      </div>
      {previewHtml && (
        <div
          style={{ marginBottom: 8, overflowX: 'auto' }}
          dangerouslySetInnerHTML={{ __html: previewHtml }}
        />
      )}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button style={btn} onClick={onCopy}>
          Copy LaTeX
        </button>
        <button style={btn} onClick={onPrint}>
          Print
        </button>
        <button style={btn} onClick={onToggleSource}>
          {showSource ? 'Hide source' : 'Show source'}
        </button>
        {copied && (
          <span style={{ fontSize: 12, color: '#0a7' }}>copied</span>
        )}
      </div>
      {showSource && (
        <pre
          style={{
            fontSize: 12,
            background: '#f5f5f5',
            padding: 8,
            borderRadius: 4,
            overflowX: 'auto',
            marginTop: 8,
          }}
        >
          {source}
        </pre>
      )}
    </div>
  )
}
