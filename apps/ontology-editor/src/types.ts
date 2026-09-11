export interface NetworkRecord {
  iri: string
  name: string
  parent: string | null
  children: string[]
}

export interface VariableRecord {
  iri: string
  label: string
  network: string
  variable_class: string
  units: number[]
  index_structures: string[]
  internal_id: string
  aliases: Record<string, string>
  doc: string
  port_variable: boolean
  tokens: string[]
}

export interface IndexRecord {
  iri: string
  label: string
  short_name: string
  network: string
  index_class: string
  internal_id: string | null
  aliases: Record<string, string>
  token: string | null
}

export interface TokenRecord {
  iri: string
  label: string
  parent: string | null
}

export interface EquationRecord {
  iri: string
  label: string
  network: string
  tokens: string[]
}

export interface OntologyContext {
  variables: VariableRecord[]
  indices: IndexRecord[]
  network_tree: Record<string, string[]>
}
