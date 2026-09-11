import { renderToString } from 'katex'
import type { AstNode, Index, Variable } from './types'

export interface LatexContext {
  variables?: Variable[]
  indices?: Index[]
  expressionNetwork?: string
}

function needsBraces(node: AstNode): boolean {
  return node.type === 'Add' || node.type === 'Expand' || node.type === 'Hadamard' ||
         node.type === 'Reduce' || node.type === 'Power'
}

function wrap(node: AstNode, ctx?: LatexContext, force = false): string {
  const inner = astToLatex(node, ctx)
  if (force || needsBraces(node)) {
    return `\\left( ${inner} \\right)`
  }
  return inner
}

function resolveVariable(name: string, ctx?: LatexContext): Variable | undefined {
  const vars = ctx?.variables ?? []
  const net = ctx?.expressionNetwork ?? ''
  if (name.includes('!')) {
    const [vn, vl] = name.split('!')
    return vars.find((v) => v.network === vn && v.label === vl)
  }
  const inScope = vars.filter((v) => v.label === name)
  if (inScope.length === 0) return undefined
  if (inScope.length === 1) return inScope[0]
  return inScope.find((v) => v.network === net) ?? inScope[0]
}

export function singleLetterLabel(label: string): string {
  if (!label) return ''
  return label.charAt(0).toUpperCase()
}

export function indexShortLabel(idx: Index | undefined): string {
  if (!idx) return ''
  return idx.short_name?.trim() || singleLetterLabel(idx.label)
}

function indexSubscripts(indexIris: string[], ctx?: LatexContext): string {
  const idxs = ctx?.indices ?? []
  const parts = indexIris.map((iri) => {
    const idx = idxs.find((i) => i.iri === iri)
    return idx
      ? (indexShortLabel(idx) || idx.aliases?.internal_code || iri)
      : iri
  })
  return `_{${parts.map((p) => `\\mathrm{${p}}`).join(',')}}`
}

export function astToLatex(node: AstNode, ctx?: LatexContext): string {
  if (!node) return ''
  switch (node.type) {
    case 'Var': {
      const name = String(node.name)
      const base = name.replace(/!/g, '\\!')
      const v = resolveVariable(name, ctx)
      if (v?.index_structures && v.index_structures.length > 0) {
        return `${base}${indexSubscripts(v.index_structures, ctx)}`
      }
      return base
    }
    case 'Group':
      return `\\left( ${astToLatex(node.body as AstNode, ctx)} \\right)`
    case 'Add':
      return `${wrap(node.left as AstNode, ctx)} ${node.op} ${wrap(node.right as AstNode, ctx)}`
    case 'Expand':
      return `${wrap(node.left as AstNode, ctx)} \\times ${wrap(node.right as AstNode, ctx)}`
    case 'Hadamard':
      return `${wrap(node.left as AstNode, ctx)} \\circ ${wrap(node.right as AstNode, ctx)}`
    case 'Reduce': {
      const left = wrap(node.left as AstNode, ctx)
      const right = wrap(node.right as AstNode, ctx)
      if (node.index) {
        return `${left} \\cdot_{${astToLatex(node.index as AstNode, ctx)}} ${right}`
      }
      return `${left} \\cdot ${right}`
    }
    case 'Power':
      return `${wrap(node.base as AstNode, ctx, true)}^{${astToLatex(node.exponent as AstNode, ctx)}}`
    case 'Instantiate':
      return `${astToLatex(node.var as AstNode, ctx)} := ${astToLatex(node.value as AstNode, ctx)}`
    case 'Integral':
      return `\\int_{${astToLatex(node.lower as AstNode, ctx)}}^{${astToLatex(node.upper as AstNode, ctx)}} ${astToLatex(node.body as AstNode, ctx)} \\, d${astToLatex(node.var as AstNode, ctx)}`
    case 'Product':
      return `\\prod_{${astToLatex(node.index as AstNode, ctx)}} ${wrap(node.body as AstNode, ctx)}`
    case 'Root':
      return `\\text{Root}\\left(${astToLatex(node.body as AstNode, ctx)}\\right)`
    case 'MaxMin':
      return `\\${node.which}\\left(${[node.a, node.b].map((n) => astToLatex(n as AstNode, ctx)).join(', ')}\\right)`
    case 'TotalDiff':
      return `\\frac{d ${astToLatex(node.x as AstNode, ctx)}}{d ${astToLatex(node.y as AstNode, ctx)}}`
    case 'ParDiff':
      return `\\frac{\\partial ${astToLatex(node.x as AstNode, ctx)}}{\\partial ${astToLatex(node.y as AstNode, ctx)}}`
    case 'ReduceSum':
      return `\\sum_{${astToLatex(node.index as AstNode, ctx)}} ${wrap(node.body as AstNode, ctx)}`
    case 'UFunc': {
      const name = String(node.name)
      if (['sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'exp', 'log', 'ln', 'sqrt', 'abs'].includes(name)) {
        return `\\${name}\\left( ${astToLatex(node.arg as AstNode, ctx)} \\right)`
      }
      if (name === 'neg') {
        return `- ${wrap(node.arg as AstNode, ctx)}`
      }
      if (name === 'inv') {
        return `${wrap(node.arg as AstNode, ctx, true)}^{-1}`
      }
      if (name === 'sign') {
        return `\\text{sign}\\left( ${astToLatex(node.arg as AstNode, ctx)} \\right)`
      }
      return `\\text{${name}}\\left( ${astToLatex(node.arg as AstNode, ctx)} \\right)`
    }
    case 'Call':
      return `\\text{${astToLatex(node.name as AstNode, ctx)}}\\left( ${(node.args as AstNode[]).map((n) => astToLatex(n as AstNode, ctx)).join(', ')} \\right)`
    default:
      return `\\text{${JSON.stringify(node).slice(0, 80)}}`
  }
}

export function renderLatex(latex: string, displayMode = true): string {
  try {
    return renderToString(latex, { throwOnError: true, displayMode })
  } catch (e) {
    const err = e instanceof Error ? e.message : String(e)
    return renderToString(`\\text{LaTeX error: } ${err.replace(/[{}]/g, '')}`, {
      throwOnError: false,
      displayMode,
    })
  }
}
