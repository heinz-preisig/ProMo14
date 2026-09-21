import { useMemo } from 'react'
import type { SavedEquation, Variable } from '../types'

export interface DeleteImpact {
  target: Variable
  variableIris: string[]
  equationIds: string[]
}

function stripPrefix(s: string): string {
  // incidence may contain qualified names like "network!iri"; keep the iri part
  return s.includes('!') ? s.split('!').pop()! : s
}

export function computeDeleteImpact(
  target: Variable,
  variables: Variable[],
  equations: SavedEquation[]
): DeleteImpact {
  const iriToVar = new Map<string, Variable>()
  const labelToIri = new Map<string, string>()
  for (const v of variables) {
    iriToVar.set(v.iri, v)
    labelToIri.set(v.label, v.iri)
  }

  const toDeleteIris = new Set<string>([target.iri])
  const toDeleteEqIds = new Set<string>()

  let changed = true
  while (changed) {
    changed = false
    for (const eq of equations) {
      if (toDeleteEqIds.has(eq.id)) continue

      const lhsIri = labelToIri.get(eq.lhs)
      const incidence = new Set((eq.check?.incidence ?? []).map(stripPrefix))

      if (lhsIri && toDeleteIris.has(lhsIri)) {
        toDeleteEqIds.add(eq.id)
        changed = true
        continue
      }

      if ([...incidence].some((iri) => toDeleteIris.has(iri))) {
        toDeleteEqIds.add(eq.id)
        if (lhsIri && !toDeleteIris.has(lhsIri)) {
          toDeleteIris.add(lhsIri)
          changed = true
        } else {
          changed = true
        }
      }
    }
  }

  return {
    target,
    variableIris: [...toDeleteIris].sort(),
    equationIds: [...toDeleteEqIds].sort(),
  }
}

export interface DeleteVariableDialogProps {
  open: boolean
  target: Variable | null
  variables: Variable[]
  equations: SavedEquation[]
  onClose: () => void
  onConfirm: (impact: DeleteImpact) => void
}

export default function DeleteVariableDialog({
  open,
  target,
  variables,
  equations,
  onClose,
  onConfirm,
}: DeleteVariableDialogProps) {
  const impact = useMemo(() => {
    if (!target) return null
    return computeDeleteImpact(target, variables, equations)
  }, [target, variables, equations])

  if (!open || !target || !impact) return null

  const iriToVar = new Map(variables.map((v) => [v.iri, v]))
  const impactedVariables = impact.variableIris.map((iri) => iriToVar.get(iri)).filter((v): v is Variable => !!v)
  const impactedEquations = equations.filter((eq) => impact.equationIds.includes(eq.id))
  const onlyTarget = impactedVariables.length === 1 && impactedEquations.length === 0

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        style={{
          width: 480,
          maxHeight: '80vh',
          background: '#fff',
          borderRadius: 6,
          padding: 20,
          boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          overflowY: 'auto',
        }}
      >
        <h3 style={{ margin: 0 }}>Delete variable?</h3>
        <div>
          You are about to delete <strong>{target.label}</strong>.
        </div>

        {onlyTarget ? (
          <div style={{ color: '#555', fontSize: 13 }}>
            No other variables or saved equations depend on it.
          </div>
        ) : (
          <div
            style={{
              background: '#fff3e0',
              border: '1px solid #ffb74d',
              borderRadius: 4,
              padding: 12,
              color: '#e65100',
              fontSize: 13,
            }}
          >
            <strong>Warning:</strong> the following dependent variables and equations will also be
            deleted because they depend on <strong>{target.label}</strong> directly or indirectly.
          </div>
        )}

        {impactedVariables.length > 1 && (
          <div>
            <strong style={{ fontSize: 13 }}>Variables to delete</strong>
            <ul style={{ margin: '4px 0', paddingLeft: 18, fontSize: 13 }}>
              {impactedVariables
                .filter((v) => v.iri !== target.iri)
                .map((v) => (
                  <li key={v.iri}>
                    <strong>{v.label}</strong> <span style={{ color: '#666' }}>({v.network})</span>
                  </li>
                ))}
            </ul>
          </div>
        )}

        {impactedEquations.length > 0 && (
          <div>
            <strong style={{ fontSize: 13 }}>Equations to delete</strong>
            <ul style={{ margin: '4px 0', paddingLeft: 18, fontSize: 13 }}>
              {impactedEquations.map((eq) => (
                <li key={eq.id}>
                  <code>
                    {eq.lhs} = {eq.text.length > 50 ? eq.text.slice(0, 50) + '…' : eq.text}
                  </code>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(impact)}
            style={{
              background: '#c62828',
              color: '#fff',
              border: '1px solid #c62828',
              borderRadius: 4,
              padding: '4px 12px',
              cursor: 'pointer',
            }}
          >
            Delete {impactedVariables.length > 1 || impactedEquations.length > 0
              ? `${impactedVariables.length} variable(s) and ${impactedEquations.length} equation(s)`
              : 'variable'}
          </button>
        </div>
      </div>
    </div>
  )
}
