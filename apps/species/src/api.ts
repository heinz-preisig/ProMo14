import type { SpeciesDocument } from './types'

const qs = (params: Record<string, string | undefined>) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v) q.set(k, v)
  const s = q.toString()
  return s ? `?${s}` : ''
}

export const graphParam = () =>
  new URLSearchParams(window.location.search).get('graph') ?? undefined

export async function fetchSpecies(graph?: string): Promise<SpeciesDocument> {
  const r = await fetch(`/api/species/species${qs({ graph })}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function saveSpecies(
  doc: SpeciesDocument,
  graph?: string,
): Promise<SpeciesDocument> {
  const r = await fetch(`/api/species/species${qs({ graph })}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(doc),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function storeStatus(): Promise<{ dirty: boolean }> {
  const r = await fetch('/api/ontology/status')
  if (!r.ok) return { dirty: false }
  return r.json()
}

export async function saveStore(): Promise<void> {
  await fetch('/api/ontology/save', { method: 'POST' })
}
