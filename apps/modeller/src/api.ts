import type {
  CatalogueFetchers,
  ConnectionRuleRecord,
  DomainRecord,
  EntityTypeRecord,
  TokenRecord,
} from '@promo/semantic'
import type { ModelDocument } from './modelPersistence'
import { apiFetch, sessionParam, withParams } from '@promo/ui'

export {
  GRAPH_IRI,
  apiFetch,
  withParams as q,
  saveStore as saveOntology,
} from '@promo/ui'

/** The species artefact override — the ``?species=`` param (§20).
 *  When absent the model's promo:usesSpecies pin supplies the IRI
 *  (resolved in App after loadModel).  Undefined = no override. */
export const SPECIES_IRI = sessionParam('species')

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

// --- §20 species artefact (vocabulary for the capability-gated gestures) ---

export interface SpeciesComponent {
  iri: string
  label: string
}
export interface SpeciesAllocation {
  iri: string
  label: string
  members: string[]
}
export interface SpeciesReaction {
  iri: string
  label: string
  reactants: string[]
  products: string[]
}
export interface SpeciesDocument {
  components: SpeciesComponent[]
  allocations: SpeciesAllocation[]
  reactions: SpeciesReaction[]
}

/** Load a species artefact (its own graph — not the model's). */
export async function fetchSpecies(
    iri: string | undefined,
): Promise<SpeciesDocument | null> {
  if (!iri) return null
  const res = await fetch(
    `/api/species/species?graph=${encodeURIComponent(iri)}`)
  if (!res.ok) return null
  return res.json()
}

/** §20 readout: species present per node / carried per arc, and the
 *  active reaction set per node (the Q index's elements). */
export interface SpeciesDistribution {
  species: string | null
  nodes: Record<string, string[]>
  arcs: Record<string, string[]>
  reactions: Record<string, string[]>
}

/** Live species distribution for the model — ?species= overrides the
 *  model's usesSpecies pin server-side. */
export async function fetchSpeciesDistribution(
  speciesIri: string | undefined,
): Promise<SpeciesDistribution | null> {
  const path = withParams('/api/instantiate/species-distribution',
                          { species: speciesIri })
  const res = await fetch(path)
  if (!res.ok) return null
  return res.json()
}

/** Entity types with their §20 capability fragments — for gating the
 *  species gestures (species_source / reaction_host / species_transport). */
export async function fetchEntityCapabilities(): Promise<Map<string, string[]>> {
  const ets = await getJson<EntityTypeRecord[]>('/api/ontology/entity-types')
  return new Map(ets.map((e) => [e.iri, e.capabilities ?? []]))
}
