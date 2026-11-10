import type { TokenRecord } from '../types'
import type { TokenPolicy } from '../axisClassifications'

/** Surface fragment of a token IRI (``…#token_energy`` →
 *  ``token_energy``) — ``promo:tokenVector`` keys are stored
 *  fragment- or IRI-keyed, so comparisons go through this. */
export function tokenFrag(iri: string): string {
  return iri.split('#').pop() ?? iri
}

/** Normalise a checker-derived tokenVector to catalogue IRIs — keys
 *  that match a catalogue entry by IRI or fragment become the full
 *  IRI; unmatched keys are kept verbatim (the backend tolerates
 *  fragment keys). */
export function normaliseTokenVector(
  vector: Record<string, number>,
  catalogue: TokenRecord[],
): Record<string, number> {
  const out: Record<string, number> = {}
  for (const [key, exp] of Object.entries(vector)) {
    const hit = catalogue.find(
      (t) => t.iri === key || tokenFrag(t.iri) === key || tokenFrag(t.iri) === tokenFrag(key),
    )
    out[hit?.iri ?? key] = exp
  }
  return out
}

/** Catalogue flattened roots-first, children indented under their
 *  ``promo:parent`` — the ancestry IS the comparability rule, so the
 *  picker shows it rather than an unordered list. */
function orderedTokens(
  catalogue: TokenRecord[],
): { token: TokenRecord; depth: number }[] {
  const byIri = new Map(catalogue.map((t) => [t.iri, t]))
  const byParent = new Map<string, TokenRecord[]>()
  for (const t of catalogue) {
    // A parent outside the catalogue (shouldn't happen) renders as root.
    const p = t.parent && byIri.has(t.parent) ? t.parent : ''
    byParent.set(p, [...(byParent.get(p) ?? []), t])
  }
  const out: { token: TokenRecord; depth: number }[] = []
  const seen = new Set<string>()
  const walk = (parent: string, depth: number) => {
    for (const t of byParent.get(parent) ?? []) {
      if (seen.has(t.iri)) continue // cycle guard
      seen.add(t.iri)
      out.push({ token: t, depth })
      walk(t.iri, depth + 1)
    }
  }
  walk('', 0)
  return out
}

/** The single most-specific token in a signature — candidates are the
 *  nonzero entries; ``promo:parent`` ancestry drops strict ancestors
 *  (component_mass beats mass — comparability runs descendant→root, so
 *  the specific pick strictly dominates).  ``null`` = no candidates or
 *  a cross-family ambiguity, which stays the user's choice. */
export function specificMember(
  vector: Record<string, number>,
  catalogue: TokenRecord[],
): string | null {
  const byIri = new Map(catalogue.map((t) => [t.iri, t]))
  const norm = normaliseTokenVector(vector, catalogue)
  const candidates = Object.entries(norm)
    .filter(([iri, e]) => e !== 0 && byIri.has(iri))
    .map(([iri]) => iri)
  const ancestors = (iri: string): Set<string> => {
    const out = new Set<string>()
    let cur = byIri.get(iri)
    while (cur?.parent && byIri.has(cur.parent)) {
      out.add(cur.parent)
      cur = byIri.get(cur.parent)
    }
    return out
  }
  const specific = candidates.filter(
    (x) => !candidates.some((z) => z !== x && ancestors(z).has(x)),
  )
  return specific.length === 1 ? specific[0] : null
}

export interface TokenSuggestion {
  /** §24 signature derived from the checked equation. */
  vector: Record<string, number>
  /** Human-readable form, e.g. "energy · component_mass^-1". */
  pretty: string
}

export interface TokenSectionProps {
  /** promo:Token catalogue — the section renders nothing when empty. */
  tokenCatalogue: TokenRecord[]
  /** Selected carriesToken IRIs (network membership, port licensing). */
  carriesTokens: Set<string>
  /** §24 tokenVector exponent map (algebraic signature). */
  tokenVector: Record<string, number>
  onToggleToken: (iri: string) => void
  onSetExponent: (iri: string, value: string) => void
  disabled?: boolean
  /** §24 neutrality-ruling projection — callers derive it via
   *  ``tokenPolicy(axes, classifications)``; ``null`` = unclassified,
   *  no hint shown. */
  policy?: TokenPolicy | null
  /** Checker-derived signature from the defining equation — shown
   *  with an Apply button when present. */
  suggestion?: TokenSuggestion | null
  onApplySuggestion?: () => void
}

/** Shared carriesToken / tokenVector editor — used by the variable
 *  detail dialog and both creation editors so token declarations
 *  happen wherever a variable is defined (§24). */
export default function TokenSection({
  tokenCatalogue,
  carriesTokens,
  tokenVector,
  onToggleToken,
  onSetExponent,
  disabled = false,
  policy = null,
  suggestion = null,
  onApplySuggestion,
}: TokenSectionProps) {
  if (tokenCatalogue.length === 0) return null

  const byIri = new Map(tokenCatalogue.map((t) => [t.iri, t]))

  // Membership candidates = tokens present in the signature
  // (checker-derived ∪ manual).  No signature → unconstrained.
  const signatureVector: Record<string, number> = {
    ...(suggestion ? normaliseTokenVector(suggestion.vector, tokenCatalogue) : {}),
    ...normaliseTokenVector(tokenVector, tokenCatalogue),
  }
  const candidates = new Set(
    Object.entries(signatureVector)
      .filter(([iri, e]) => e !== 0 && byIri.has(iri))
      .map(([iri]) => iri),
  )
  const suggestedMember = specificMember(signatureVector, tokenCatalogue)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span>Tokens</span>
      <div style={{ fontSize: 11, color: '#777' }}>
        carriesToken = network membership (port licensing);
        tokenVector = algebraic signature (exponent per token,
        e.g. energy +1 · mass −1; empty = untracked).
      </div>
      {policy?.bearing && carriesTokens.size === 0 && (
        <div style={{ fontSize: 11, color: '#8d6e00' }}>
          A {policy.kind} carries a token — pick the{' '}
          {policy.family ?? 'token'} network(s) it rides.
        </div>
      )}
      {policy != null && !policy.bearing && policy.kind !== '' &&
        candidates.size === 0 && (
        <div style={{ fontSize: 11, color: '#999' }}>
          {policy.kind} is token-neutral — no network membership
          expected.
        </div>
      )}
      {suggestion && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 12,
            color: '#33691e',
          }}
        >
          <span>
            Suggested signature from equation: <code>{suggestion.pretty}</code>
          </span>
          {onApplySuggestion && (
            <button type="button" onClick={onApplySuggestion}>
              Apply
            </button>
          )}
        </div>
      )}
      {suggestedMember != null && !carriesTokens.has(suggestedMember) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 12,
            color: '#33691e',
          }}
        >
          <span>
            Suggested membership:{' '}
            <strong>{byIri.get(suggestedMember)?.label}</strong>
            {candidates.size > 1
              ? ' — most specific token in the signature'
              : ''}
          </span>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onToggleToken(suggestedMember)}
          >
            Apply
          </button>
        </div>
      )}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          maxHeight: 140,
          overflowY: 'auto',
          border: '1px solid #ccc',
          borderRadius: 4,
          padding: 8,
          opacity: disabled ? 0.55 : 1,
        }}
      >
        {orderedTokens(tokenCatalogue).map(({ token: t, depth }) => (
          <div
            key={t.iri}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              paddingLeft: depth * 16,
            }}
          >
            <label
              style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}
              title={
                t.parent
                  ? `kind of ${
                      tokenCatalogue.find((p) => p.iri === t.parent)?.label ?? t.parent
                    } — comparable by ancestry`
                  : t.iri
              }
            >
              <input
                type="checkbox"
                checked={carriesTokens.has(t.iri)}
                disabled={
                  disabled ||
                  (candidates.size > 0 && !candidates.has(t.iri) &&
                    !carriesTokens.has(t.iri))
                }
                onChange={() => onToggleToken(t.iri)}
              />
              <span>
                {depth > 0 && <span style={{ color: '#999' }}>↳ </span>}
                {t.label}{t.kind ? ` (${t.kind})` : ''}
              </span>
            </label>
            <input
              type="number"
              step="1"
              title={`tokenVector exponent for ${t.label}`}
              placeholder="exp"
              disabled={disabled}
              value={tokenVector[t.iri]
                ?? tokenVector[tokenFrag(t.iri)]
                ?? ''}
              onChange={(e) => onSetExponent(t.iri, e.target.value)}
              style={{ width: 52 }}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
