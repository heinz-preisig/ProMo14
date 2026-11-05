import type { TokenRecord } from '../types'

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
  suggestion = null,
  onApplySuggestion,
}: TokenSectionProps) {
  if (tokenCatalogue.length === 0) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <span>Tokens</span>
      <div style={{ fontSize: 11, color: '#777' }}>
        carriesToken = network membership (port licensing);
        tokenVector = algebraic signature (exponent per token,
        e.g. energy +1 · mass −1; empty = untracked).
      </div>
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
        {tokenCatalogue.map((t) => (
          <div
            key={t.iri}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
              <input
                type="checkbox"
                checked={carriesTokens.has(t.iri)}
                disabled={disabled}
                onChange={() => onToggleToken(t.iri)}
              />
              <span>
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
