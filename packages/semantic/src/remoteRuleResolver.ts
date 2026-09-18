import type {
  Iri,
  AsyncConnectionRuleResolver,
  ConnectionRuleQuery,
  ConnectionRuleResolver,
  ConnectionRuleResult,
} from './contracts'

// ---------------------------------------------------------------------------
// Remote connection-rule resolver
//
// Implements the synchronous ConnectionRuleResolver interface over
// GET /api/ontology/resolve-connection (ancestor-aware rule matching lives
// in the backend — single authority, no duplicated logic here).
//
//   resolve()      — sync cache read for hover feedback; on a miss it fires
//                    the fetch in the background and returns a neutral
//                    "allowed, no connections" result.  onUpdate() fires
//                    when the real answer lands so the UI can re-render.
//   resolveAsync() — authoritative answer for connect actions (right-click
//                    insert, open-arc reconnect).
//
// Endpoint pair selection: the backend resolves *domain* IRIs, so domain
// type IRIs win when the query carries them; otherwise the entity type IRI
// itself is used (entity types double as domain selectors until the
// modeller models domains explicitly).
//
// Rule → arc type: the backend licenses *carriers* (token-flow | reference),
// surfaced as arcTypeIri `promo:ArcType/<carrier>` (falling back to the
// rule type when a rule has no carrier).
// ---------------------------------------------------------------------------

export interface RemoteRuleResolverOptions {
  /** Base URL prefix for the API (default '' — uses the dev-server proxy). */
  baseUrl?: string
  /** Artefact graph IRI for the session (the hub's ?graph= param). */
  graphIri?: string
  /** Resolver used when the fetch fails (e.g. backend down).  Errors are
   *  not cached, so the remote is retried on the next query. */
  fallback?: ConnectionRuleResolver
  /** Called after a fetch populates the cache — e.g. bump a React state. */
  onUpdate?: () => void
}

interface ResolveConnectionResponse {
  rules: { iri: Iri; rule_type?: string; carrier?: string }[]
}

export class RemoteRuleResolver implements AsyncConnectionRuleResolver {
  private cache = new Map<string, ConnectionRuleResult>()
  private pending = new Map<string, Promise<ConnectionRuleResult>>()

  constructor(private opts: RemoteRuleResolverOptions = {}) {}

  /** The (source, target) domain pair the backend resolves for a query. */
  private endpointPair(query: ConnectionRuleQuery): { source: Iri; target: Iri } | null {
    const source = query.sourceDomainTypeIris[0] ?? query.sourceEntityTypeIris[0]
    const target = query.targetDomainTypeIris[0] ?? query.targetEntityTypeIris[0]
    if (!source || !target) return null
    return { source, target }
  }

  resolve(query: ConnectionRuleQuery): ConnectionRuleResult {
    const pair = this.endpointPair(query)
    if (!pair) return { status: 'forbidden', reason: 'no endpoint IRIs in query' }
    const key = `${pair.source}|${pair.target}`
    const hit = this.cache.get(key)
    if (hit) return hit
    void this.fetchRules(pair.source, pair.target, key, query)
    return { status: 'allowed', connections: [] }
  }

  async resolveAsync(query: ConnectionRuleQuery): Promise<ConnectionRuleResult> {
    const pair = this.endpointPair(query)
    if (!pair) return { status: 'forbidden', reason: 'no endpoint IRIs in query' }
    const key = `${pair.source}|${pair.target}`
    const hit = this.cache.get(key)
    if (hit) return hit
    return this.fetchRules(pair.source, pair.target, key, query)
  }

  /** Drop all cached answers (e.g. after the ontology changes). */
  invalidate(): void {
    this.cache.clear()
  }

  private fetchRules(
    source: Iri,
    target: Iri,
    key: string,
    query: ConnectionRuleQuery,
  ): Promise<ConnectionRuleResult> {
    const inFlight = this.pending.get(key)
    if (inFlight) return inFlight

    const params = new URLSearchParams({ source, target })
    if (this.opts.graphIri) params.set('graph', this.opts.graphIri)
    const url = `${this.opts.baseUrl ?? ''}/api/ontology/resolve-connection?${params}`

    const promise = fetch(url)
      .then(async (res): Promise<ConnectionRuleResult> => {
        if (!res.ok) throw new Error(`resolve-connection ${res.status}`)
        const body = (await res.json()) as ResolveConnectionResponse
        const result: ConnectionRuleResult = body.rules.length === 0
          ? { status: 'forbidden', reason: 'no applicable connection rules' }
          : {
              status: 'allowed',
              connections: body.rules.map((r) => ({
                ruleIri: r.iri,
                arcTypeIri: `promo:ArcType/${r.carrier ?? r.rule_type ?? 'generic'}`,
              })),
            }
        // Only real backend answers are cached — a fallback result below
        // must not stick, or the remote would never be retried.
        this.cache.set(key, result)
        return result
      })
      .catch((err): ConnectionRuleResult => {
        if (this.opts.fallback) return this.opts.fallback.resolve(query)
        return { status: 'forbidden', reason: `resolve-connection failed: ${err}` }
      })
      .then((result) => {
        this.pending.delete(key)
        this.opts.onUpdate?.()
        return result
      })

    this.pending.set(key, promise)
    return promise
  }
}
