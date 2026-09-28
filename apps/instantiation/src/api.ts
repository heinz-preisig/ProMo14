import type {
  CodeOut,
  InitialOut,
  InstantiationReport,
  ValueCellsOut,
} from './types'
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

/** Replace a variable's §20 value-cell table — ``values`` keys are
 *  "|"-joined index-element IRIs in indexStructure order. */
export async function putValues(
  variable: string,
  values: Record<string, number>,
): Promise<ValueCellsOut> {
  const res = await apiFetch('/api/instantiate/values', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ variable, values }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<ValueCellsOut>
}

/** The server-side t=0 solve — ``par`` keys are emitted names
 *  (parameter slots + ``ic0_<name>`` for par-pinned ICs), values are
 *  scalars or flat index-ordered lists (C order, last index fastest —
 *  docs/value-cells.md). */
export async function solveInitial(
  par: Record<string, number | number[]>,
  steadyState: boolean,
): Promise<InitialOut> {
  const res = await apiFetch('/api/instantiate/initial', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ par, steady_state: steadyState }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<InitialOut>
}
