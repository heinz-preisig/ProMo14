import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import TokenSection from './TokenSection'

const catalogue = [
  { iri: 'signal', label: 'Signal', kind: 'reference' },
  { iri: 'observation', label: 'Observation', kind: 'reference', parent: 'signal' },
  { iri: 'time', label: 'Time', kind: 'basis' },
]

describe('connection membership editor', () => {
  it('offers independent memberships without exponent controls or forced selection', () => {
    const html = renderToStaticMarkup(<TokenSection tokenCatalogue={catalogue} carriesTokens={new Set(['signal'])} onToggleToken={() => {}} />)
    expect(html).toContain('Connection networks')
    expect(html).toContain('Signal')
    expect(html).toContain('Observation')
    expect(html).not.toContain('Time')
    expect(html).not.toContain('type="number"')
    expect(html).not.toContain('Suggested')
    expect(html).not.toContain('disabled')
    expect(html.match(/checked=""/g)).toHaveLength(1)
  })

  it('respects read-only membership controls', () => {
    const html = renderToStaticMarkup(<TokenSection tokenCatalogue={catalogue} carriesTokens={new Set(['signal'])} onToggleToken={() => {}} disabled />)
    expect(html.match(/disabled=""/g)).toHaveLength(2)
  })
})
