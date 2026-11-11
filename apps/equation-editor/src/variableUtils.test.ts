import { describe, expect, it } from 'vitest'

import type { Variable } from './types'
import { referenceDisplay, signatureMismatch } from './variableUtils'

const ZERO = [0, 0, 0, 0, 0, 0, 0, 0]
const IDX_N = 'https://w3id.org/promo#index_N'
const IDX_A = 'https://w3id.org/promo#index_A'

describe('signatureMismatch — §18 fixed-signature rule', () => {
  it('accepts an identical derived signature', () => {
    const declared = { units: [0, 0, 0, 1, 0, 0, 0, 0], index_structures: [IDX_N] }
    const derived = { units: [0, 0, 0, 1, 0, 0, 0, 0], indices: [IDX_N] }
    expect(signatureMismatch(declared, derived)).toEqual([])
  })

  it('flags differing units', () => {
    const declared = { units: [0, 0, 0, 1, 0, 0, 0, 0], index_structures: [IDX_N] }
    const derived = { units: [1, 0, 0, 0, 0, 0, 0, 0], indices: [IDX_N] }
    expect(signatureMismatch(declared, derived)).toEqual(['units'])
  })

  it('flags differing index structures, including order', () => {
    const declared = { units: ZERO, index_structures: [IDX_N, IDX_A] }
    expect(
      signatureMismatch(declared, { units: ZERO, indices: [IDX_A, IDX_N] }),
    ).toEqual(['index structure'])
    expect(
      signatureMismatch(declared, { units: ZERO, indices: [IDX_N] }),
    ).toEqual(['index structure'])
  })

  it('flags both fields together', () => {
    const declared = { units: ZERO, index_structures: [IDX_N] }
    const derived = { units: [1, 0, 0, 0, 0, 0, 0, 0], indices: [IDX_A] }
    expect(signatureMismatch(declared, derived)).toEqual([
      'units',
      'index structure',
    ])
  })

  it('treats a missing declared unit vector as zero', () => {
    expect(
      signatureMismatch({ index_structures: [] }, { units: ZERO, indices: [] }),
    ).toEqual([])
    expect(
      signatureMismatch(
        { index_structures: [] },
        { units: [1, 0, 0, 0, 0, 0, 0, 0], indices: [] },
      ),
    ).toEqual(['units'])
  })

  it('skips untracked derived fields — cannot compare what was not derived', () => {
    const declared = { units: [1, 0, 0, 0, 0, 0, 0, 0], index_structures: [IDX_N] }
    expect(signatureMismatch(declared, { units: null, indices: null })).toEqual(
      [],
    )
    expect(signatureMismatch(declared, {})).toEqual([])
  })
})

describe('referenceDisplay — §18 used-by readout', () => {
  const BASE = 'https://ex.org/lib'
  const variables = [
    {
      iri: `${BASE}#V_1`,
      label: 'fmc',
      internal_id: 'V_1',
      network: 'root',
      equations: {
        E_4: { iri: `${BASE}#E_4`, internal_id: 'E_4', lhs: 'fmc', rhs: 'x' },
      },
    },
  ] as unknown as Variable[]

  it('extracts the equation fragment and resolves the owner by dict key', () => {
    const ref = { equation: `${BASE}#E_4`, graph: BASE, via: 'rhs' }
    expect(referenceDisplay(ref, variables)).toEqual({
      eqId: 'E_4',
      ownerLabel: 'fmc',
    })
  })

  it('resolves by the equation record IRI when the dict key differs', () => {
    const vars = [
      {
        iri: `${BASE}#V_1`,
        label: 'fmc',
        internal_id: 'V_1',
        network: 'root',
        equations: {
          root: { iri: `${BASE}#E_4`, lhs: 'fmc', rhs: 'x' },
        },
      },
    ] as unknown as Variable[]
    const ref = { equation: `${BASE}#E_4`, graph: BASE, via: 'lhs' }
    expect(referenceDisplay(ref, vars)).toEqual({
      eqId: 'E_4',
      ownerLabel: 'fmc',
    })
  })

  it('returns a null owner for equations owned outside the set', () => {
    const ref = { equation: `${BASE}#E_9`, graph: BASE, via: 'rhs' }
    expect(referenceDisplay(ref, variables)).toEqual({
      eqId: 'E_9',
      ownerLabel: null,
    })
  })
})
