import type {
  Assignment,
  BehaviourContext,
  EvaluateReport,
  Selection,
} from './types'
import { apiFetch } from '@promo/ui'

export { GRAPH_IRI, getStoreStatus, saveStore } from '@promo/ui'

export async function loadContext(): Promise<BehaviourContext> {
  const res = await apiFetch('/api/behaviour/context')
  return res.json() as Promise<BehaviourContext>
}

export async function evaluate(sel: Selection): Promise<EvaluateReport> {
  const res = await apiFetch('/api/behaviour/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sel),
  })
  return res.json() as Promise<EvaluateReport>
}

export async function loadAssignment(
  entityType: string,
): Promise<Assignment | null> {
  const res = await apiFetch(
    `/api/behaviour/assignment?entity_type=${encodeURIComponent(entityType)}`,
  )
  if (res.status === 404) return null
  return res.json() as Promise<Assignment>
}

export async function saveAssignment(sel: Selection): Promise<Assignment> {
  const res = await apiFetch('/api/behaviour/assignment', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sel),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<Assignment>
}

export async function listAssignments(): Promise<Assignment[]> {
  const res = await apiFetch('/api/behaviour/assignments')
  return res.json() as Promise<Assignment[]>
}

export async function deleteAssignment(entityType: string): Promise<void> {
  await apiFetch(
    `/api/behaviour/assignment?entity_type=${encodeURIComponent(entityType)}`,
    { method: 'DELETE' },
  )
}
