import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { RemoteRuleResolver } from './remoteRuleResolver'
import { buildConnectionQuery } from './connectionService'
import { placeholderCatalogue, placeholderRuleResolver } from './placeholderCatalogue'
import type { ConnectionRuleQuery } from './contracts'

const QUERY: ConnectionRuleQuery = buildConnectionQuery(
  'promo:TypeA',
  'promo:TypeB',
  placeholderCatalogue,
)

function mockFetch(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(body),
  } as Response)
}

const RULES_BODY = {
  source: 'promo:TypeA',
  target: 'promo:TypeB',
  rules: [
    { iri: 'promo:rule_physical-same', rule_type: 'physical-same', carrier: 'token-flow' },
    { iri: 'promo:rule_access', rule_type: 'access', carrier: 'reference' },
  ],
}

describe('RemoteRuleResolver', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch(RULES_BODY))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('maps backend rules to allowed connections with carrier arc types', async () => {
    const r = new RemoteRuleResolver()
    const result = await r.resolveAsync(QUERY)
    expect(result.status).toBe('allowed')
    if (result.status === 'allowed') {
      expect(result.connections).toEqual([
        { ruleIri: 'promo:rule_physical-same', arcTypeIri: 'https://w3id.org/promo#ArcType/token-flow' },
        { ruleIri: 'promo:rule_access', arcTypeIri: 'https://w3id.org/promo#ArcType/reference' },
      ])
    }
  })

  it('falls back to rule_type for the arc type when carrier is missing', async () => {
    vi.stubGlobal('fetch', mockFetch({
      rules: [{ iri: 'promo:rule_x', rule_type: 'signal' }],
    }))
    const r = new RemoteRuleResolver()
    const result = await r.resolveAsync(QUERY)
    expect(result.status === 'allowed' && result.connections[0].arcTypeIri)
      .toBe('https://w3id.org/promo#ArcType/signal')
  })

  it('returns forbidden when the backend lists no applicable rules', async () => {
    vi.stubGlobal('fetch', mockFetch({ rules: [] }))
    const r = new RemoteRuleResolver()
    const result = await r.resolveAsync(QUERY)
    expect(result.status).toBe('forbidden')
  })

  it('sends source/target (+ graph) as query params', async () => {
    const f = mockFetch(RULES_BODY)
    vi.stubGlobal('fetch', f)
    const r = new RemoteRuleResolver({ graphIri: 'promo:graph/x' })
    await r.resolveAsync(QUERY)
    const url = f.mock.calls[0][0] as string
    expect(url).toContain('source=promo%3ATypeA')
    expect(url).toContain('target=promo%3ATypeB')
    expect(url).toContain('graph=promo%3Agraph%2Fx')
  })

  it('sync resolve returns a neutral answer on cache miss, then the real one', async () => {
    const r = new RemoteRuleResolver()
    const first = r.resolve(QUERY)
    expect(first).toEqual({ status: 'allowed', connections: [] })
    await r.resolveAsync(QUERY) // warm the cache
    const second = r.resolve(QUERY)
    expect(second.status === 'allowed' && second.connections.length).toBe(2)
  })

  it('deduplicates in-flight fetches for the same pair', async () => {
    const f = mockFetch(RULES_BODY)
    vi.stubGlobal('fetch', f)
    const r = new RemoteRuleResolver()
    await Promise.all([r.resolveAsync(QUERY), r.resolveAsync(QUERY)])
    expect(f).toHaveBeenCalledTimes(1)
  })

  it('caches per etype pair — same domains, different etypes resolve independently', async () => {
    // §14: lumped↔env and lumped↔transport share domain_physical|
    // domain_physical but license different rules.  A domain-only key
    // would return the first resolution for every physical pair.
    const base = {
      sourceDomainTypeIris: ['promo:domain_physical'],
      targetDomainTypeIris: ['promo:domain_physical'],
      sourceTokenTypeIris: [],
      targetTokenTypeIris: [],
      domainRelation: 'internal' as const,
    }
    const qEnv: ConnectionRuleQuery = {
      ...base,
      sourceEntityTypeIris: ['promo:et_lumped'],
      targetEntityTypeIris: ['promo:et_env'],
    }
    const qConv: ConnectionRuleQuery = {
      ...base,
      sourceEntityTypeIris: ['promo:et_lumped'],
      targetEntityTypeIris: ['promo:et_conv'],
    }
    const accessOnly = {
      rules: [{ iri: 'promo:rule_access', rule_type: 'access', carrier: 'reference' }],
    }
    const f = vi.fn().mockImplementation((url: string) => {
      const body = url.includes('target_etype=promo%3Aet_env')
        ? accessOnly : RULES_BODY
      return Promise.resolve({
        ok: true, status: 200, json: () => Promise.resolve(body),
      } as Response)
    })
    vi.stubGlobal('fetch', f)
    const r = new RemoteRuleResolver()
    const envRes = await r.resolveAsync(qEnv)
    const convRes = await r.resolveAsync(qConv)
    expect(f).toHaveBeenCalledTimes(2)
    expect(envRes.status === 'allowed' && envRes.connections.map((c) => c.arcTypeIri))
      .toEqual(['https://w3id.org/promo#ArcType/reference'])
    expect(convRes.status === 'allowed' && convRes.connections.length).toBe(2)
    // Re-resolve — still cached under their own keys, no third fetch.
    await r.resolveAsync(qEnv)
    expect(f).toHaveBeenCalledTimes(2)
  })

  it('uses the fallback resolver on fetch error and does not cache it', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    const r = new RemoteRuleResolver({ fallback: placeholderRuleResolver })
    const result = await r.resolveAsync(QUERY)
    // Placeholder allow-all answer
    expect(result.status === 'allowed' && result.connections.length).toBe(2)
    // Not cached: a working backend is picked up on the next query.
    vi.stubGlobal('fetch', mockFetch(RULES_BODY))
    const retry = await r.resolveAsync(QUERY)
    expect(retry.status === 'allowed' && retry.connections[0].ruleIri)
      .toBe('promo:rule_physical-same')
  })

  it('returns forbidden without a fetch when the query has no endpoint IRIs', async () => {
    const f = mockFetch(RULES_BODY)
    vi.stubGlobal('fetch', f)
    const r = new RemoteRuleResolver()
    const empty: ConnectionRuleQuery = {
      sourceEntityTypeIris: [],
      targetEntityTypeIris: [],
      sourceDomainTypeIris: [],
      targetDomainTypeIris: [],
      sourceTokenTypeIris: [],
      targetTokenTypeIris: [],
      domainRelation: 'internal',
    }
    const result = await r.resolveAsync(empty)
    expect(result.status).toBe('forbidden')
    expect(f).not.toHaveBeenCalled()
  })

  it('prefers domain type IRIs over entity type IRIs for the endpoint pair', async () => {
    const f = mockFetch(RULES_BODY)
    vi.stubGlobal('fetch', f)
    const r = new RemoteRuleResolver()
    const q: ConnectionRuleQuery = {
      ...QUERY,
      sourceDomainTypeIris: ['promo:domain/physical'],
      targetDomainTypeIris: ['promo:domain/information'],
    }
    await r.resolveAsync(q)
    const url = f.mock.calls[0][0] as string
    expect(url).toContain('source=promo%3Adomain%2Fphysical')
    expect(url).toContain('target=promo%3Adomain%2Finformation')
  })
})
