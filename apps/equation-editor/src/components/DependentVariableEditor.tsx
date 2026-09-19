import { useCallback, useEffect, useState } from 'react'
import { checkExpression, generateExpression, parseExpression } from '../api'
import type { AstNode, CheckRequest, CheckResponse, CodegenTarget, Index, NetworkTree, Variable } from '../types'
import ExpressionInput from './ExpressionInput'
import LaTeXPreview from './LaTeXPreview'
import NetworkTreeSelect from './NetworkTreeSelect'
import ResultPanel from './ResultPanel'
import VariablePalette from './VariablePalette'
import type { SavedEquation } from './EquationList'

const VARIABLE_CLASSES = ['state', 'effort', 'transport', 'frame', 'network', 'constant', 'parameter']

/** Classes allowed on the LHS of ``Instantiate(proto)`` — an instance is
 *  a bound-value slot, not a computed quantity (ADR-008). */
const INSTANTIATE_CLASSES = ['constant', 'parameter']

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
  const [latexSym, setLatexSym] = useState('')

  const [text, setText] = useState('')
  const [ast, setAst] = useState<AstNode | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [checkResult, setCheckResult] = useState<CheckResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [doc, setDoc] = useState('')
  const [genTarget, setGenTarget] = useState<CodegenTarget>('python')
  const [genCode, setGenCode] = useState<string | null>(null)
  const [genLoading, setGenLoading] = useState(false)

  useEffect(() => {
    if (open) {
      setDomain(initialDomain)
      setVariableClass(initialClass)
      setName('')
      setLatexSym('')
      setText('')
      setAst(null)
      setParseError(null)
      setCheckResult(null)
      setError(null)
      setDoc('')
      setLoading(false)
      setGenCode(null)
      setGenLoading(false)
    }
  }, [open])

  useEffect(() => {
    setAst(null)
    setParseError(null)
    setCheckResult(null)
    setError(null)
    setGenCode(null)
  }, [name, domain, variableClass, text, latexSym])

  // Instantiate RHS → LHS class restricted to constant|parameter.  The
  // text heuristic covers the pre-check state (ast only exists after a
  // successful parse); the backend checker stays authoritative (ADR-008).
  const isInstantiate =
    ast?.type === 'Instantiate' || /^\s*Instantiate\s*\(/.test(text)
  const effectiveClass =
    isInstantiate && !INSTANTIATE_CLASSES.includes(variableClass)
      ? 'parameter'
      : variableClass

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
        // Instantiate LHS must be constant|parameter — sync the select so
        // the request below already carries an allowed class (ADR-008).
        if (parseRes.ast.type === 'Instantiate' && !INSTANTIATE_CLASSES.includes(variableClass)) {
          setVariableClass('parameter')
        }
      } else {
        setParseError(parseRes.error ?? 'Parse failed')
        setLoading(false)
        return
      }

      const res = await checkExpression(buildRequest())
      setCheckResult(res)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [text, variables, indices, domain, name, variableClass, networkTree])

  /** The draft LHS variable — shared by /check, /generate, accept and the
   *  LaTeX preview so all see the same record (incl. the latex alias). */
  const draftVariable = useCallback((): Variable => {
    const lhs = name.trim()
    return {
      iri: `promo:${lhs.toLowerCase()}`,
      label: lhs,
      network: domain,
      type: effectiveClass,
      units: checkResult?.units ?? [0, 0, 0, 0, 0, 0, 0, 0],
      index_structures: checkResult?.indices ?? [],
      internal_id: nextInternalId(variables),
      port_variable: false,
      aliases: latexSym.trim() ? { latex: latexSym.trim() } : {},
      doc,
    }
  }, [name, domain, effectiveClass, variables, checkResult, latexSym, doc])

  /** The check request for the current inputs — shared by /check and
   *  /generate so both see the same draft LHS variable. */
  const buildRequest = useCallback((): CheckRequest => {
    const lhs = name.trim()
    return {
      text,
      variables: [...variables, draftVariable()],
      indices,
      variable_definition_network: domain,
      expression_definition_network: domain,
      lhs: lhs || null,
      network_tree: networkTree,
    }
  }, [text, variables, indices, domain, name, variableClass, networkTree, draftVariable])

  const handleGenerate = useCallback(async () => {
    setGenLoading(true)
    setGenCode(null)
    setError(null)
    try {
      const res = await generateExpression({ ...buildRequest(), target: genTarget })
      if (res.ok && res.code) {
        setGenCode(res.code)
      } else {
        setError(res.error ?? 'Generate failed')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setGenLoading(false)
    }
  }, [buildRequest, genTarget])

  const handleAccept = () => {
    const lhs = name.trim()
    if (!lhs || !domain || !effectiveClass || !checkResult?.ok) return

    const draft = draftVariable()

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
            <select value={effectiveClass} onChange={(e) => setVariableClass(e.target.value)}>
              <option value="">Select…</option>
              {(isInstantiate ? INSTANTIATE_CLASSES : VARIABLE_CLASSES).map((c) => (
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

          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            LaTeX:
            <input
              type="text"
              value={latexSym}
              onChange={(e) => setLatexSym(e.target.value)}
              placeholder="e.g. \\rho — defaults to name"
              style={{ width: 140 }}
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
              variables={[...variables, draftVariable()]}
              indices={indices}
              expressionNetwork={domain}
              lhs={name.trim() || undefined}
            />

            <ResultPanel result={checkResult} loading={loading} indices={indices} label={name.trim()} />

            {checkResult?.ok && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <strong style={{ fontSize: 13 }}>Generate:</strong>
                  <select
                    value={genTarget}
                    onChange={(e) => { setGenTarget(e.target.value as CodegenTarget); setGenCode(null) }}
                  >
                    <option value="python">Python</option>
                    <option value="matlab">Matlab</option>
                    <option value="latex">LaTeX</option>
                  </select>
                  <button type="button" onClick={handleGenerate} disabled={genLoading}>
                    {genLoading ? 'Generating…' : 'Generate'}
                  </button>
                </div>
                {genCode && (
                  <pre
                    style={{
                      margin: 0,
                      padding: 10,
                      background: '#f5f5f5',
                      border: '1px solid #ddd',
                      borderRadius: 4,
                      fontSize: 12,
                      overflowX: 'auto',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {genCode}
                  </pre>
                )}
              </div>
            )}

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
