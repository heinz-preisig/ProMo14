import { useEffect, useState } from 'react'
import { getVariableReferences } from './api'

/** Proactive §18 usage lock: how many equations reference the variable.
 *  ``count`` is null while fetching or on error — the backend still
 *  guards with a 409, so the lock is a courtesy. */
export function useVariableLock(iri: string | null | undefined) {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    setCount(null)
    if (!iri) return
    let cancelled = false
    getVariableReferences(iri)
      .then((r) => {
        if (!cancelled) setCount(r.references.length)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [iri])

  return { count, used: (count ?? 0) > 0 }
}
