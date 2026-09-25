import { useEffect, useState } from 'react'
import { getVariableReferences } from './api'
import type { VariableReferences } from './api'

/** Proactive §18 usage lock: how many equations reference the variable.
 *  ``count`` is null while fetching or on error — the backend still
 *  guards with a 409, so the lock is a courtesy. */
export function useVariableLock(iri: string | null | undefined) {
  const [references, setReferences] = useState<VariableReferences['references']>([])
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    setCount(null)
    setReferences([])
    if (!iri) return
    let cancelled = false
    getVariableReferences(iri)
      .then((r) => {
        if (!cancelled) {
          setReferences(r.references)
          setCount(r.references.length)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [iri])

  return { count, references, used: (count ?? 0) > 0 }
}
