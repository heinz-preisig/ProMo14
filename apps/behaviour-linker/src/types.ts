/** Types mirroring backend/behaviour/service.py models. */

export interface EntityType {
  iri: string
  label: string
  branch: string
  parent: string | null
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
  lhs_class: string
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
  /** Declared outputs — external sinks; their definers are
   *  reachability roots alongside the base equation (§21). */
  outputs: string[]
}

/** A §21 move — the only mutation channel (POST /move). */
export interface Move extends Selection {
  kind: 'pick_base' | 'pick' | 'delete' | 'mark' | 'unmark' | 'reorder'
  variable?: string | null
  equation?: string | null
  role?: 'instantiated' | 'ports' | 'outputs' | null
}

export interface UnresolvedVar {
  variable: string
  candidates: string[]
  /** True when the variable is unresolved because an output mark
   *  demands a definer (§21 output endpoint). */
  as_output: boolean
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
  /** Bound-value variables (constant/parameter class or promo:value)
   *  referenced by the selection — implicit instantiation endpoints.
   *  Candidates are still listed so the hint can be overridden. */
  auto_instantiated: UnresolvedVar[]
  /** Equations that resolve a currently unresolved variable and are
   *  reachable from the selected base cone. */
  frontier: string[]
  cycles: string[][]
  conflicts: Conflict[]
  order_violations: OrderViolation[]
  warnings: string[]
  closed: boolean
  /** Resolved output marks (echo of the selection). */
  outputs: string[]
  /** Defined, non-state variables nothing consumes and no output
   *  claims — dead code / pending output marks (§21). */
  unconsumed: string[]
  labels: Record<string, string>
}

/** POST /move response — the re-closed selection + fresh report. */
export interface MoveResult {
  selection: Assignment
  report: EvaluateReport
  /** Equations the move pulled in (unique-candidate definers). */
  pulled: string[]
  /** Equations the move pruned (dead cones). */
  pruned: string[]
}

export interface Assignment {
  entity_type: string
  sequence: string[]
  base_equation: string | null
  state_variable: string | null
  instantiated: string[]
  ports: string[]
  outputs: string[]
  closed: boolean
}
