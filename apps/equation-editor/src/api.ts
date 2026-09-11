import type { AstNode, CheckRequest, CheckResponse, ContextResponse, ParseRequest, ParseResponse } from './types'

export async function parseExpression(text: string): Promise<ParseResponse> {
  const res = await fetch('/api/equation/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text } satisfies ParseRequest),
  })
  return res.json() as Promise<ParseResponse>
}

export async function checkExpression(req: CheckRequest): Promise<CheckResponse> {
  const res = await fetch('/api/equation/check', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  return res.json() as Promise<CheckResponse>
}

export async function loadContext(): Promise<ContextResponse> {
  const res = await fetch('/api/equation/context')
  return res.json() as Promise<ContextResponse>
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
      return `Instantiate( ${nodeToString(node.var as AstNode)} , ${nodeToString(node.value as AstNode)} )`
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
