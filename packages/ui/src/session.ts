/** Session plumbing shared by every ProMo SPA.
 *
 *  An app is launched as ``<app>?graph=<iri>`` (plus app-specific
 *  params like ``vars`` or ``species``); the params are read once at
 *  module load and appended to every API call via ``withParams`` /
 *  ``apiFetch`` so the backend can scope writes to the artefact.
 */

/** One URL query param, read once, or ``undefined`` when absent. */
export function sessionParam(name: string): string | undefined {
  return new URLSearchParams(window.location.search).get(name) ?? undefined
}

/** The artefact this session edits — present in every ProMo app. */
export const GRAPH_IRI = sessionParam('graph')

/** Append ``?graph=`` plus any extra session params to an API path. */
export function withParams(
  path: string,
  extra: Record<string, string | undefined> = {},
): string {
  const params = new URLSearchParams()
  if (GRAPH_IRI) params.set('graph', GRAPH_IRI)
  for (const [k, v] of Object.entries(extra)) if (v) params.set(k, v)
  const s = params.toString()
  if (!s) return path
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}${s}`
}

/** Build an ``apiFetch`` that appends ``graph`` plus additional
 *  session params by name — e.g. ``createApiFetch('vars')`` for the
 *  instantiation app. */
export function createApiFetch(...extraSessionParams: string[]) {
  const extra: Record<string, string | undefined> = {}
  for (const n of extraSessionParams) extra[n] = sessionParam(n)
  return (path: string, init?: RequestInit) =>
    fetch(withParams(path, extra), init)
}

/** Standard fetcher: ``apiFetch(path)`` → ``fetch(path?graph=…)``. */
export const apiFetch = createApiFetch()
