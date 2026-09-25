import type { CodeOut, InstantiationReport } from './types'
import { createApiFetch, sessionParam } from '@promo/ui'

export { GRAPH_IRI, getStoreStatus, saveStore } from '@promo/ui'

/** The var/expr artefact supplying variables, equations and the
 *  assignment graph — ?vars= (default: dataset-wide scope). */
export const VARS_IRI = sessionParam('vars')

const apiFetch = createApiFetch('vars')

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
