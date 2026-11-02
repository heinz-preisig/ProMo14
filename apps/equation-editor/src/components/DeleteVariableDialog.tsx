import 'katex/dist/katex.min.css'
import { useMemo } from 'react'
import { astToLatex, renderLatex } from '../latex'
import type { Index, Variable } from '../types'

export interface DeleteImpact {
  target: Variable
  variableIris: string[]
  equationIds: string[]
}

/** Flattened view of every persisted equation, derived from variables.
 *  Owner is tracked by IRI (rename-robust); incidence comes from the
 *  canonical promo:incidenceList — always populated, unlike the
 *  session-only check result. */
interface FlatEquation {
  id: string
  ownerIri: string
  ownerLabel: string
  rhs: string
  incidence: string[]
}

function flattenEquations(variables: Variable[]): FlatEquation[] {
  const out: FlatEquation[] = []
  for (const v of variables) {
    for (const [id, rec] of Object.entries(v.equations ?? {})) {
      out.push({
        id,
        ownerIri: v.iri,
        ownerLabel: v.label,
        rhs: rec.rhs,
        incidence: rec.incidence_list ?? [],
      })
    }
  }
  return out
}

export function computeDeleteImpact(
  target: Variable,
  variables: Variable[]
): DeleteImpact {
  const flat = flattenEquations(variables)
  const toDeleteIris = new Set<string>([target.iri])
  const toDeleteEqIds = new Set<string>()

  let changed = true
  while (changed) {
    changed = false
    for (const eq of flat) {
      if (toDeleteEqIds.has(eq.id)) continue
      if (!toDeleteIris.has(eq.ownerIri)
          && !eq.incidence.some((iri) => toDeleteIris.has(iri))) {
        continue
      }
      toDeleteEqIds.add(eq.id)
      // The equation dies → so does the variable it defines; the cone
      // grows and the loop re-scans.
      if (!toDeleteIris.has(eq.ownerIri)) {
        toDeleteIris.add(eq.ownerIri)
        changed = true
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
  indices?: Index[]
  onClose: () => void
  onConfirm: (impact: DeleteImpact) => void
}

export default function DeleteVariableDialog({
  open,
  target,
  variables,
  indices = [],
  onClose,
  onConfirm,
}: DeleteVariableDialogProps) {
  const flatEqs = useMemo(() => flattenEquations(variables), [variables])
  const impact = useMemo(() => {
    if (!target) return null
    return computeDeleteImpact(target, variables)
  }, [target, variables])

  if (!open || !target || !impact) return null

  const iriToVar = new Map(variables.map((v) => [v.iri, v]))
  const impactedVariables = impact.variableIris.map((iri) => iriToVar.get(iri)).filter((v): v is Variable => !!v)
  const impactedEquations = flatEqs.filter((eq) => impact.equationIds.includes(eq.id))
  const onlyTarget = impactedVariables.length === 1 && impactedEquations.length === 0
  // Frozen walls — the backend 409s; mirror it here so the reason is
  // visible before confirming.
  const frozenVars = impactedVariables.filter((v) => v.frozen)
  const blocked = !!target.frozen || frozenVars.length > 0

  // Rendered symbol for a variable — latex alias + index subscripts.
  const varLatexHtml = (v: Variable) =>
    renderLatex(astToLatex({ type: 'Var', name: v.label }, { variables, indices }), false)


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
          You are about to delete{' '}
          <strong
            dangerouslySetInnerHTML={{ __html: varLatexHtml(target) }}
          />{' '}
          <span style={{ color: '#666', fontSize: 12 }}>({target.label})</span>.
        </div>

        {blocked && (
          <div
            style={{
              background: '#e3f2fd',
              border: '1px solid #1565c0',
              borderRadius: 4,
              padding: 12,
              color: '#1565c0',
              fontSize: 13,
            }}
          >
            <strong>Blocked:</strong> {target.frozen
              ? <><strong>{target.label}</strong> is frozen (proven)</>
              : <>{frozenVars.map((v) => v.label).join(', ')} {frozenVars.length === 1 ? 'is' : 'are'} frozen (proven)</>
            } — unfreeze first.
          </div>
        )}

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
                    <span dangerouslySetInnerHTML={{ __html: varLatexHtml(v) }} />{' '}
                    <span style={{ color: '#666' }}>{v.label} ({v.network})</span>
                    {v.frozen && (
                      <span style={{ marginLeft: 4, fontSize: 10, color: '#1565c0' }}>frozen</span>
                    )}
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
                <li key={eq.id} style={{ overflowX: 'auto' }}>
                  <code>
                    {eq.ownerLabel} = {eq.rhs.length > 50 ? eq.rhs.slice(0, 50) + '…' : eq.rhs}
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
            disabled={blocked}
            title={blocked ? 'Unfreeze the marked variables first' : undefined}
            style={{
              background: blocked ? '#bbb' : '#c62828',
              color: '#fff',
              border: `1px solid ${blocked ? '#bbb' : '#c62828'}`,
              borderRadius: 4,
              padding: '4px 12px',
              cursor: blocked ? 'not-allowed' : 'pointer',
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
