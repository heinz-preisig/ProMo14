import type {
  AxisTermRecord,
  ClassificationAxisRecord,
  ConnectionRuleRecord,
  DomainRecord,
  EntityTypeRecord,
  IndexRecord,
  NetworkRecord,
  OntologyContext,
  ScaleDimensionRecord,
  ScaleValueRecord,
  TokenRecord,
} from './types'

export async function loadOntologyContext(): Promise<OntologyContext> {
  const res = await fetch('/api/ontology/context')
  if (!res.ok) throw new Error(`Failed to load context: ${res.status}`)
  return res.json()
}

export async function listNetworks(): Promise<NetworkRecord[]> {
  const res = await fetch('/api/ontology/networks')
  if (!res.ok) throw new Error(`Failed to load networks: ${res.status}`)
  return res.json()
}

export async function createNetwork(record: NetworkRecord): Promise<NetworkRecord> {
  const res = await fetch('/api/ontology/networks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create network: ${res.status}`)
  return res.json()
}

export async function listIndices(): Promise<IndexRecord[]> {
  const res = await fetch('/api/ontology/indices')
  if (!res.ok) throw new Error(`Failed to load indices: ${res.status}`)
  return res.json()
}

export async function createIndex(record: IndexRecord): Promise<IndexRecord> {
  const res = await fetch('/api/ontology/indices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create index: ${res.status}`)
  return res.json()
}

export async function deleteIndex(iri: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/ontology/indices/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete index: ${res.status}`)
  return res.json()
}

export async function listTokens(): Promise<TokenRecord[]> {
  const res = await fetch('/api/ontology/tokens')
  if (!res.ok) throw new Error(`Failed to load tokens: ${res.status}`)
  return res.json()
}

export async function createToken(record: TokenRecord): Promise<TokenRecord> {
  const res = await fetch('/api/ontology/tokens', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create token: ${res.status}`)
  return res.json()
}

export async function deleteToken(iri: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/ontology/tokens/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete token: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Domains
// ---------------------------------------------------------------------------

export async function listDomains(): Promise<DomainRecord[]> {
  const res = await fetch('/api/ontology/domains')
  if (!res.ok) throw new Error(`Failed to load domains: ${res.status}`)
  return res.json()
}

export async function createDomain(record: DomainRecord): Promise<DomainRecord> {
  const res = await fetch('/api/ontology/domains', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create domain: ${res.status}`)
  return res.json()
}

export async function deleteDomain(iri: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/ontology/domains/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete domain: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Classification axes
// ---------------------------------------------------------------------------

export async function listAxes(): Promise<ClassificationAxisRecord[]> {
  const res = await fetch('/api/ontology/axes')
  if (!res.ok) throw new Error(`Failed to load axes: ${res.status}`)
  return res.json()
}

export async function createAxis(record: ClassificationAxisRecord): Promise<ClassificationAxisRecord> {
  const res = await fetch('/api/ontology/axes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create axis: ${res.status}`)
  return res.json()
}

export async function deleteAxis(iri: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/ontology/axes/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete axis: ${res.status}`)
  return res.json()
}

export async function listAxisTerms(): Promise<AxisTermRecord[]> {
  const res = await fetch('/api/ontology/axis-terms')
  if (!res.ok) throw new Error(`Failed to load axis terms: ${res.status}`)
  return res.json()
}

export async function createAxisTerm(record: AxisTermRecord): Promise<AxisTermRecord> {
  const res = await fetch('/api/ontology/axis-terms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create axis term: ${res.status}`)
  return res.json()
}

export async function deleteAxisTerm(iri: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/ontology/axis-terms/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete axis term: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Scale dimensions + values
// ---------------------------------------------------------------------------

export async function listScaleDimensions(): Promise<ScaleDimensionRecord[]> {
  const res = await fetch('/api/ontology/scale-dimensions')
  if (!res.ok) throw new Error(`Failed to load scale dimensions: ${res.status}`)
  return res.json()
}

export async function createScaleDimension(record: ScaleDimensionRecord): Promise<ScaleDimensionRecord> {
  const res = await fetch('/api/ontology/scale-dimensions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create scale dimension: ${res.status}`)
  return res.json()
}

export async function deleteScaleDimension(iri: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/ontology/scale-dimensions/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete scale dimension: ${res.status}`)
  return res.json()
}

export async function listScaleValues(): Promise<ScaleValueRecord[]> {
  const res = await fetch('/api/ontology/scale-values')
  if (!res.ok) throw new Error(`Failed to load scale values: ${res.status}`)
  return res.json()
}

export async function createScaleValue(record: ScaleValueRecord): Promise<ScaleValueRecord> {
  const res = await fetch('/api/ontology/scale-values', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create scale value: ${res.status}`)
  return res.json()
}

export async function deleteScaleValue(iri: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/ontology/scale-values/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete scale value: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Entity types
// ---------------------------------------------------------------------------

export async function listEntityTypes(): Promise<EntityTypeRecord[]> {
  const res = await fetch('/api/ontology/entity-types')
  if (!res.ok) throw new Error(`Failed to load entity types: ${res.status}`)
  return res.json()
}

export async function createEntityType(record: EntityTypeRecord): Promise<EntityTypeRecord> {
  const res = await fetch('/api/ontology/entity-types', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create entity type: ${res.status}`)
  return res.json()
}

export async function deleteEntityType(iri: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/ontology/entity-types/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete entity type: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Connection rules
// ---------------------------------------------------------------------------

export async function listConnectionRules(): Promise<ConnectionRuleRecord[]> {
  const res = await fetch('/api/ontology/connection-rules')
  if (!res.ok) throw new Error(`Failed to load connection rules: ${res.status}`)
  return res.json()
}

export async function createConnectionRule(record: ConnectionRuleRecord): Promise<ConnectionRuleRecord> {
  const res = await fetch('/api/ontology/connection-rules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create connection rule: ${res.status}`)
  return res.json()
}

export async function deleteConnectionRule(iri: string): Promise<{ deleted: string }> {
  const res = await fetch(`/api/ontology/connection-rules/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete connection rule: ${res.status}`)
  return res.json()
}

export async function saveOntology(filename: string): Promise<{ saved: string }> {
  const res = await fetch('/api/ontology/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename }),
  })
  if (!res.ok) throw new Error(`Failed to save ontology: ${res.status}`)
  return res.json()
}

export interface OntologyVersion {
  iri: string
  version: string
  published_on: string | null
}

export async function listVersions(): Promise<{ versions: OntologyVersion[]; suggested_next: string }> {
  const res = await fetch('/api/ontology/versions')
  if (!res.ok) throw new Error(`Failed to list versions: ${res.status}`)
  return res.json()
}

export async function publishOntology(version: string): Promise<{ version_iri: string; saved: string }> {
  const res = await fetch('/api/ontology/publish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Publish failed: ${res.status}`)
  }
  return res.json()
}

/** Download the ontology as Turtle (a frozen version, or the working draft). */
export function exportOntology(version?: string): void {
  const url = version
    ? `/api/ontology/export?version=${encodeURIComponent(version)}`
    : '/api/ontology/export'
  const a = document.createElement('a')
  a.href = url
  a.download = version ? `ontology-${version}.ttl` : 'ontology.ttl'
  document.body.appendChild(a)
  a.click()
  a.remove()
}
