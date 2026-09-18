import { useCallback, useEffect, useRef, useState } from 'react'
import { getStoreStatus } from './api'

/** Poll the backend's dirty flag and warn on tab close while changes are
 *  unsaved.  The flag is store-global: mutations from any editor (or the
 *  catalogue) light the badge in every open tool. */
export function useStoreDirty(pollMs = 4000) {
  const [dirty, setDirty] = useState(false)
  const dirtyRef = useRef(false)

  const refresh = useCallback(async () => {
    try {
      const s = await getStoreStatus()
      dirtyRef.current = s.dirty
      setDirty(s.dirty)
    } catch {
      // Backend unreachable — keep last known state.
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, pollMs)
    return () => clearInterval(t)
  }, [refresh, pollMs])

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirtyRef.current) e.preventDefault()
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [])

  return { dirty, refresh }
}
