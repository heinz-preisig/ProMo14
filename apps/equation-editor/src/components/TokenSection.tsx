import type { TokenRecord } from '../types'

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

interface TokenSectionProps {
  tokenCatalogue: TokenRecord[]
  carriesTokens: Set<string>
  onToggleToken: (iri: string) => void
  disabled?: boolean
}

export default function TokenSection({ tokenCatalogue, carriesTokens, onToggleToken, disabled = false }: TokenSectionProps) {
  const members = tokenCatalogue.filter((t) => t.kind !== 'basis')
  if (members.length === 0) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span>Connection networks</span>
      <div style={{ fontSize: 11, color: '#777' }}>Membership for connection licensing — independent of units and equations.</div>
      <div style={{ maxHeight: 160, overflowY: 'auto', border: '1px solid #ccc', borderRadius: 4, padding: 8 }}>
        {orderedTokens(members).map(({ token, depth }) => (
          <label key={token.iri} style={{ display: 'flex', gap: 6, paddingLeft: depth * 16, marginBottom: 4 }}>
            <input type="checkbox" checked={carriesTokens.has(token.iri)} disabled={disabled} onChange={() => onToggleToken(token.iri)} />
            {token.label}{token.kind ? ` (${token.kind})` : ''}
          </label>
        ))}
      </div>
    </div>
  )
}
