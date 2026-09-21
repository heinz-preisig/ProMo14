import type { Variable } from './types'

/** Next free ``V_n`` internal id across the variable set. */
export function nextInternalId(variables: Variable[]): string {
  const max = variables
    .map((v) => parseInt(v.internal_id?.replace(/^V_/, '') ?? '0', 10))
    .filter((n) => !Number.isNaN(n))
  const next = (max.length ? Math.max(...max) : 0) + 1
  return `V_${next}`
}

/** Next free ``E_n`` equation id across all variables' equations.
 *  Smallest-free, not max+1: legacy ``E_<epoch-ms>`` ids would poison
 *  the sequence forever. */
export function nextEquationId(variables: Variable[]): string {
  const used = new Set<number>()
  for (const v of variables) {
    for (const [key, eq] of Object.entries(v.equations ?? {})) {
      for (const cand of [key, eq.internal_id]) {
        const m = /^E_(\d+)$/.exec(cand ?? '')
        if (m) used.add(parseInt(m[1], 10))
      }
    }
  }
  let n = 1
  while (used.has(n)) n += 1
  return `E_${n}`
}
