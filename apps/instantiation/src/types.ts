/** Types mirroring backend/instantiate/service.py models. */

export interface VarBinding {
  var: string
  role: string
  binding: string
  instance: string
  indices: Record<string, string[]>
  matrix: string | null
  value: string | null
}

export interface EqBinding {
  equation: string
  lhs: string
  inputs: string[]
}

export interface EntityInstantiation {
  entity_type: string
  nodes: string[]
  has_assignment: boolean
  closed: boolean
  state_variable: string | null
  variables: VarBinding[]
  equations: EqBinding[]
}

export interface PortBinding {
  node: string
  var: string
  status: string
  arc: string | null
  peer_node: string | null
  peer_var: string | null
  element: string | null
  candidates: string[][]
}

export interface Problem {
  kind: string
  message: string
  node: string | null
  entity_type: string | null
}

export interface SchedBlock {
  entity_type: string
  equation: string
  lhs: string
  loop: number
}

export interface Schedule {
  levels: SchedBlock[][]
  loops: string[][]
}

export interface IncidenceMatrix {
  index: string
  nodes: string[]
  arcs: string[]
  entries: [number, number, number][]
}

export interface IncidenceReport {
  base: IncidenceMatrix
  sub_indices: IncidenceMatrix[]
}

/** GET /api/instantiate/model response. */
export interface InstantiationReport {
  model: string
  vars_graph: string | null
  indices: Record<string, string[]>
  entity_types: EntityInstantiation[]
  ports: PortBinding[]
  incidence: IncidenceReport
  schedule: Schedule
  problems: Problem[]
  labels: Record<string, string>
}

/** GET /api/instantiate/code response. */
export interface CodeOut {
  ok: boolean
  target: string
  source: string
  error: string | null
  problems: string[]
}
