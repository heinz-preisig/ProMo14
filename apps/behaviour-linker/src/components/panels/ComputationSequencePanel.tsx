import { useState } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { EqLine } from '../EqLine'
import { btn, card } from '../../styles'
import type { Equation, EvaluateReport } from '../../types'

interface ComputationSequencePanelProps {
  sequence: string[]
  baseEquation: string | null
  outputs: string[]
  report: EvaluateReport | null
  eqs: Map<string, Equation>
  lab: (iri: string | null | undefined) => string
  onRemove: (iri: string) => void
  onMove: (iri: string, dir: -1 | 1) => void
  onToggleOutput: (varIri: string) => void
  /** Pick a different definer for a slot's lhs — the engine
   *  exchanges it and re-closes (regime alternatives, §54). */
  onPickAlt: (varIri: string, eqIri: string) => void
  dragIri: string | null
  setDragIri: Dispatch<SetStateAction<string | null>>
  dropTarget: string | null
  setDropTarget: Dispatch<SetStateAction<string | null>>
  dropOn: (target: string) => void
}

export function ComputationSequencePanel({
  sequence,
  baseEquation,
  outputs,
  report,
  eqs,
  lab,
  onRemove,
  onMove,
  onToggleOutput,
  onPickAlt,
  dragIri,
  setDragIri,
  dropTarget,
  setDropTarget,
  dropOn,
}: ComputationSequencePanelProps) {
  const [altFor, setAltFor] = useState<string | null>(null)
  return (
    <div style={card}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        Computation sequence
        {report?.state_variable && (
          <span style={{ fontWeight: 400, color: '#666' }}>
            {' '}
            — state: {lab(report.state_variable)}
          </span>
        )}
      </div>
      {sequence.length === 0 && (
        <div style={{ fontSize: 13, color: '#888' }}>
          No equations selected yet.
        </div>
      )}
      {sequence.map((eqIri, i) => {
        const e = eqs.get(eqIri)
        const alts = e
          ? Array.from(eqs.values()).filter(
              (c) => c.lhs === e.lhs && c.iri !== eqIri,
            )
          : []
        return (
          <div key={eqIri}>
          <div
            draggable
            onDragStart={() => setDragIri(eqIri)}
            onDragOver={(ev) => {
              ev.preventDefault()
              setDropTarget(eqIri)
            }}
            onDragLeave={() =>
              setDropTarget((d) => (d === eqIri ? null : d))
            }
            onDrop={() => {
              dropOn(eqIri)
              setDragIri(null)
              setDropTarget(null)
            }}
            onDragEnd={() => {
              setDragIri(null)
              setDropTarget(null)
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
              padding: '2px 4px',
              cursor: 'grab',
              borderTop:
                dropTarget === eqIri && dragIri !== eqIri
                  ? '2px solid #06c'
                  : '2px solid transparent',
              opacity: dragIri === eqIri ? 0.4 : 1,
            }}
          >
            <span style={{ color: '#999', width: 18 }}>{i}</span>
            <span style={{ flex: 1 }}>
              {e ? <EqLine eq={e} lhsLabel={lab(e.lhs)} /> : '?'}
              {eqIri === baseEquation && (
                <span style={{ color: '#06c' }}> (base)</span>
              )}
            </span>
            {e && (
              <button
                style={{
                  ...btn,
                  color: outputs.includes(e.lhs) ? '#06c' : undefined,
                  fontWeight: outputs.includes(e.lhs) ? 700 : 400,
                }}
                title="toggle output endpoint on the LHS variable"
                onClick={() => onToggleOutput(e.lhs)}
              >
                out
              </button>
            )}
            {alts.length > 0 && (
              <button
                style={{
                  ...btn,
                  color: altFor === eqIri ? '#06c' : undefined,
                }}
                title={`alternatives for ${lab(e?.lhs)}`}
                onClick={() =>
                  setAltFor((a) => (a === eqIri ? null : eqIri))
                }
              >
                ⇄{alts.length}
              </button>
            )}
            <button style={btn} onClick={() => onMove(eqIri, -1)}>
              ↑
            </button>
            <button style={btn} onClick={() => onMove(eqIri, 1)}>
              ↓
            </button>
            <button style={btn} onClick={() => onRemove(eqIri)}>
              ✕
            </button>
          </div>
          {altFor === eqIri && e && (
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 6,
                padding: '4px 4px 4px 26px',
                fontSize: 13,
              }}
            >
              {alts.map((c) => (
                <button
                  key={c.iri}
                  style={btn}
                  title={c.rhs}
                  onClick={() => {
                    onPickAlt(e.lhs, c.iri)
                    setAltFor(null)
                  }}
                >
                  ⇄ <EqLine eq={c} lhsLabel={lab(c.lhs)} />
                </button>
              ))}
            </div>
          )}
          </div>
        )
      })}
    </div>
  )
}
