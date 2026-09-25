import { type ChangeEvent, type KeyboardEvent, useRef, useState } from 'react'
import { OPERATOR_HELP } from '../operatorHelp'
import OperatorHelp from './OperatorHelp'
import SyntaxDiagram from './SyntaxDiagram'

export interface ExpressionInputProps {
  value: string
  onChange: (value: string) => void
  onCheck: () => void
  disabled?: boolean
}

const OP_BUTTONS: { label: string; value: string; tip?: string }[] = [
  { label: '+', value: ' + ' },
  { label: '-', value: ' - ' },
  { label: '*', value: ' * ' },
  { label: ':', value: ' : ' },
  { label: '.', value: ' . ' },
  { label: '^', value: ' ^ ' },
  { label: '(', value: ' (', tip: 'open group' },
  { label: ')', value: ') ', tip: 'close group' },
]

/** Tooltip text for an operator button — syntax + meaning from the
 *  shared reference table. */
const tipFor = (label: string) => {
  const h = OPERATOR_HELP.find(
    (e) =>
      e.label === label ||
      e.label.split(/\s*\/\s*|\s+/).includes(label),
  )
  return h ? `${h.syntax} — ${h.description}` : undefined
}

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
  'sign',
]

export default function ExpressionInput({
  value,
  onChange,
  onCheck,
  disabled,
}: ExpressionInputProps) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const [helpOpen, setHelpOpen] = useState(false)
  const [syntaxOpen, setSyntaxOpen] = useState(false)

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
            title={b.tip ?? tipFor(b.label)}
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
            title={tipFor(f)}
            style={{ padding: '4px 8px', fontSize: 12 }}
          >
            {f}(
          </button>
        ))}
        <button
          type="button"
          onClick={() => setHelpOpen((o) => !o)}
          title="Operator reference"
          style={{
            marginLeft: 'auto',
            padding: '4px 10px',
            fontSize: 12,
            fontWeight: 'bold',
            background: '#1565c0',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
          }}
        >
          ?
        </button>
        <button
          type="button"
          onClick={() => setSyntaxOpen(true)}
          title="Railway diagram of the expression grammar"
          style={{
            padding: '4px 10px',
            fontSize: 12,
            fontWeight: 'bold',
            background: '#1565c0',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
          }}
        >
          syntax
        </button>
      </div>
      {helpOpen && <OperatorHelp />}
      {syntaxOpen && <SyntaxDiagram onClose={() => setSyntaxOpen(false)} />}
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
