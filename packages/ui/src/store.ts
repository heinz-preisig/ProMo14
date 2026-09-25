/** Backend store-status fetchers shared by every app — the
 *  ``/api/ontology/{status,save}`` endpoints are store-global. */

import { apiFetch } from './session'

export interface StoreStatus {
  dirty: boolean
  last_saved: string | null
}

export async function getStoreStatus(): Promise<StoreStatus> {
  const res = await apiFetch('/api/ontology/status')
  if (!res.ok) throw new Error(`Failed to load store status: ${res.status}`)
  return res.json()
}

export async function saveStore(): Promise<{ saved: string }> {
  const res = await apiFetch('/api/ontology/save', { method: 'POST' })
  if (!res.ok) throw new Error(`save: ${res.status} ${await res.text()}`)
  return res.json()
}
