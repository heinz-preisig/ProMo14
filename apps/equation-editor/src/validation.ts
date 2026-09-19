/** Shared variable-definition constants and validation.
 *
 *  ``VARIABLE_NAME_RE`` mirrors the expression-language lexer
 *  (``backend/equation/parser.py``): an identifier is
 *  ``[a-zA-Z_][a-zA-Z0-9_]*`` — letters, digits and underscore, not
 *  starting with a digit.  The ``!`` network qualifier is *not* part
 *  of a variable's own label; it only appears in qualified references.
 */
export const VARIABLE_NAME_RE = /^[a-zA-Z_][a-zA-Z0-9_]*$/

export function isValidVariableName(name: string): boolean {
  return VARIABLE_NAME_RE.test(name.trim())
}

export const VARIABLE_NAME_HINT =
  'Letters, digits and underscore; must not start with a digit'

export const VARIABLE_CLASSES = [
  'state',
  'effort',
  'transport',
  'frame',
  'network',
  'constant',
  'parameter',
]

/** Names are case-sensitive end-to-end (lexer, rdfs:label lookup and
 *  the minted IRI all preserve case).  This helper spots collisions a
 *  user is likely to miss: an exact match means the save overwrites an
 *  existing variable; a case-variant match (`rho` vs `Rho`) is legal
 *  but almost always a mistake. */
export function findNameCollision(
  variables: { label: string }[],
  name: string,
): 'exact' | 'similar' | null {
  const trimmed = name.trim()
  if (!trimmed) return null
  const lower = trimmed.toLowerCase()
  let similar = false
  for (const v of variables) {
    if (v.label === trimmed) return 'exact'
    if (v.label.toLowerCase() === lower) similar = true
  }
  return similar ? 'similar' : null
}
