import type { AstNode, CheckRequest, CheckResponse, ContextResponse, GenerateRequest, GenerateResponse, ParseRequest, ParseResponse, SavedEquation, Variable } from './types'
import { nextEquationId } from './variableUtils'
import { apiFetch, withParams } from '@promo/ui'

export {
  GRAPH_IRI,
  getStoreStatus,
  saveStore as saveOntology,
} from '@promo/ui'
export type { StoreStatus } from '@promo/ui'

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

export async function saveVariable(
  v: Variable,
  equation?: SavedEquation,
  allVariables: Variable[] = [],
): Promise<Variable> {
  // Re-save replaces the whole record — carry stored equations forward
  // or an edit would silently drop them.
  const equations: Record<string, unknown> = { ...(v.equations ?? {}) }
  if (equation) {
    // Sequential E_n (smallest free) — epoch-ms ids are unreadable in
    // the printed document.  Pool is the full variable set when given.
    const eqId = nextEquationId(allVariables.length ? allVariables : [v])
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
    classifications: v.classifications ?? {},
    variable_class: v.type ?? null,
    port_variable: v.port_variable ?? false,
    imported: v.imported ?? false,
    doc: v.doc ?? '',
    units: v.units ?? [0, 0, 0, 0, 0, 0, 0, 0],
    tokens: v.tokens ?? [],
    value: v.value ?? null,
    index_structures: v.index_structures ?? [],
    equations,
    compiled_lhs: null,
    memory: null,
    created: v.created ?? null,
    modified: v.modified ?? null,
  }
  const res = await apiFetch('/api/equation/variables', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw await apiError(res, `Failed to save variable: ${res.status}`)
  return res.json()
}

/** Build an Error from a failed response, surfacing FastAPI's ``detail``
 *  (string or the structured 409 payload from the mutability guard). */
async function apiError(res: Response, fallback: string): Promise<Error> {
  try {
    const body = await res.json()
    const d = body?.detail
    if (typeof d === 'string') return new Error(d)
    if (d && typeof d.message === 'string') {
      const refs = (d.references ?? [])
        .map((r: { via?: string; equation?: string }) => `  ${r.via}: ${r.equation}`)
        .join('\n')
      return new Error(refs ? `${d.message}\n${refs}` : d.message)
    }
  } catch { /* body not JSON — fall through */ }
  return new Error(fallback)
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
 *  current graph scope — opened in a new tab.  ``pdf`` compiles server-
 *  side and opens in the browser's PDF viewer; ``tex`` is the raw
 *  compilable source. */
export function documentUrl(format: 'pdf' | 'tex' = 'pdf'): string {
  return withParams(`/api/equation/document?format=${format}`)
}

export async function deleteVariable(iri: string): Promise<void> {
  const res = await apiFetch(`/api/equation/variables/${encodeURIComponent(iri)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw await apiError(res, `Failed to delete variable: ${res.status}`)
}

export interface VariableReferences {
  iri: string
  used: boolean
  references: { equation: string; graph: string; via: string }[]
}

/** Equations referencing a variable — drives the mutability lock (§18):
 *  structural fields are editable only while ``used`` is false. */
export async function getVariableReferences(iri: string): Promise<VariableReferences> {
  const res = await apiFetch(`/api/equation/variables/${encodeURIComponent(iri)}/references`)
  if (!res.ok) throw await apiError(res, `Failed to load references: ${res.status}`)
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
      return `Instantiate( ${nodeToString(node.var as AstNode)} )`
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
