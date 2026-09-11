import { type ChangeEvent, type KeyboardEvent, useRef } from 'react'

export interface ExpressionInputProps {
  value: string
  onChange: (value: string) => void
  onCheck: () => void
  disabled?: boolean
}

const OP_BUTTONS = [
  { label: '+', value: ' + ' },
  { label: '-', value: ' - ' },
  { label: '*', value: ' * ' },
  { label: ':', value: ' : ' },
  { label: '.', value: ' . ' },
  { label: '^', value: ' ^ ' },
  { label: '(', value: ' (' },
  { label: ')', value: ') ' },
]

const FUNC_BUTTONS = [
  'Integral',
  'Product',
  'Root',
  'TotalDiff',
  'ParDiff',
  'reduceSum',
  'Instantiate',
  'sin',
  'cos',
  'exp',
  'log',
  'sqrt',
  'abs',
  'neg',
  'inv',
]

export default function ExpressionInput({
  value,
  onChange,
  onCheck,
  disabled,
}: ExpressionInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null)

  const insert = (token: string) => {
    const el = ref.current
    if (!el) return
    const start = el.selectionStart ?? 0
    const end = el.selectionEnd ?? 0
    const before = value.slice(0, start)
    const after = value.slice(end)
    const next = before + token + after
    onChange(next)
    setTimeout(() => {
      el.focus()
      const pos = start + token.length
      el.setSelectionRange(pos, pos)
    }, 0)
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'enter') {
      e.preventDefault()
      onCheck()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {OP_BUTTONS.map((b) => (
          <button
            key={b.label}
            type="button"
            onClick={() => insert(b.value)}
            disabled={disabled}
            style={{ minWidth: 32, padding: '4px 8px', fontSize: 14 }}
          >
            {b.label}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {FUNC_BUTTONS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => insert(`${f}(`)}
            disabled={disabled}
            style={{ padding: '4px 8px', fontSize: 12 }}
          >
            {f}(
          </button>
        ))}
      </div>
      <textarea
        ref={ref}
        value={value}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder="Type an expression, e.g. U - p . V"
        spellCheck={false}
        style={{
          width: '100%',
          minHeight: 80,
          fontFamily: 'monospace',
          fontSize: 16,
          padding: 8,
          border: '1px solid #ccc',
          borderRadius: 4,
          resize: 'vertical',
        }}
      />
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button type="button" onClick={onCheck} disabled={disabled} style={{ fontWeight: 'bold' }}>
          Check (Ctrl/Cmd+Enter)
        </button>
        <span style={{ fontSize: 12, color: '#666' }}>No numeric literals. Use network!label to qualify.</span>
      </div>
    </div>
  )
}
