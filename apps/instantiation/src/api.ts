import type { CodeOut, InstantiationReport } from './types'

/** The model artefact to instantiate — from the hub's ?graph= link.
 *  Undefined means the default working ontology's model graph. */
export const GRAPH_IRI =
  new URLSearchParams(window.location.search).get('graph') || undefined

/** The var/expr artefact supplying variables, equations and the
 *  assignment graph — ?vars= (default: dataset-wide scope). */
export const VARS_IRI =
  new URLSearchParams(window.location.search).get('vars') || undefined

/** Append the session's graph/vars params to an API path. */
function q(path: string): string {
  const params = new URLSearchParams()
  if (GRAPH_IRI) params.set('graph', GRAPH_IRI)
  if (VARS_IRI) params.set('vars', VARS_IRI)
  const s = params.toString()
  if (!s) return path
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}${s}`
}

function apiFetch(path: string, init?: RequestInit) {
  return fetch(q(path), init)
}

export async function loadReport(): Promise<InstantiationReport> {
  const res = await apiFetch('/api/instantiate/model')
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<InstantiationReport>
}

export async function generateCode(target: string): Promise<CodeOut> {
  const res = await apiFetch(
    `/api/instantiate/code?target=${encodeURIComponent(target)}`,
  )
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<CodeOut>
}

export async function getStoreStatus(): Promise<{ dirty: boolean }> {
  const res = await apiFetch('/api/ontology/status')
  return res.json() as Promise<{ dirty: boolean }>
}

export async function saveStore(): Promise<void> {
  const res = await apiFetch('/api/ontology/save', { method: 'POST' })
  if (!res.ok) throw new Error(`save: ${res.status} ${await res.text()}`)
}
