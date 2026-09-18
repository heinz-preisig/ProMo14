import type {
  CatalogueFetchers,
  ConnectionRuleRecord,
  DomainRecord,
  EntityTypeRecord,
  TokenRecord,
} from '@promo/semantic'
import type { ModelDocument } from './modelPersistence'

/** The artefact graph this session edits — from the hub's ?graph= link.
 *  Undefined means the default working ontology. */
export const GRAPH_IRI =
  new URLSearchParams(window.location.search).get('graph') || undefined

/** Append the session's graph param to an API path. */
export function q(path: string): string {
  if (!GRAPH_IRI) return path
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}graph=${encodeURIComponent(GRAPH_IRI)}`
}

export function apiFetch(path: string, init?: RequestInit) {
  return fetch(q(path), init)
}

async function getJson<T>(path: string): Promise<T> {
  const res = await apiFetch(path)
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json() as Promise<T>
}

/** Fetchers for ``RemoteCatalogue.load`` — ontology-backed entity types,
 *  domains, tokens and connection rules for the current graph scope. */
export const catalogueFetchers: CatalogueFetchers = {
  entityTypes: () => getJson<EntityTypeRecord[]>('/api/ontology/entity-types'),
  domains: () => getJson<DomainRecord[]>('/api/ontology/domains'),
  tokens: () => getJson<TokenRecord[]>('/api/ontology/tokens'),
  connectionRules: () => getJson<ConnectionRuleRecord[]>('/api/ontology/connection-rules'),
}

// --- Model persistence (ADR-007: the artefact graph is one model document) ---

export async function loadModel(): Promise<ModelDocument> {
  return getJson<ModelDocument>('/api/modeller/model')
}

export async function saveModel(doc: ModelDocument): Promise<void> {
  const res = await apiFetch('/api/modeller/model', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(doc),
  })
  if (!res.ok) throw new Error(`Failed to save model: ${res.status}`)
}

/** Persist the RDF store to its TriG file (clears the dirty flag). */
export async function saveOntology(): Promise<void> {
  const res = await apiFetch('/api/ontology/save', { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to save ontology: ${res.status}`)
}
