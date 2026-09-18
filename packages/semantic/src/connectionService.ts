import type {
  Iri,
  AsyncConnectionRuleResolver,
  ConnectionRuleQuery,
  ConnectionRuleResult,
  ConnectionRuleResolver,
  SemanticCatalogue,
} from './contracts'

// ---------------------------------------------------------------------------
// Shared connection-rule service
//
// Both arc creation (insertArc) and open-arc reconnection (reconnectOpenArc)
// go through this service so that a single resolver decides validity and
// picks the arc type.  Entity ``domainTypeIris`` feed the domain-based
// backend resolution; catalogue-only placeholder types leave them empty.
// ---------------------------------------------------------------------------

export function buildConnectionQuery(
  sourceEntityType: Iri,
  targetEntityType: Iri,
  catalogue: SemanticCatalogue,
): ConnectionRuleQuery {
  const sourceEntity = catalogue.getBaseEntity(sourceEntityType)
  const targetEntity = catalogue.getBaseEntity(targetEntityType)

  return {
    sourceEntityTypeIris: sourceEntity?.typeIris.length
      ? sourceEntity.typeIris
      : [sourceEntityType],
    targetEntityTypeIris: targetEntity?.typeIris.length
      ? targetEntity.typeIris
      : [targetEntityType],
    sourceDomainTypeIris: sourceEntity?.domainTypeIris ?? [],
    targetDomainTypeIris: targetEntity?.domainTypeIris ?? [],
    sourceTokenTypeIris: [],
    targetTokenTypeIris: [],
    domainRelation: 'internal',
  }
}

export function resolveConnection(
  sourceEntityType: Iri,
  targetEntityType: Iri,
  catalogue: SemanticCatalogue,
  resolver: ConnectionRuleResolver,
): ConnectionRuleResult {
  const query = buildConnectionQuery(sourceEntityType, targetEntityType, catalogue)
  return resolver.resolve(query)
}

/** Async variant for connect actions (insert arc, reconnect open arc) that
 *  need the authoritative answer.  Falls back to the sync ``resolve`` for
 *  resolvers without an async path. */
export async function resolveConnectionAsync(
  sourceEntityType: Iri,
  targetEntityType: Iri,
  catalogue: SemanticCatalogue,
  resolver: ConnectionRuleResolver,
): Promise<ConnectionRuleResult> {
  const query = buildConnectionQuery(sourceEntityType, targetEntityType, catalogue)
  if ('resolveAsync' in resolver) {
    return (resolver as AsyncConnectionRuleResolver).resolveAsync(query)
  }
  return resolver.resolve(query)
}

export function pickArcType(
  result: ConnectionRuleResult,
  preferredArcType: Iri,
): Iri | null {
  if (result.status === 'forbidden') return null

  if (result.connections.length === 0) return null

  const preferred = result.connections.find((c) => c.arcTypeIri === preferredArcType)
  if (preferred) return preferred.arcTypeIri

  return result.connections[0].arcTypeIri
}
