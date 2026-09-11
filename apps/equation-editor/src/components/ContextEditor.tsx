import { useEffect, useState } from 'react'
import type { Index, NetworkTree, Variable } from '../types'

export interface ContextEditorProps {
  variables: Variable[]
  indices: Index[]
  networkTree: NetworkTree
  expressionNetwork: string
  onChange: (ctx: {
    variables: Variable[]
    indices: Index[]
    networkTree: NetworkTree
    expressionNetwork: string
  }) => void
}

export default function ContextEditor({
  variables,
  indices,
  networkTree,
  expressionNetwork,
  onChange,
}: ContextEditorProps) {
  const [text, setText] = useState(() => stringify({ variables, indices, networkTree, expressionNetwork }))
  const [error, setError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)

  const ctxString = stringify({ variables, indices, networkTree, expressionNetwork })
  useEffect(() => {
    if (!dirty) {
      setText(ctxString)
    }
  }, [ctxString, dirty])

  const apply = () => {
    try {
      const parsed = JSON.parse(text) as {
        variables: Variable[]
        indices: Index[]
        networkTree: NetworkTree
        expressionNetwork: string
      }
      onChange(parsed)
      setError(null)
      setDirty(false)
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <strong style={{ fontSize: 13 }}>Equation context (JSON)</strong>
        <button type="button" onClick={apply}>
          Apply
        </button>
      </div>
      {error && <div style={{ color: '#c62828', fontSize: 12 }}>{error}</div>}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
        style={{
          width: '100%',
          minHeight: 160,
          fontFamily: 'monospace',
          fontSize: 12,
          padding: 8,
          border: '1px solid #ccc',
          borderRadius: 4,
          resize: 'vertical',
          whiteSpace: 'pre',
          overflowWrap: 'normal',
          overflowX: 'auto',
        }}
      />
    </div>
  )
}

function stringify(ctx: {
  variables: Variable[]
  indices: Index[]
  networkTree: NetworkTree
  expressionNetwork: string
}): string {
  return JSON.stringify(ctx, null, 2)
}
