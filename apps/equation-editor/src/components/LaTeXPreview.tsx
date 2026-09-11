import 'katex/dist/katex.min.css'
import { astToLatex, renderLatex } from '../latex'
import type { AstNode, Index, Variable } from '../types'

export interface LaTeXPreviewProps {
  ast: AstNode | null
  variables?: Variable[]
  indices?: Index[]
  expressionNetwork?: string
}

export default function LaTeXPreview({
  ast,
  variables = [],
  indices = [],
  expressionNetwork = '',
}: LaTeXPreviewProps) {
  if (!ast) {
    return <div style={{ color: '#888', fontSize: 13 }}>Parse an expression to see a preview.</div>
  }

  const latex = astToLatex(ast, { variables, indices, expressionNetwork })
  const html = renderLatex(latex)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <strong style={{ fontSize: 13 }}>LaTeX preview</strong>
      <div
        style={{
          padding: 12,
          border: '1px solid #ccc',
          borderRadius: 4,
          background: '#fff',
          minHeight: 60,
          overflowX: 'auto',
        }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
      <code style={{ fontSize: 12, color: '#555', wordBreak: 'break-all' }}>{latex}</code>
    </div>
  )
}
