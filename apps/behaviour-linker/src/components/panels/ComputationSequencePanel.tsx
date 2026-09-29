import type { Dispatch, SetStateAction } from 'react'
import { EqLine } from '../EqLine'
import { btn, card } from '../../styles'
import type { Equation, EvaluateReport } from '../../types'

interface ComputationSequencePanelProps {
  sequence: string[]
  baseEquation: string | null
  report: EvaluateReport | null
  eqs: Map<string, Equation>
  lab: (iri: string | null | undefined) => string
  onRemove: (iri: string) => void
  onMove: (iri: string, dir: -1 | 1) => void
  dragIri: string | null
  setDragIri: Dispatch<SetStateAction<string | null>>
  dropTarget: string | null
  setDropTarget: Dispatch<SetStateAction<string | null>>
  dropOn: (target: string) => void
}

export function ComputationSequencePanel({
  sequence,
  baseEquation,
  report,
  eqs,
  lab,
  onRemove,
  onMove,
  dragIri,
  setDragIri,
  dropTarget,
  setDropTarget,
  dropOn,
}: ComputationSequencePanelProps) {
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
        return (
          <div
            key={eqIri}
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
        )
      })}
    </div>
  )
}
