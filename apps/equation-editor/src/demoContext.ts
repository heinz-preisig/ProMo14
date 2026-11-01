import type { Index, NetworkTree, Variable } from './types'

// ProMo unit vector order: [time, length, amount, mass, temperature, current, light, nil]

// Indices extracted from the ProMo13 ontology (var_equ_rdf.ttl).
export const demoIndices: Index[] = [
  { iri: 'https://w3id.org/promo/ontology#node', label: 'node', short_name: 'N', network: 'root', index_class: 'index', aliases: { internal_code: 'I_1' }, token: 'https://w3id.org/promo/ontology#I_1' },
  { iri: 'https://w3id.org/promo/ontology#arc', label: 'arc', short_name: 'A', network: 'root', index_class: 'index', aliases: { internal_code: 'I_2' }, token: 'https://w3id.org/promo/ontology#I_2' },
  { iri: 'https://w3id.org/promo/ontology#interface', label: 'interface', short_name: 'I', network: 'root', index_class: 'index', aliases: { internal_code: 'I_3' }, token: 'https://w3id.org/promo/ontology#I_3' },
  { iri: 'https://w3id.org/promo/ontology#species', label: 'species', short_name: 'S', network: 'root', index_class: 'index', aliases: { internal_code: 'I_4' }, token: 'https://w3id.org/promo/ontology#I_4' },
  { iri: 'https://w3id.org/promo/ontology#species_conversion', label: 'species_conversion', short_name: 'C', network: 'root', index_class: 'index', aliases: { internal_code: 'I_5' }, token: 'https://w3id.org/promo/ontology#I_5' },
  { iri: 'https://w3id.org/promo/ontology#D', label: 'D', short_name: 'D', network: 'root', index_class: 'index', aliases: { internal_code: 'I_6' }, token: 'https://w3id.org/promo/ontology#I_6' },
  { iri: 'https://w3id.org/promo/ontology#p', label: 'p', short_name: 'P', network: 'root', index_class: 'index', aliases: { internal_code: 'I_7' }, token: 'https://w3id.org/promo/ontology#I_7' },
  { iri: 'https://w3id.org/promo/ontology#q', label: 'q', short_name: 'Q', network: 'root', index_class: 'index', aliases: { internal_code: 'I_8' }, token: 'https://w3id.org/promo/ontology#I_8' },
  { iri: 'https://w3id.org/promo/ontology#r', label: 'r', short_name: 'R', network: 'root', index_class: 'index', aliases: { internal_code: 'I_9' }, token: 'https://w3id.org/promo/ontology#I_9' },
  { iri: 'https://w3id.org/promo/ontology#t', label: 't', short_name: 'T', network: 'root', index_class: 'index', aliases: { internal_code: 'I_10' }, token: 'https://w3id.org/promo/ontology#I_10' },
  { iri: 'https://w3id.org/promo/ontology#u', label: 'u', short_name: 'U', network: 'root', index_class: 'index', aliases: { internal_code: 'I_11' }, token: 'https://w3id.org/promo/ontology#I_11' },
]

// Variables kept for reference; the editor starts with an empty set.
export const demoVariables: Variable[] = []

export const demoNetworkTree: NetworkTree = {
  root: ['physical', 'control', 'info_processing'],
  physical: ['macroscopic', 'microscopic', 'reactions'],
  macroscopic: ['solid', 'fluid', 'energy'],
  fluid: ['liquid', 'gas'],
}
