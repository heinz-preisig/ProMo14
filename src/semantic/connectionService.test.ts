import { describe, it, expect } from 'vitest'
import { buildConnectionQuery, resolveConnection, pickArcType } from './connectionService'
import { placeholderCatalogue, placeholderRuleResolver } from './placeholderCatalogue'
import type { ConnectionRuleResult } from './contracts'

describe('buildConnectionQuery', () => {
  it('uses typeIris from entity definitions when available', () => {
    const query = buildConnectionQuery('promo:TypeA', 'promo:TypeB', placeholderCatalogue)
    // Placeholder entities have empty typeIris, so the entity IRI itself is used
    expect(query.sourceEntityTypeIris).toEqual(['promo:TypeA'])
    expect(query.targetEntityTypeIris).toEqual(['promo:TypeB'])
  })

  it('falls back to the entity type IRI when entity is not in catalogue', () => {
    const query = buildConnectionQuery('promo:UnknownA', 'promo:UnknownB', placeholderCatalogue)
    expect(query.sourceEntityTypeIris).toEqual(['promo:UnknownA'])
    expect(query.targetEntityTypeIris).toEqual(['promo:UnknownB'])
  })

  it('defaults domain and token type IRIs to empty arrays', () => {
    const query = buildConnectionQuery('promo:TypeA', 'promo:TypeB', placeholderCatalogue)
    expect(query.sourceDomainTypeIris).toEqual([])
    expect(query.targetDomainTypeIris).toEqual([])
    expect(query.sourceTokenTypeIris).toEqual([])
    expect(query.targetTokenTypeIris).toEqual([])
  })

  it('defaults domainRelation to internal', () => {
    const query = buildConnectionQuery('promo:TypeA', 'promo:TypeB', placeholderCatalogue)
    expect(query.domainRelation).toBe('internal')
  })
})

describe('resolveConnection', () => {
  it('returns allowed with both arc types from the placeholder resolver', () => {
    const result = resolveConnection(
      'promo:TypeA',
      'promo:TypeB',
      placeholderCatalogue,
      placeholderRuleResolver,
    )
    expect(result.status).toBe('allowed')
    if (result.status === 'allowed') {
      expect(result.connections).toHaveLength(2)
      expect(result.connections[0].arcTypeIri).toBe('promo:ArcType1')
      expect(result.connections[1].arcTypeIri).toBe('promo:ArcType2')
    }
  })
})

describe('pickArcType', () => {
  const allowedResult: ConnectionRuleResult = {
    status: 'allowed',
    connections: [
      { ruleIri: 'promo:Rule/X', arcTypeIri: 'promo:ArcType1' },
      { ruleIri: 'promo:Rule/Y', arcTypeIri: 'promo:ArcType2' },
    ],
  }

  it('returns the preferred arc type when it is among allowed connections', () => {
    expect(pickArcType(allowedResult, 'promo:ArcType2')).toBe('promo:ArcType2')
  })

  it('returns the first allowed arc type when preferred is not in the list', () => {
    expect(pickArcType(allowedResult, 'promo:ArcType99')).toBe('promo:ArcType1')
  })

  it('returns null when allowed but connections list is empty', () => {
    const emptyAllowed: ConnectionRuleResult = {
      status: 'allowed',
      connections: [],
    }
    expect(pickArcType(emptyAllowed, 'promo:ArcType1')).toBeNull()
  })

  it('returns null when the result is forbidden', () => {
    const forbidden: ConnectionRuleResult = {
      status: 'forbidden',
      reason: 'Incompatible types',
    }
    expect(pickArcType(forbidden, 'promo:ArcType1')).toBeNull()
  })
})
