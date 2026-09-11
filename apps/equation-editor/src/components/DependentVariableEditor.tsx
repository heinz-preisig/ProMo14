import { useCallback, useEffect, useState } from 'react'
import { checkExpression, parseExpression } from '../api'
import type { AstNode, CheckRequest, CheckResponse, Index, NetworkTree, Variable } from '../types'
import ExpressionInput from './ExpressionInput'
import LaTeXPreview from './LaTeXPreview'
import NetworkTreeSelect from './NetworkTreeSelect'
import ResultPanel from './ResultPanel'
import VariablePalette from './VariablePalette'
import type { SavedEquation } from './EquationList'

const VARIABLE_CLASSES = ['state', 'effort', 'transport', 'frame', 'network', 'constant', 'parameter']

export interface DependentVariableEditorProps {
  open: boolean
  onClose: () => void
  variables: Variable[]
  indices: Index[]
  networkTree: NetworkTree
  initialDomain: string
  initialClass: string
  onAccept: (v: Variable, eq: SavedEquation) => void
}

function nextInternalId(variables: Variable[]): string {
  const max = variables
    .map((v) => parseInt(v.internal_id?.replace(/^V_/, '') ?? '0', 10))
    .filter((n) => !Number.isNaN(n))
  const next = (max.length ? Math.max(...max) : 0) + 1
  return `V_${next}`
}

export default function DependentVariableEditor({
  open,
  onClose,
  variables,
  indices,
  networkTree,
  initialDomain,
  initialClass,
  onAccept,
}: DependentVariableEditorProps) {
  const [domain, setDomain] = useState(initialDomain)
  const [variableClass, setVariableClass] = useState(initialClass)
  const [name, setName] = useState('')

  const [text, setText] = useState('')
  const [ast, setAst] = useState<AstNode | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [checkResult, setCheckResult] = useState<CheckResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [doc, setDoc] = useState('')

  useEffect(() => {
    if (open) {
      setDomain(initialDomain)
      setVariableClass(initialClass)
      setName('')
      setText('')
      setAst(null)
      setParseError(null)
      setCheckResult(null)
      setError(null)
      setDoc('')
      setLoading(false)
    }
  }, [open])

  useEffect(() => {
    setAst(null)
    setParseError(null)
    setCheckResult(null)
    setError(null)
  }, [name, domain, variableClass, text])

  const handleCheck = useCallback(async () => {
    setLoading(true)
    setParseError(null)
    setAst(null)
    setCheckResult(null)
    setError(null)
    try {
      const parseRes = await parseExpression(text)
      if (parseRes.ok && parseRes.ast) {
        setAst(parseRes.ast)
      } else {
        setParseError(parseRes.error ?? 'Parse failed')
        setLoading(false)
        return
      }

      const lhs = name.trim()
      const draft: Variable = {
        iri: `promo:${lhs.toLowerCase()}`,
        label: lhs,
        network: domain,
        type: variableClass,
        units: [0, 0, 0, 0, 0, 0, 0, 0],
        index_structures: [],
        internal_id: nextInternalId(variables),
        port_variable: false,
      }

      const req: CheckRequest = {
        text,
        variables: [...variables, draft],
        indices,
        variable_definition_network: domain,
        expression_definition_network: domain,
        lhs: lhs || null,
        network_tree: networkTree,
      }
      const res = await checkExpression(req)
      setCheckResult(res)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [text, variables, indices, domain, name, variableClass, networkTree])

  const handleAccept = () => {
    const lhs = name.trim()
    if (!lhs || !domain || !variableClass || !checkResult?.ok) return

    const draft: Variable = {
      iri: `promo:${lhs.toLowerCase()}`,
      label: lhs,
      network: domain,
      type: variableClass,
      units: checkResult.units ?? [0, 0, 0, 0, 0, 0, 0, 0],
      index_structures: checkResult.indices ?? [],
      internal_id: nextInternalId(variables),
      port_variable: false,
      doc,
    }

    const eq: SavedEquation = {
      id: `${Date.now()}`,
      lhs,
      text,
      ast,
      check: checkResult,
    }

    onAccept(draft, eq)
    onClose()
  }

  const insertText = useCallback((token: string) => {
    setText((prev) => prev + token)
  }, [])

  if (!open) return null

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
          width: '90vw',
          height: '90vh',
          background: '#fff',
          borderRadius: 6,
          padding: 20,
          boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          fontSize: 13,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            marginBottom: 16,
            paddingBottom: 12,
            borderBottom: '1px solid #ccc',
          }}
        >
          <h3 style={{ margin: 0 }}>New dependent variable</h3>

          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Domain:
            <NetworkTreeSelect tree={networkTree} selected={domain} onSelect={setDomain} />
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Class:
            <select value={variableClass} onChange={(e) => setVariableClass(e.target.value)}>
              <option value="">Select…</option>
              {VARIABLE_CLASSES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Name:
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="LHS name"
              style={{ width: 120 }}
            />
          </label>

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="button" onClick={handleAccept} disabled={!checkResult?.ok || !name.trim()}>
              Accept
            </button>
          </div>
        </div>

        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', gap: 16 }}>
          <div
            style={{
              width: 220,
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
              overflowY: 'auto',
              paddingRight: 8,
            }}
          >
            <strong>Variables</strong>
            <VariablePalette
              variables={variables}
              expressionNetwork={domain}
              onInsert={insertText}
            />
          </div>

          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
              overflowY: 'auto',
            }}
          >
            <ExpressionInput
              value={text}
              onChange={setText}
              onCheck={handleCheck}
              disabled={loading}
            />

            {parseError && (
              <div
                style={{
                  padding: 10,
                  background: '#ffebee',
                  border: '1px solid #ef9a9a',
                  borderRadius: 4,
                  color: '#c62828',
                  fontSize: 13,
                }}
              >
                <strong>Parse error</strong>
                <div>{parseError}</div>
              </div>
            )}

            {error && <div style={{ color: '#c62828', fontSize: 13 }}>{error}</div>}

            <LaTeXPreview
              ast={ast}
              variables={variables}
              indices={indices}
              expressionNetwork={domain}
            />

            <ResultPanel result={checkResult} loading={loading} indices={indices} label={name.trim()} />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}>
                Documentation
                <textarea
                  value={doc}
                  onChange={(e) => setDoc(e.target.value)}
                  placeholder="Add a description for this variable…"
                  style={{ width: '100%', minHeight: 60, fontSize: 13, padding: 8 }}
                />
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
