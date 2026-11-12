import type { ConsistencyReport, ConsistencyRow } from './types'

export function affectedEquations(report: ConsistencyReport, variable: string): ConsistencyRow[] {
  const changed = new Set([variable])
  const affected = new Set<ConsistencyRow>()
  let grew = true
  while (grew) {
    grew = false
    for (const row of report.equations) {
      if (!affected.has(row) && (changed.has(row.variable) || row.operands.some((v) => changed.has(v.iri)))) {
        affected.add(row)
        changed.add(row.variable)
        grew = true
      }
    }
  }
  return report.equations.filter((r) => affected.has(r))
}
