import { useEffect, useState } from 'react'
import { storeStatus } from './api'

/** Poll the backend store dirty flag; warn on tab close if unsaved. */
export function useStoreDirty(intervalMs = 3000) {
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      try {
        const s = await storeStatus()
        if (alive) setDirty(!!s.dirty)
      } catch {
        /* backend down — leave flag as-is */
      }
    }
    tick()
    const t = setInterval(tick, intervalMs)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [intervalMs])

  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  return dirty
}
