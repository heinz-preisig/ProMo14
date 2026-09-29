import type { Equation } from '../types'
import { TeX } from './TeX'

/** ``E_n: lhs := rhs`` — math when the backend supplied latex, else text. */
export function EqLine({ eq, lhsLabel }: { eq: Equation; lhsLabel: string }) {
  return (
    <span>
      <TeX latex={eq.lhs_latex} fallback={lhsLabel} />
      {' := '}
      <TeX latex={eq.rhs_latex} fallback={eq.rhs} />
    </span>
  )
}
