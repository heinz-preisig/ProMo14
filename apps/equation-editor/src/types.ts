export interface EquationRecord {
  iri: string
  internal_id?: string | null
  lhs: string
  rhs: string
  rhs_latex?: string | null
  equation_class?: string | null
  network?: string | null
  incidence_list?: string[]
  doc?: string
  created?: string | null
  modified?: string | null
}

export interface Variable {
  iri: string
  label: string
  network: string
  type?: string
  units?: number[]
  index_structures?: string[]
  internal_id?: string | null
  aliases?: Record<string, string>
  doc?: string
  port_variable?: boolean
  tokens?: string[]
  /** Pre-bound promo:value — universal constants carry it permanently. */
  value?: string | null
  equations?: Record<string, EquationRecord>
  classifications?: Record<string, string>
  imported?: boolean
  created?: string | null
  modified?: string | null
}

export interface Index {
  iri: string
  label: string
  short_name?: string
  network?: string
  index_class?: string
  aliases?: Record<string, string>
  token?: string | null
  /** IRI of the base index this is a subset of (§16 sub-index). */
  sub_index_of?: string | null
  /** IRI of the entity type/term selecting membership (§16). */
  selector?: string | null
}

export interface NetworkTree {
  [parent: string]: string[]
}

export interface ContextResponse {
  variables: Variable[]
  indices: Index[]
  network_tree: NetworkTree
}

export interface CheckRequest {
  text: string
  variables: Variable[]
  indices: Index[]
  variable_definition_network: string
  expression_definition_network: string
  lhs?: string | null
  network_tree: NetworkTree
}

export interface CheckResponse {
  ok: boolean
  units?: number[] | null
  units_pretty?: string | null
  indices?: string[] | null
  incidence?: string[] | null
  label?: string | null
  error?: string | null
  error_kind?: string | null
  candidates?: Array<Record<string, unknown>> | null
}

export type CodegenTarget = 'python' | 'matlab' | 'latex'

export interface GenerateRequest extends CheckRequest {
  target: CodegenTarget
}

export interface GenerateResponse {
  ok: boolean
  code?: string | null
  error?: string | null
  error_kind?: string | null
  candidates?: Array<Record<string, unknown>> | null
}

export interface ParseRequest {
  text: string
}

export interface ParseResponse {
  ok: boolean
  ast?: AstNode | null
  error?: string | null
}

export type AstNode =
  | { type: 'Var'; name: string }
  | { type: 'Group'; body: AstNode }
  | { type: 'Add'; op: '+' | '-'; left: AstNode; right: AstNode }
  | { type: 'Expand'; left: AstNode; right: AstNode }
  | { type: 'Hadamard'; left: AstNode; right: AstNode }
  | { type: 'Reduce'; left: AstNode; right: AstNode; index?: AstNode | null }
  | { type: 'Power'; base: AstNode; exponent: AstNode }
  | { type: 'Instantiate'; var: AstNode }
  | { type: 'Integral'; body: AstNode; var: AstNode; lower: AstNode; upper: AstNode }
  | { type: 'Product'; body: AstNode; index: AstNode }
  | { type: 'Root'; body: AstNode }
  | { type: 'MaxMin'; which: 'max' | 'min'; a: AstNode; b: AstNode }
  | { type: 'TotalDiff'; x: AstNode; y: AstNode }
  | { type: 'ParDiff'; x: AstNode; y: AstNode }
  | { type: 'ReduceSum'; body: AstNode; index: AstNode }
  | { type: 'UFunc'; name: string; arg: AstNode }
  | { type: 'Call'; name: AstNode; args: AstNode[] }
  | { type: string; [key: string]: unknown }

/** A checked equation kept in the session list and attached to a
 *  variable record on save. */
export interface SavedEquation {
  id: string
  lhs: string
  text: string
  ast: AstNode | null
  check: CheckResponse | null
}
