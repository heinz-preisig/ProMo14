/** Types mirroring backend/instantiate/service.py models. */

export interface VarBinding {
  var: string
  role: string
  binding: string
  instance: string
  /** index IRI → bound element set (null: unbound/symbolic extent). */
  indices: Record<string, string[] | null>
  matrix: string | null
  value: string | null
  /** §20 value-cell table: "|"-joined element-IRI keys → scalar. */
  values: Record<string, number>
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
  initial_equations: EqBinding[]
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

/** One t=0 requirement — an ``ic`` on a differentiated/accumulated
 *  state or a ``guess`` for a SolveRoot lhs.  ``status`` stays
 *  ``needed`` until ``supplied_by`` names coverage (``initialise``
 *  equation or value ``cells``). */
export interface IcNeed {
  var: string
  entity_type: string
  kind: string
  equation: string
  instance: string
  supplied_by: string | null
  status: string
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
  ic_needs: IcNeed[]
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

/** GET/PUT /api/instantiate/values response. */
export interface ValueCellsOut {
  variable: string
  values: Record<string, number>
}

/** POST /api/instantiate/initial response — the in-service t=0
 *  solve: flat ``y0`` plus per-state slices, ``par_needed`` echoing
 *  the parameter keys the emitted module reads. */
export interface InitialOut {
  ok: boolean
  y0: number[]
  states: {
    name: string
    var: string
    entity_type: string
    values: number[]
  }[]
  par_needed: string[]
  steady_state: boolean
  error: string | null
  problems: string[]
}
