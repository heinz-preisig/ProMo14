import type { EquationClass, Variable } from './types'

/** Display label for a stored ``equation_class`` — resolves an
 *  EquationClass IRI to its label; legacy bare labels pass through. */
export function equationClassLabel(
  ref: string | null | undefined,
  classes: EquationClass[],
): string {
  if (!ref) return ''
  return classes.find((c) => c.iri === ref)?.label ?? ref
}

/** §18 fixed-signature rule: a used variable keeps its units and
 *  index structures — any equation attached or rewritten on it must
 *  derive exactly the declared signature.  Returns the mismatching
 *  field labels (``[]`` when the derived signature matches, or when a
 *  derived field is untracked and cannot be compared). */
export function signatureMismatch(
  declared: { units?: number[] | null; index_structures?: string[] | null },
  derived: { units?: number[] | null; indices?: string[] | null },
): string[] {
  const bad: string[] = []
  if (
    derived.units &&
    JSON.stringify(derived.units) !==
      JSON.stringify(declared.units ?? [0, 0, 0, 0, 0, 0, 0, 0])
  ) {
    bad.push('units')
  }
  if (
    derived.indices &&
    JSON.stringify([...derived.indices].sort()) !==
      JSON.stringify([...(declared.index_structures ?? [])].sort())
  ) {
    bad.push('index structure')
  }
  return bad
}

/** Display pieces for a §18 ``/references`` entry: the equation's
 *  local id and the label of the variable that owns the equation.
 *  ``via === 'lhs'`` marks the variable's own defining equations;
 *  other values are foreign uses inside an rhs. */
export function referenceDisplay(
  ref: { equation: string; graph: string; via: string },
  variables: Variable[],
): { eqId: string; ownerLabel: string | null } {
  const eqId = ref.equation.split('#').pop() ?? ref.equation
  const owner = variables.find((v) =>
    Object.entries(v.equations ?? {}).some(
      ([key, eq]) =>
        key === eqId || eq.iri === ref.equation || eq.internal_id === eqId,
    ),
  )
  return { eqId, ownerLabel: owner?.label ?? null }
}

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
