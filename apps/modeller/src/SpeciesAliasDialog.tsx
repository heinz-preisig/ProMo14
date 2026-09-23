// ---------------------------------------------------------------------------
// §20 species aliases — model-level dialog.
//
// The species artefact owns the abstract vocabulary (A, B, C …); the
// model owns its interpretation.  An alias binds a Component IRI to a
// local name ("A" :: "H2O") — persisted as promo:speciesAlias triples
// in the model graph, so two models can read the same scheme
// differently.
// ---------------------------------------------------------------------------

import type { SpeciesDocument } from './api'
import type { Command } from './state/ModelState'

const frag = (iri: string) =>
  iri.split('#').pop()?.split('/').pop() ?? iri

const S: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
  },
  dialog: {
    background: '#fff', borderRadius: 8, padding: 16, width: 380,
    maxHeight: '70vh', display: 'flex', flexDirection: 'column',
    boxShadow: '0 8px 30px rgba(0,0,0,0.25)',
  },
  head: { fontSize: 14, fontWeight: 600, marginBottom: 4 },
  sub: { fontSize: 11, color: '#6b7280', marginBottom: 12 },
  list: { overflowY: 'auto', flex: 1 },
  row: {
    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
    fontSize: 12,
  },
  name: { width: 110, fontFamily: 'monospace', fontSize: 11 },
  input: {
    flex: 1, minWidth: 0, padding: '3px 6px', fontSize: 12,
    border: '1px solid #d1d5db', borderRadius: 4,
  },
  footer: { display: 'flex', justifyContent: 'flex-end', marginTop: 12 },
  btn: {
    padding: '5px 14px', fontSize: 12, border: 'none', borderRadius: 5,
    background: '#2563eb', color: '#fff', cursor: 'pointer',
    fontWeight: 600,
  },
  muted: { fontSize: 11, color: '#9ca3af' },
}

export function SpeciesAliasDialog({
  speciesDoc,
  aliases,
  dispatch,
  onClose,
}: {
  speciesDoc: SpeciesDocument
  aliases: Map<string, string>
  dispatch: (c: Command) => void
  onClose: () => void
}) {
  return (
    <div style={S.overlay} onClick={onClose}>
      <div style={S.dialog} onClick={(e) => e.stopPropagation()}>
        <div style={S.head}>Species aliases</div>
        <div style={S.sub}>
          Local names for this model — the artefact stays abstract.
        </div>
        <div style={S.list}>
          {speciesDoc.components.map((c) => (
            <div key={c.iri} style={S.row}>
              <span style={S.name} title={c.iri}>
                {c.label || frag(c.iri)}
              </span>
              <span>::</span>
              <input
                style={S.input}
                placeholder="alias (e.g. H2O)"
                value={aliases.get(c.iri) ?? ''}
                onChange={(e) =>
                  dispatch({
                    type: 'setSpeciesAlias',
                    componentIri: c.iri,
                    alias: e.target.value,
                  })
                }
              />
            </div>
          ))}
          {speciesDoc.components.length === 0 && (
            <div style={S.muted}>no components in the species artefact</div>
          )}
        </div>
        <div style={S.footer}>
          <button style={S.btn} onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  )
}
