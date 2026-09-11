import type { Index, NetworkTree, Variable } from './types'

// ProMo unit vector order: [time, length, amount, mass, temperature, current, light, nil]

// Indices extracted from the ProMo13 ontology (var_equ_rdf.ttl).
export const demoIndices: Index[] = [
  { iri: 'promo:node', label: 'node', short_name: 'N', network: 'root', index_class: 'index', aliases: { internal_code: 'I_1' }, token: 'promo:I_1' },
  { iri: 'promo:arc', label: 'arc', short_name: 'A', network: 'root', index_class: 'index', aliases: { internal_code: 'I_2' }, token: 'promo:I_2' },
  { iri: 'promo:interface', label: 'interface', short_name: 'I', network: 'root', index_class: 'index', aliases: { internal_code: 'I_3' }, token: 'promo:I_3' },
  { iri: 'promo:species', label: 'species', short_name: 'S', network: 'root', index_class: 'index', aliases: { internal_code: 'I_4' }, token: 'promo:I_4' },
  { iri: 'promo:species_conversion', label: 'species_conversion', short_name: 'C', network: 'root', index_class: 'index', aliases: { internal_code: 'I_5' }, token: 'promo:I_5' },
  { iri: 'promo:D', label: 'D', short_name: 'D', network: 'root', index_class: 'index', aliases: { internal_code: 'I_6' }, token: 'promo:I_6' },
  { iri: 'promo:p', label: 'p', short_name: 'P', network: 'root', index_class: 'index', aliases: { internal_code: 'I_7' }, token: 'promo:I_7' },
  { iri: 'promo:q', label: 'q', short_name: 'Q', network: 'root', index_class: 'index', aliases: { internal_code: 'I_8' }, token: 'promo:I_8' },
  { iri: 'promo:r', label: 'r', short_name: 'R', network: 'root', index_class: 'index', aliases: { internal_code: 'I_9' }, token: 'promo:I_9' },
  { iri: 'promo:t', label: 't', short_name: 'T', network: 'root', index_class: 'index', aliases: { internal_code: 'I_10' }, token: 'promo:I_10' },
  { iri: 'promo:u', label: 'u', short_name: 'U', network: 'root', index_class: 'index', aliases: { internal_code: 'I_11' }, token: 'promo:I_11' },
]

// Variables kept for reference; the editor starts with an empty set.
export const demoVariables: Variable[] = []

export const demoNetworkTree: NetworkTree = {
  root: ['physical', 'control', 'info_processing'],
  physical: ['macroscopic', 'microscopic', 'reactions'],
  macroscopic: ['solid', 'fluid', 'energy'],
  fluid: ['liquid', 'gas'],
}
