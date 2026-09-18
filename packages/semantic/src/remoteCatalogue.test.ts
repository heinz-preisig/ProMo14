import { describe, expect, it } from 'vitest'
import { buildConnectionQuery } from './connectionService'
import { placeholderCatalogue } from './placeholderCatalogue'
import { RemoteCatalogue } from './remoteCatalogue'
import type { CatalogueFetchers } from './remoteCatalogue'

const fetchers: CatalogueFetchers = {
  entityTypes: async () => [
    {
      iri: 'promo:EntityType/capacity',
      label: 'capacity',
      temporal_type: 'dynamic',
      spatial_type: 'distributed',
      branch: 'physical',
    },
    {
      iri: 'promo:EntityType/control',
      label: 'control',
      temporal_type: 'event-dynamic',
      branch: 'information',
    },
    {
      iri: 'promo:EntityType/noBranch',
      label: 'branchless',
      temporal_type: 'constant',
    },
  ],
  domains: async () => [
    { iri: 'promo:Domain/physical', name: 'physical', branch: 'physical' },
    { iri: 'promo:Domain/information', name: 'information', branch: 'information' },
    { iri: 'promo:Domain/thermo', name: 'thermo', parent: 'promo:Domain/physical' },
  ],
  tokens: async () => [
    { iri: 'promo:Token/mass', label: 'mass', kind: 'conserved' },
  ],
  connectionRules: async () => [
    { iri: 'promo:Rule/1', rule_type: 'physical-same', carrier: 'token-flow' },
    { iri: 'promo:Rule/2', rule_type: 'access', carrier: 'reference' },
    { iri: 'promo:Rule/3', rule_type: 'physical-same', carrier: 'token-flow' },
  ],
}

async function load() {
  const cat = await RemoteCatalogue.load(fetchers, placeholderCatalogue)
  return cat
}

describe('RemoteCatalogue', () => {
  it('maps entity types with branch -> domain IRI', async () => {
    const cat = await load()
    const cap = cat.getBaseEntity('promo:EntityType/capacity')
    expect(cap?.label).toBe('capacity')
    expect(cap?.typeIris).toEqual(['promo:EntityType/capacity'])
    expect(cap?.domainTypeIris).toEqual(['promo:Domain/physical'])
    const ctrl = cat.getBaseEntity('promo:EntityType/control')
    expect(ctrl?.domainTypeIris).toEqual(['promo:Domain/information'])
    // no branch -> empty domain list
    expect(cat.getBaseEntity('promo:EntityType/noBranch')?.domainTypeIris).toEqual([])
  })

  it('records temporal/spatial metadata as attributes', async () => {
    const cat = await load()
    const cap = cat.getBaseEntity('promo:EntityType/capacity')
    const attrs = Object.fromEntries(
      (cap?.attributes ?? []).map((a) => [a.predicateIri, a.value]),
    )
    expect(attrs['promo:temporalType']).toBe('dynamic')
    expect(attrs['promo:spatialType']).toBe('distributed')
  })

  it('synthesises arc types from rule carriers', async () => {
    const cat = await load()
    const iris = cat.getArcTypes().map((a) => a.iri).sort()
    expect(iris).toEqual(['promo:ArcType/reference', 'promo:ArcType/token-flow'])
  })

  it('exposes domains and tokens', async () => {
    const cat = await load()
    expect(cat.getDomain('promo:Domain/thermo')?.label).toBe('thermo')
    expect(cat.getToken('promo:Token/mass')?.label).toBe('mass')
  })

  it('delegates graphical definitions to the fallback', async () => {
    const cat = await load()
    const cap = cat.getBaseEntity('promo:EntityType/capacity')
    expect(cap?.graphicalDefinitionIri).toBeTruthy()
    expect(cat.getGraphicalDefinition(cap!.graphicalDefinitionIri!)).toBeTruthy()
  })

  it('returns the fallback catalogue when the backend is down', async () => {
    const cat = await RemoteCatalogue.load(
      {
        entityTypes: () => Promise.reject(new Error('down')),
        domains: fetchers.domains,
        tokens: fetchers.tokens,
        connectionRules: fetchers.connectionRules,
      },
      placeholderCatalogue,
    )
    expect(cat).toBe(placeholderCatalogue)
  })
})

describe('buildConnectionQuery with domain-backed entities', () => {
  it('populates domainTypeIris from the entity definitions', async () => {
    const cat = await load()
    const q = buildConnectionQuery(
      'promo:EntityType/capacity',
      'promo:EntityType/control',
      cat,
    )
    expect(q.sourceDomainTypeIris).toEqual(['promo:Domain/physical'])
    expect(q.targetDomainTypeIris).toEqual(['promo:Domain/information'])
    expect(q.sourceEntityTypeIris).toEqual(['promo:EntityType/capacity'])
  })

  it('leaves domain IRIs empty for placeholder entities', () => {
    const q = buildConnectionQuery('promo:TypeA', 'promo:TypeB', placeholderCatalogue)
    expect(q.sourceDomainTypeIris).toEqual([])
    expect(q.targetDomainTypeIris).toEqual([])
  })
})
