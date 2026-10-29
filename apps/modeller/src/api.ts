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

/** Load any artefact's model document by graph IRI (§22 referenced
 *  composites — interface reads go through this, not the session's
 *  own artefact). */
export async function loadModelDoc(iri: string): Promise<ModelDocument> {
  return getJson<ModelDocument>(
    `/api/modeller/model?graph=${encodeURIComponent(iri)}`)
}

// --- §22 referenced composites -------------------------------------

export interface CatalogueLine {
  iri: string
  type: string
  label: string
  status: string
  referencedBy: string[]
}

/** Artefact lines for the library pick (model artefacts only are
 *  usable as referenced composites). */
export async function fetchCatalogueLines(): Promise<CatalogueLine[]> {
  const res = await fetch('/api/catalogue')
  if (!res.ok) return []
  const body = await res.json()
  return (body.lines ?? []) as CatalogueLine[]
}

/** §22 extract-to-submodel: move the selected subtree roots into a
 *  new model artefact; the host gets a referenced composite. */
export async function extractSubmodel(
  iri: string,
  treeNodeIds: number[],
  label?: string,
): Promise<{ iri: string; compositeTreeId: number }> {
  const res = await apiFetch('/api/modeller/extract-submodel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ iri, treeNodeIds, label }),
  })
  if (!res.ok) throw new Error(`extract failed: ${res.status}`)
  return res.json()
}

/** §22 dissolve: flatten a referenced composite to inline content. */
export async function dissolveComposite(
  treeNodeId: number,
): Promise<{ dissolved: string; compositeTreeId: number }> {
  const res = await apiFetch('/api/modeller/dissolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ treeNodeId }),
  })
  if (!res.ok) throw new Error(`dissolve failed: ${res.status}`)
  return res.json()
}

export async function saveModel(doc: ModelDocument): Promise<void> {
  const res = await apiFetch('/api/modeller/model', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(doc),
  })
  if (!res.ok) throw new Error(`Failed to save model: ${res.status}`)
}

export async function fetchBehaviourEntityTypes(): Promise<Set<string>> {
  const iris = await getJson<string[]>('/api/modeller/behaviour-entity-types')
  return new Set(iris)
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

/** ADR-008 layer 2: the variables an entity type's assignment mentions
 *  — the candidate set for promo:fix marks on a model node. */
export interface EntityVariable {
  var: string
  label: string
  role: string   // state|port|instantiated|defined|input
}

export async function fetchEntityVariables(
  entityType: string,
): Promise<EntityVariable[]> {
  if (!entityType) return []
  const path = withParams('/api/instantiate/entity-variables',
                          { entity_type: entityType })
  const res = await fetch(path)
  if (!res.ok) return []
  return res.json()
}

// --- §13/§14 connect-time port satisfaction -----------------------------

export interface PortDemand {
  var: string
  label: string
  tokens: string[]
  /** satisfied|ambiguous|unbound|unlicensed */
  status: string
  candidates: string[]
  state_hidden: boolean
}

export interface PortSide {
  entity_type: string
  has_assignment: boolean
  ports: PortDemand[]
  unsatisfied: string[]
}

export interface PortSatisfaction {
  source: PortSide
  target: PortSide
  carrier: string | null
  matched_tokens: string[] | null
}

/** Adjudicate a proposed source↔target connection: which BL port
 *  demands on each side an arc of ``arcType`` (optional) would feed.
 *  Advisory — the gesture stays permissive. */
export async function fetchPortSatisfaction(
  source: string,
  target: string,
  arcType?: string,
): Promise<PortSatisfaction | null> {
  const path = withParams('/api/modeller/port-satisfaction', {
    source, target, ...(arcType ? { arc_type: arcType } : {}),
  })
  const res = await fetch(path)
  if (!res.ok) return null
  return res.json()
}
