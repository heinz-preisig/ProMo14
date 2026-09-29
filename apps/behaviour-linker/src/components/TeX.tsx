import { renderToString } from 'katex'
import { useMemo } from 'react'

/** Inline KaTeX; falls back to monospace text when no latex is stored
 *  or rendering fails. */
export function TeX({
  latex,
  fallback,
}: {
  latex?: string | null
  fallback: string
}) {
  const html = useMemo(() => {
    if (!latex) return null
    try {
      return renderToString(latex, { throwOnError: true, displayMode: false })
    } catch {
      return null
    }
  }, [latex])
  if (html === null) return <code>{fallback}</code>
  return <span dangerouslySetInnerHTML={{ __html: html }} />
}
