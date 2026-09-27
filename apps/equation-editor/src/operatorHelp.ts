/** Operator reference for the expression language — single source for
 *  button tooltips and the "?" help panel in ExpressionInput.
 *  Syntax must match backend/equation/parser.py + syntax.py. */
export interface OperatorHelpEntry {
  /** Button label / lookup key. */
  label: string
  /** Syntax template shown in the help panel and tooltip. */
  syntax: string
  description: string
}

export const OPERATOR_HELP: OperatorHelpEntry[] = [
  { label: '+', syntax: 'a + b', description: 'add' },
  { label: '-', syntax: 'a - b', description: 'subtract' },
  { label: '*', syntax: 'a * b', description: 'reduce product — operands must have exactly one common index' },
  { label: ':', syntax: 'a : b', description: 'expand (outer) product' },
  { label: '.', syntax: 'a . b', description: 'index-preserving product — retains common indices and may expand the index set' },
  { label: '^', syntax: 'a ^ b', description: 'power — right-associative' },
  {
    label: 'Integral',
    syntax: 'Integral(expr :: t in [t0, te])',
    description: 'definite integral of expr over t from t0 to te',
  },
  {
    label: 'Product',
    syntax: 'Product(expr, i)',
    description: 'product of expr over running index i',
  },
  {
    label: 'Root',
    syntax: 'Root(expr)',
    description: 'implicit equation — solve expr = 0',
  },
  {
    label: 'TotalDiff',
    syntax: 'TotalDiff(f, x)',
    description: 'total differential df/dx',
  },
  {
    label: 'ParDiff',
    syntax: 'ParDiff(f, x)',
    description: 'partial differential ∂f/∂x',
  },
  {
    label: 'reduceSum',
    syntax: 'reduceSum(expr, i)',
    description: 'sum of expr over running index i',
  },
  {
    label: 'Instantiate',
    syntax: 'Instantiate(proto)',
    description:
      'declare the LHS variable as an instance of prototype proto — must be the whole right-hand side (ADR-008)',
  },
  {
    label: 'max / min',
    syntax: 'max(a, b)',
    description: 'maximum or minimum of two expressions',
  },
  {
    label: 'sin cos exp log abs neg sign',
    syntax: 'f(x)',
    description: 'unary functions',
  },
  {
    label: 'sqrt',
    syntax: 'sqrt(x)',
    description: 'square root — every unit exponent must be even',
  },
  {
    label: 'inv',
    syntax: 'inv(x)',
    description: 'scalar reciprocal',
  },
  {
    label: 'f(…)',
    syntax: 'myFunc(a, b)',
    description: 'call a registered user function',
  },
]
