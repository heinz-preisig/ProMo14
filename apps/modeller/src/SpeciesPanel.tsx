// ---------------------------------------------------------------------------
// §20 species gestures — capability-gated editing in the Properties panel.
//
//   species_source    node → pick the Allocation it injects
//   reaction_host     node → toggle hosted Reactions
//   species_transport arc  → per-species permeability (semipermeable wall)
//
// The vocabulary (components / allocations / reactions) comes from the
// species artefact named by the ``?species=`` param.
// ---------------------------------------------------------------------------

import type { ModelArc, ModelNode } from './types'
import type { SpeciesDistribution, SpeciesDocument } from './api'
import type { Command } from './state/ModelState'

const frag = (iri: string) =>
  iri.split('#').pop()?.split('/').pop() ?? iri

const S = {
  box: { fontSize: 11, borderTop: '1px solid #ccc', paddingTop: 8 } as const,
  head: { fontSize: 12, fontWeight: 600, marginBottom: 4 } as const,
  label: { display: 'block', fontSize: 11, marginBottom: 2 } as const,
  select: { width: '100%', fontSize: 11, padding: '2px 4px' } as const,
  check: { display: 'flex', alignItems: 'center', gap: 4,
           fontSize: 11, marginBottom: 2 } as const,
  muted: { fontSize: 10, color: '#9ca3af' } as const,
}

export function SpeciesPanel({
  node,
  nodeCaps,
  arc,
  arcIsTransport,
  speciesDoc,
  aliases,
  dist,
  dispatch,
}: {
  node?: ModelNode
  nodeCaps: string[]
  arc?: ModelArc
  arcIsTransport: boolean
  speciesDoc: SpeciesDocument
  /** §20 model-level alias map (Component IRI → local name). */
  aliases: Map<string, string>
  /** §20 live distribution — species present per element. */
  dist?: SpeciesDistribution | null
  dispatch: (c: Command) => void
}) {
  const compLabel = (iri: string) =>
    aliases.get(iri) ??
    speciesDoc.components.find((c) => c.iri === iri)?.label ??
    frag(iri)

  const rxnLabel = (iri: string) =>
    speciesDoc.reactions.find((r) => r.iri === iri)?.label ?? frag(iri)

  const readout = (
    label: string,
    iris: string[] | undefined,
    labelOf: (iri: string) => string = compLabel,
  ) =>
    iris && iris.length > 0
      ? <div style={S.muted}>{label}: {iris.map(labelOf).join(', ')}</div>
      : null

  // ---- node gestures -------------------------------------------------------
  if (node) {
    const canSource = nodeCaps.includes('species_source')
    const canReact = nodeCaps.includes('reaction_host')
    const present = dist?.nodes[node.iri]
    const active = dist?.reactions[node.iri]
    if (!canSource && !canReact && !present?.length && !active?.length)
      return null
    return (
      <div style={S.box}>
        <div style={S.head}>Species</div>
        {readout('present', present)}
        {readout('active', active, rxnLabel)}
        {canSource && (
          <>
            <label style={S.label}>injects allocation</label>
            <select
              style={S.select}
              value={node.speciesAllocation ?? ''}
              onChange={(e) =>
                dispatch({
                  type: 'setNodeSpecies',
                  iri: node.iri,
                  speciesAllocation: e.target.value || undefined,
                  reactions: node.reactions,
                })
              }
            >
              <option value="">— none —</option>
              {speciesDoc.allocations.map((a) => (
                <option key={a.iri} value={a.iri}>
                  {a.label || frag(a.iri)} ({a.members.length})
                </option>
              ))}
            </select>
          </>
        )}
        {canReact && (
          <>
            <label style={{ ...S.label, marginTop: 6 }}>hosts reactions</label>
            {speciesDoc.reactions.map((r) => {
              const on = node.reactions?.includes(r.iri) ?? false
              return (
                <label key={r.iri} style={S.check}>
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() =>
                      dispatch({
                        type: 'setNodeSpecies',
                        iri: node.iri,
                        speciesAllocation: node.speciesAllocation,
                        reactions: on
                          ? (node.reactions ?? []).filter((x) => x !== r.iri)
                          : [...(node.reactions ?? []), r.iri],
                      })
                    }
                  />
                  {r.label || frag(r.iri)}
                </label>
              )
            })}
            {speciesDoc.reactions.length === 0 && (
              <div style={S.muted}>no reactions in the species artefact</div>
            )}
          </>
        )}
      </div>
    )
  }

  // ---- arc gesture ---------------------------------------------------------
  if (arc && arcIsTransport) {
    const perm = arc.permeable // undefined = all pass
    return (
      <div style={S.box}>
        <div style={S.head}>Permeability</div>
        {readout('carries', dist?.arcs[arc.iri])}
        <label style={S.check}>
          <input
            type="checkbox"
            checked={perm === undefined}
            onChange={() =>
              dispatch({
                type: 'setArcPermeable',
                iri: arc.iri,
                permeable: perm === undefined
                  ? [] // restrict to nothing → then tick species
                  : undefined, // back to all-pass
              })
            }
          />
          all species pass
        </label>
        {perm !== undefined && (
          <>
            <div style={S.muted}>pass:</div>
            {speciesDoc.components.map((c) => {
              const on = perm.includes(c.iri)
              return (
                <label key={c.iri} style={S.check}>
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() =>
                      dispatch({
                        type: 'setArcPermeable',
                        iri: arc.iri,
                        permeable: on
                          ? perm.filter((x) => x !== c.iri)
                          : [...perm, c.iri],
                      })
                    }
                  />
                  {compLabel(c.iri)}
                </label>
              )
            })}
          </>
        )}
      </div>
    )
  }

  return null
}
