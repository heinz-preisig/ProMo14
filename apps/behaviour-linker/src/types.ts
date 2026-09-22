/** Types mirroring backend/behaviour/service.py models. */

export interface EntityType {
  iri: string
  label: string
  branch: string
  scale_values: string[]
}

export interface Equation {
  iri: string
  internal_id: string | null
  lhs: string
  lhs_latex: string | null
  rhs: string
  rhs_latex: string | null
  equation_class: string | null
  network: string | null
  incidence: string[]
}

export interface Variable {
  iri: string
  label: string
  network: string
  variable_class: string
  port_variable: boolean
  tokens: string[]
}

export interface BehaviourContext {
  entity_types: EntityType[]
  equations: Equation[]
  variables: Variable[]
}

/** The user's current assignment state for one entity type. */
export interface Selection {
  entity_type: string
  sequence: string[]
  base_equation: string | null
  instantiated: string[]
  ports: string[]
}

export interface UnresolvedVar {
  variable: string
  candidates: string[]
}

export interface Conflict {
  kind: string
  variable: string | null
  equation: string | null
  detail: string
}

export interface OrderViolation {
  equation: string
  variable: string
  defined_by: string
  detail: string
}

/** POST /evaluate response — the closure report plus a label map. */
export interface EvaluateReport {
  state_variable: string | null
  defined: Record<string, string>
  unresolved: UnresolvedVar[]
  cycles: string[][]
  conflicts: Conflict[]
  order_violations: OrderViolation[]
  warnings: string[]
  closed: boolean
  labels: Record<string, string>
}

export interface Assignment {
  entity_type: string
  sequence: string[]
  base_equation: string | null
  state_variable: string | null
  instantiated: string[]
  ports: string[]
  closed: boolean
}
