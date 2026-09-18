import type { AstNode, CheckRequest, CheckResponse, ContextResponse, GenerateRequest, GenerateResponse, ParseRequest, ParseResponse, Variable } from './types'
import type { SavedEquation } from './components/EquationList'

/** The artefact graph this session edits — from the hub's ?graph= link.
 *  Undefined means the default working ontology. */
export const GRAPH_IRI =
  new URLSearchParams(window.location.search).get('graph') || undefined

/** Append the session's graph param to an API path. */
function q(path: string): string {
  if (!GRAPH_IRI) return path
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}graph=${encodeURIComponent(GRAPH_IRI)}`
}

function apiFetch(path: string, init?: RequestInit) {
  return fetch(q(path), init)
}

export async function parseExpression(text: string): Promise<ParseResponse> {
  const res = await apiFetch('/api/equation/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text } satisfies ParseRequest),
  })
  return res.json() as Promise<ParseResponse>
}

export async function checkExpression(req: CheckRequest): Promise<CheckResponse> {
  const res = await apiFetch('/api/equation/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  return res.json() as Promise<CheckResponse>
}

export async function loadContext(): Promise<ContextResponse> {
  const res = await apiFetch('/api/equation/context')
  return res.json() as Promise<ContextResponse>
}

export async function saveVariable(v: Variable, equation?: SavedEquation): Promise<Variable> {
  const equations: Record<string, unknown> = {}
  if (equation) {
    const eqId = `E_${Date.now()}`
    equations[eqId] = {
      iri: '',
      internal_id: eqId,
      lhs: v.iri,
      rhs: equation.text,
      rhs_latex: null,
      equation_class: 'generic',
      network: v.network,
      incidence_list: equation.check?.incidence ?? [],
      doc: '',
      created: new Date().toISOString(),
      modified: new Date().toISOString(),
    }
  }
  const body = {
    iri: v.iri || '',
    label: v.label,
    internal_id: v.internal_id ?? null,
    aliases: v.aliases ?? {},
    network: v.network,
    classifications: {},
    variable_class: v.type ?? null,
    port_variable: v.port_variable ?? false,
    imported: false,
    doc: v.doc ?? '',
    units: v.units ?? [0, 0, 0, 0, 0, 0, 0, 0],
    tokens: v.tokens ?? [],
    index_structures: v.index_structures ?? [],
    equations,
    compiled_lhs: null,
    memory: null,
    created: null,
    modified: null,
  }
  const res = await apiFetch('/api/equation/variables', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`Failed to save variable: ${res.status}`)
  return res.json()
}

export async function generateExpression(req: GenerateRequest): Promise<GenerateResponse> {
  const res = await apiFetch('/api/equation/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`Failed to generate: ${res.status}`)
  return res.json()
}

/** URL of the printable LaTeX document (variables + equations) for the
 *  current graph scope — opened in a new tab for print/compile. */
export function documentUrl(): string {
  return q('/api/equation/document')
}

export async function deleteVariable(iri: string): Promise<void> {
  const res = await apiFetch(`/api/equation/variables/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(`Failed to delete variable: ${res.status}`)
}

export interface StoreStatus {
  dirty: boolean
  last_saved: string | null
}

export async function getStoreStatus(): Promise<StoreStatus> {
  const res = await apiFetch('/api/ontology/status')
  if (!res.ok) throw new Error(`Failed to load store status: ${res.status}`)
  return res.json()
}

/** Persist the whole dataset (ontology + artefact graphs) to ontology.trig. */
export async function saveOntology(filename = 'ontology.trig'): Promise<{ saved: string }> {
  const res = await apiFetch('/api/ontology/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename }),
  })
  if (!res.ok) throw new Error(`Failed to save: ${res.status}`)
  return res.json()
}

export function nodeToString(node: AstNode): string {
  switch (node.type) {
    case 'Var':
      return node.name as string
    case 'Group':
      return `( ${nodeToString(node.body as AstNode)} )`
    case 'Add':
      return `${nodeToString(node.left as AstNode)} ${node.op} ${nodeToString(node.right as AstNode)}`
    case 'Expand':
      return `${nodeToString(node.left as AstNode)} : ${nodeToString(node.right as AstNode)}`
    case 'Hadamard':
      return `${nodeToString(node.left as AstNode)} . ${nodeToString(node.right as AstNode)}`
    case 'Reduce':
      if (node.index) {
        return `${nodeToString(node.left as AstNode)} * ${nodeToString(node.index as AstNode)} ${nodeToString(node.right as AstNode)}`
      }
      return `${nodeToString(node.left as AstNode)} * ${nodeToString(node.right as AstNode)}`
    case 'Power':
      return `${nodeToString(node.base as AstNode)} ^ ${nodeToString(node.exponent as AstNode)}`
    case 'Instantiate':
      return `Instantiate( ${nodeToString(node.expr as AstNode)} , ${nodeToString(node.shape as AstNode)} )`
    case 'Integral':
      return `Integral( ${nodeToString(node.body as AstNode)} :: ${nodeToString(node.var as AstNode)} in [ ${nodeToString(node.lower as AstNode)} , ${nodeToString(node.upper as AstNode)} ] )`
    case 'Product':
      return `Product( ${nodeToString(node.body as AstNode)} , ${nodeToString(node.index as AstNode)} )`
    case 'Root':
      return `Root( ${nodeToString(node.body as AstNode)} )`
    case 'MaxMin':
      return `${node.which}( ${nodeToString(node.a as AstNode)} , ${nodeToString(node.b as AstNode)} )`
    case 'TotalDiff':
      return `TotalDiff( ${nodeToString(node.x as AstNode)} , ${nodeToString(node.y as AstNode)} )`
    case 'ParDiff':
      return `ParDiff( ${nodeToString(node.x as AstNode)} , ${nodeToString(node.y as AstNode)} )`
    case 'ReduceSum':
      return `reduceSum( ${nodeToString(node.body as AstNode)} , ${nodeToString(node.index as AstNode)} )`
    case 'UFunc':
      return `${node.name}( ${nodeToString(node.arg as AstNode)} )`
    case 'Call':
      return `${nodeToString(node.name as AstNode)}( ${(node.args as AstNode[]).map(nodeToString).join(', ')} )`
    default:
      return JSON.stringify(node)
  }
}
