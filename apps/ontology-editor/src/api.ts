import type {
  EquationRecord,
  IndexRecord,
  NetworkRecord,
  OntologyContext,
  TokenRecord,
  VariableRecord,
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

export async function listVariables(): Promise<VariableRecord[]> {
  const res = await fetch('/api/ontology/variables')
  if (!res.ok) throw new Error(`Failed to load variables: ${res.status}`)
  return res.json()
}

export async function createVariable(record: VariableRecord): Promise<VariableRecord> {
  const res = await fetch('/api/ontology/variables', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to create variable: ${res.status}`)
  return res.json()
}

export async function updateVariable(
  iri: string,
  record: VariableRecord
): Promise<VariableRecord> {
  const res = await fetch(`/api/ontology/variables/${encodeURIComponent(iri)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(record),
  })
  if (!res.ok) throw new Error(`Failed to update variable: ${res.status}`)
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

export async function listTokens(): Promise<TokenRecord[]> {
  const res = await fetch('/api/ontology/tokens')
  if (!res.ok) throw new Error(`Failed to load tokens: ${res.status}`)
  return res.json()
}

export async function listEquations(): Promise<EquationRecord[]> {
  const res = await fetch('/api/ontology/equations')
  if (!res.ok) throw new Error(`Failed to load equations: ${res.status}`)
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
