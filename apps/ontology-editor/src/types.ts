// ---------------------------------------------------------------------------
// Domain tree (two-branch: physical / information)
// ---------------------------------------------------------------------------

export interface NetworkRecord {
  iri: string
  name: string
  parent: string | null
  children: string[]
}

export interface DomainRecord {
  iri: string
  name: string
  label: string | null
  parent: string | null
  branch: string | null // "physical" or "information" (top-level only)
  children: string[]
  tokens: string[] // token IRIs explicitly assigned to this domain
  inherited_tokens: string[] // token IRIs inherited from ancestors (read-only)
}

// ---------------------------------------------------------------------------
// Classification axes (multi-axis, per-domain, hierarchical)
// ---------------------------------------------------------------------------

export interface AxisTermRecord {
  iri: string
  axis: string // axis IRI
  label: string
  parent: string | null
}

export interface ClassificationAxisRecord {
  iri: string
  domain: string // domain IRI where this axis is defined
  name: string // e.g. "role", "extensivity", "origin"
  parent: string | null // inherited from parent domain
  terms: AxisTermRecord[] // terms in this axis hierarchy
}

// ---------------------------------------------------------------------------
// Variables and equations (aligned with docs/ontology-data-model.md)
// ---------------------------------------------------------------------------

export interface EquationRecord {
  iri: string
  internal_id: string | null // E_N code name
  lhs: string // variable IRI being defined
  rhs: string // token stream (global_ID form)
  rhs_latex: string // generated LaTeX, cached
  equation_class: string // IRI of EquationClass node (hierarchical)
  network: string // expression definition network
  incidence_list: string[] // derived, cached
  doc: string
  created: string | null
  modified: string | null
}

export interface VariableRecord {
  // Identity & naming (three-name pattern)
  iri: string
  label: string
  internal_id: string | null
  aliases: Record<string, string>
  // extensible: internal_code, latex, matlab, python, modelica, ...

  // Domain / location
  network: string
  classifications: Record<string, string> // axis IRI -> axis term IRI
  variable_class: string | null // legacy, kept for backward compat
  port_variable: boolean
  imported: boolean

  // Semantics
  doc: string
  units: number[]
  tokens: string[]

  // Index structure
  index_structures: string[]

  // Equations (nested, one per expression network)
  equations: Record<string, EquationRecord>

  // Codegen metadata
  compiled_lhs: Record<string, unknown> | null
  memory: Record<string, unknown> | null

  // Audit
  created: string | null
  modified: string | null
}

// ---------------------------------------------------------------------------
// Indices
// ---------------------------------------------------------------------------

export interface IndexRecord {
  iri: string
  label: string
  short_name: string | null
  network: string
  index_class: string
  internal_id: string | null
  aliases: Record<string, string>
  token: string | null
}

// ---------------------------------------------------------------------------
// Tokens
// ---------------------------------------------------------------------------

export interface TokenRecord {
  iri: string
  label: string
  parent: string | null
}

// ---------------------------------------------------------------------------
// Scales (first-class concept: time scale, length scale, user-defined)
// ---------------------------------------------------------------------------

export interface ScaleValueRecord {
  iri: string
  dimension: string // scale dimension IRI
  label: string // e.g. "microscopic", "macroscopic"
  parent: string | null // hierarchical (tree)
}

export interface ScaleDimensionRecord {
  iri: string
  name: string // e.g. "time", "length"
  domain: string // domain IRI where this scale is defined
  parent: string | null // inherited from parent domain
  values: ScaleValueRecord[]
}

// ---------------------------------------------------------------------------
// Entity types (CWA 17960 — seed/default, not hardcoded schema)
// ---------------------------------------------------------------------------

export interface EntityTypeRecord {
  iri: string
  label: string
  temporal_type: string // "constant" | "dynamic" | "event-dynamic"
  spatial_type: string | null // "uniform" | "distributed" (physical only)
  spatial_size: string | null // "infinite" | "finite" | "infinitesimal"
  branch: string // "physical" | "information"
  scale_values: string[] // scale value IRIs
  description: string
}

// ---------------------------------------------------------------------------
// Connection rules
// ---------------------------------------------------------------------------

export interface ConnectionRuleRecord {
  iri: string
  rule_type: string // "physical-same" | "physical-cross" | "signal"
  source_domain: string | null
  target_domain: string | null
  shared_tokens: string[]
  direction: string | null // "bidirectional" | "unidirectional"
  description: string
}

// ---------------------------------------------------------------------------
// Ontology context (API response)
// ---------------------------------------------------------------------------

export interface OntologyContext {
  variables: VariableRecord[]
  indices: IndexRecord[]
  network_tree: Record<string, string[]>
  domains: DomainRecord[]
  axes: ClassificationAxisRecord[]
  scale_dimensions: ScaleDimensionRecord[]
  entity_types: EntityTypeRecord[]
  connection_rules: ConnectionRuleRecord[]
}
