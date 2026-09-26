import { renderToString } from 'katex'
import type { AstNode, Index, Variable } from './types'

export interface LatexContext {
  variables?: Variable[]
  indices?: Index[]
  expressionNetwork?: string
  /** Label of the variable being defined — the LHS of Instantiate. */
  lhs?: string
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

// Surface names (index codes, labels) are atomic names, not math — a raw
// '_' inside _{...} is a KaTeX/LaTeX double-subscript error.
const texEscape = (name: string): string => name.replace(/_/g, '\\_')

// Verbatim latex aliases often arrive in label form ("F_conv",
// "\\hat{m}_conv") where '_' is meant to subscript the whole tail — but
// a bare '_' consumes only ONE token, so "F_conv" renders F_c + "onv".
// Brace unbraced runs: "_conv" → "_{conv}"; "_{...}" and "\_" pass through.
const braceSubscripts = (alias: string): string =>
  alias.replace(/(?<!\\)_([A-Za-z0-9]+)/g, '_{$1}')

function indexSubscripts(indexIris: string[], ctx?: LatexContext): string {
  const idxs = ctx?.indices ?? []
  const parts = indexIris.map((iri) => {
    const idx = idxs.find((i) => i.iri === iri)
    return idx
      ? (indexShortLabel(idx) || idx.aliases?.internal_code || iri)
      : iri
  })
  return `_{${parts.map((p) => `\\mathrm{${texEscape(p)}}`).join(',')}}`
}

function appendIndexSubscripts(base: string, indexIris: string[], ctx?: LatexContext): string {
  const generated = indexSubscripts(indexIris, ctx)
  while (base.startsWith('{') && base.endsWith('}')) {
    let depth = 0
    let enclosesAll = true
    for (let pos = 0; pos < base.length; pos += 1) {
      if (base[pos] === '{') depth += 1
      else if (base[pos] === '}') {
        depth -= 1
        if (depth === 0 && pos !== base.length - 1) {
          enclosesAll = false
          break
        }
      }
    }
    if (!enclosesAll || depth !== 0) break
    base = base.slice(1, -1)
  }
  if (!base.endsWith('}')) return `{${base}}${generated}`
  let depth = 0
  for (let pos = base.length - 1; pos >= 0; pos -= 1) {
    if (base[pos] === '}') depth += 1
    else if (base[pos] === '{') {
      depth -= 1
      if (depth === 0) {
        if (pos > 0 && base[pos - 1] === '_') {
          return `${base.slice(0, pos - 1)}_{${base.slice(pos + 1, -1)},${generated.slice(2, -1)}}`
        }
        break
      }
    }
  }
  return `{${base}}${generated}`
}

export function astToLatex(node: AstNode, ctx?: LatexContext): string {
  if (!node) return ''
  switch (node.type) {
    case 'Var': {
      const name = String(node.name)
      const v = resolveVariable(name, ctx)
      // A latex alias is raw LaTeX (e.g. "\\rho", "0") — render verbatim
      // (with subscript runs braced); otherwise fall back to the
      // surface token the user typed.
      const base = v?.aliases?.latex
        ? braceSubscripts(v.aliases.latex)
        : suggestLatexAlias(v?.label ?? name.replace(/!/g, '\\!'))
      if (v?.index_structures && v.index_structures.length > 0) {
        // Brace the base: a verbatim alias may itself carry a subscript
        // ("r_z") — "{r_z}_{N}" compiles, "r_z_{N}" is a double subscript.
        return appendIndexSubscripts(base, v.index_structures, ctx)
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
    case 'Instantiate': {
      // ``lhs := inst(proto)`` — declares the LHS variable (ctx.lhs) as a
      // new instance of the prototype; the instance's own symbol is the
      // user's latex alias (ADR-008).
      const lhs = ctx?.lhs
        ? astToLatex({ type: 'Var', name: ctx.lhs } as AstNode, ctx)
        : '?'
      return `${lhs} := \\mathrm{inst}\\left( ${astToLatex(node.var as AstNode, ctx)} \\right)`
    }
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
      const arg = astToLatex(node.arg as AstNode, ctx)
      // Explicit macros only — \abs, \asin, \acos, \atan are NOT
      // defined commands (KaTeX parse error); inverse trig is
      // \arcsin &c., abs renders as |x|.
      const TEX_FN: Record<string, string> = {
        sin: '\\sin', cos: '\\cos', tan: '\\tan',
        asin: '\\arcsin', acos: '\\arccos', atan: '\\arctan',
        exp: '\\exp', ln: '\\ln', log: '\\log',
      }
      if (name in TEX_FN) {
        return `${TEX_FN[name]}\\left( ${arg} \\right)`
      }
      if (name === 'sqrt') {
        return `\\sqrt{${arg}}`
      }
      if (name === 'abs') {
        return `\\left| ${arg} \\right|`
      }
      if (name === 'neg') {
        return `- ${wrap(node.arg as AstNode, ctx)}`
      }
      if (name === 'inv') {
        return `${wrap(node.arg as AstNode, ctx, true)}^{-1}`
      }
      if (name === 'sign') {
        return `\\text{sign}\\left( ${arg} \\right)`
      }
      return `\\text{${name}}\\left( ${arg} \\right)`
    }
    case 'Call':
      return `\\text{${astToLatex(node.name as AstNode, ctx)}}\\left( ${(node.args as AstNode[]).map((n) => astToLatex(n as AstNode, ctx)).join(', ')} \\right)`
    default:
      return `\\text{${JSON.stringify(node).slice(0, 80)}}`
  }
}

const GREEK_NAMES = new Set([
  'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'varepsilon', 'zeta',
  'eta', 'theta', 'vartheta', 'iota', 'kappa', 'lambda', 'mu', 'nu',
  'xi', 'pi', 'varpi', 'rho', 'varrho', 'sigma', 'varsigma', 'tau',
  'upsilon', 'phi', 'varphi', 'chi', 'psi', 'omega',
  'Gamma', 'Delta', 'Theta', 'Lambda', 'Xi', 'Pi', 'Sigma', 'Upsilon',
  'Phi', 'Psi', 'Omega',
])

export function suggestLatexAlias(name: string): string {
  const [base, ...qualifierParts] = name.trim().split('_')
  const symbol = GREEK_NAMES.has(base) ? `\\${base}` : texEscape(base)
  return qualifierParts.length
    ? `${symbol}_{${texEscape(qualifierParts.join('_'))}}`
    : symbol
}

export function validateLatexAlias(alias: string): string | null {
  const value = alias.trim()
  if (!value) return null
  const latex = appendIndexSubscripts(braceSubscripts(value), ['validation'], {
    indices: [{ iri: 'validation', label: 'N', network: '', aliases: { internal_code: 'N' } }],
  })
  try {
    renderToString(latex, { throwOnError: true })
    return null
  } catch (error) {
    return error instanceof Error ? error.message.replace(/^KaTeX parse error:\s*/, '') : String(error)
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
