import { describe, expect, it } from 'vitest'
import { affectedEquations, signatureText } from './consistencyUtils'
import type { ConsistencyReport, ConsistencyRow } from './types'

const row = (variable: string, operands: string[]): ConsistencyRow => ({
  variable, label: variable, equation: `E_${variable}`, equation_id: `E_${variable}`,
  network: 'physical', graphs: [], rhs: '', status: 'consistent',
  declared: { units: [], indices: [], tokens: {} }, derived: null,
  operands: operands.map((iri) => ({ iri, label: iri, tokens: {}, graphs: [] })), conflicts: [], findings: [],
})

describe('consistency report', () => {
  it('finds transitive consumers independent of report order and handles cycles', () => {
    const report: ConsistencyReport = {
      graph: 'g', revision: 'r', summary: { consistent: 4, error: 0, advisory: 0, untracked: 0 },
      equations: [row('c', ['b']), row('b', ['a']), row('a', ['c']), row('other', [])],
    }
    expect(affectedEquations(report, 'a').map((r) => r.variable)).toEqual(['c', 'b', 'a'])
  })
  it('does not label missing tracking as neutral', () => {
    expect(signatureText(null)).toBe('untracked')
    expect(signatureText({})).toBe('neutral ({})')
    expect(signatureText({ mass: 1, time: -1 })).toBe('mass^1 time^-1')
  })
})
