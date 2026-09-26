import { useCallback, useEffect, useState } from 'react'
import { checkExpression, generateExpression, parseExpression } from '../api'
import type { AstNode, CheckRequest, CheckResponse, ClassificationAxis, CodegenTarget, Domain, Index, NetworkTree, SavedEquation, Variable } from '../types'
import AxisClassifications, {
  applicableAxes,
  deriveType,
  FIELD_LABEL_STYLE,
  findTermIri,
} from '../axisClassifications'
import { nextInternalId } from '../variableUtils'
import { useVariableLock } from '../useVariableLock'
import ExpressionInput from './ExpressionInput'
import LaTeXPreview from './LaTeXPreview'
import NetworkTreeSelect from './NetworkTreeSelect'
import ResultPanel from './ResultPanel'
import VariablePalette from './VariablePalette'
import {
  findNameCollision,
  isValidVariableName,
  VARIABLE_CLASSES,
  VARIABLE_NAME_HINT,
} from '../validation'
import { suggestLatexAlias, validateLatexAlias } from '../latex'

/** Classes allowed on the LHS of ``Instantiate(proto)`` — an instance is
 *  a bound-value slot, not a computed quantity (ADR-008). */
const INSTANTIATE_CLASSES = ['constant', 'parameter']

export interface DependentVariableEditorProps {
  open: boolean
  onClose: () => void
  variables: Variable[]
  indices: Index[]
  networkTree: NetworkTree
  axes: ClassificationAxis[]
  domains: Domain[]
  initialDomain: string
  initialClassifications: Record<string, string>
  /** When set, the editor attaches the equation to this existing
   *  variable instead of minting a new one — fields are prefilled and
   *  structural ones lock while the variable is used (§18). */
  editing?: Variable | null
  onDefaultsChange?: (domain: string, classifications: Record<string, string>) => void
  onAccept: (v: Variable, eq: SavedEquation) => void
}

export default function DependentVariableEditor({
  open,
  onClose,
  variables,
  indices,
  networkTree,
  axes,
  domains,
  initialDomain,
  initialClassifications,
  editing,
  onDefaultsChange,
  onAccept,
}: DependentVariableEditorProps) {
  const [domain, setDomain] = useState(initialDomain)
  const [classifications, setClassifications] = useState<Record<string, string>>({})
  const [variableClass, setVariableClass] = useState('')
  const [name, setName] = useState('')
  const [latexSym, setLatexSym] = useState('')
  const [latexError, setLatexError] = useState<string | null>(null)

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
  // §18 usage lock — structural fields grey out while referenced.
  const { used } = useVariableLock(editing?.iri)

  useEffect(() => {
    if (open) {
      const cls = editing?.classifications ?? initialClassifications
      setDomain(editing?.network ?? initialDomain)
      setClassifications(cls)
      setVariableClass(editing?.type ?? deriveType(axes, cls))
      setName(editing?.label ?? '')
      setLatexSym(editing?.aliases?.latex ?? '')
      setText('')
      setAst(null)
      setParseError(null)
      setCheckResult(null)
      setError(null)
      setDoc(editing?.doc ?? '')
      setLoading(false)
      setGenCode(null)
      setGenLoading(false)
    }
  }, [open, editing])

  useEffect(() => {
    setAst(null)
    setParseError(null)
    setCheckResult(null)
    setError(null)
    setGenCode(null)
  }, [name, domain, variableClass, text, latexSym])

  useEffect(() => {
    setLatexError(validateLatexAlias(latexSym))
  }, [latexSym])

  // Report the current domain/classifications so the app can offer
  // them as defaults next time either variable editor is opened.
  // Skipped in editing mode — the existing variable's values aren't
  // user defaults.
  useEffect(() => {
    if (!editing) onDefaultsChange?.(domain, classifications)
  }, [domain, classifications, editing])

  // Instantiate RHS → LHS class restricted to constant|parameter.  The
  // text heuristic covers the pre-check state (ast only exists after a
  // successful parse); the backend checker stays authoritative (ADR-008).
  const isInstantiate =
    ast?.type === 'Instantiate' || /^\s*Instantiate\s*\(/.test(text)
  // Structural fields lock while the edited variable is used — the
  // Instantiate class-forcing must not bypass the lock either.
  const structuralLocked = !!editing && used
  const effectiveClass =
    !structuralLocked && isInstantiate && !INSTANTIATE_CLASSES.includes(variableClass)
      ? 'parameter'
      : variableClass

  // Names must be valid expression-language identifiers (lexer rule).
  const nameValid = isValidVariableName(name)
  const collision = findNameCollision(
    editing ? variables.filter((x) => x.iri !== editing.iri) : variables,
    name,
  )

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
        // Instantiate LHS must be constant|parameter — sync the
        // function pick (parameter lives on the function axis) so the
        // request below already carries an allowed class (ADR-008).
        if (
          !structuralLocked &&
          parseRes.ast.type === 'Instantiate' &&
          !INSTANTIATE_CLASSES.includes(variableClass)
        ) {
          setVariableClass('parameter')
          const hit = findTermIri(axes, 'function', 'parameter')
          if (hit) {
            setClassifications((prev) => ({ ...prev, [hit.axisIri]: hit.termIri }))
          }
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
   *  LaTeX preview so all see the same record (incl. the latex alias).
   *  In editing mode it carries the existing record (iri, internal_id,
   *  equations, classifications, audit fields) so saveVariable's
   *  replace-semantics POST loses nothing. */
  const draftVariable = useCallback((): Variable => {
    const lhs = name.trim()
    const aliases = { ...(editing?.aliases ?? {}) }
    if (latexSym.trim()) aliases.latex = latexSym.trim()
    else delete aliases.latex
    const selectedDomainIri = domains.find((item) => item.name === domain)?.iri ?? null
    return {
      ...(editing ?? {}),
      // Case-sensitive IRI: the language treats `rho` and `Rho` as
      // distinct identifiers, so the IRI must preserve case too.
      iri: editing?.iri ?? `promo:${lhs}`,
      label: lhs,
      network: domain,
      domain_iri: selectedDomainIri,
      type: effectiveClass,
      units: checkResult?.units ?? editing?.units ?? [0, 0, 0, 0, 0, 0, 0, 0],
      index_structures: checkResult?.indices ?? editing?.index_structures ?? [],
      internal_id: editing?.internal_id ?? nextInternalId(variables),
      port_variable: editing?.port_variable ?? false,
      classifications,
      aliases,
      doc,
    }
  }, [name, domain, effectiveClass, variables, checkResult, latexSym, doc, editing, classifications])

  /** The variable context for /check, /generate and the LaTeX preview —
   *  the draft replaces the stored record when editing, appends when
   *  creating. */
  const contextVariables = useCallback((): Variable[] => {
    if (!nameValid) return variables
    const draft = draftVariable()
    return editing
      ? variables.map((x) => (x.iri === editing.iri ? draft : x))
      : [...variables, draft]
  }, [variables, editing, draftVariable, nameValid])

  /** The check request for the current inputs — shared by /check and
   *  /generate so both see the same draft LHS variable. */
  const buildRequest = useCallback((): CheckRequest => {
    const lhs = name.trim()
    const selectedDomainIri = domains.find((item) => item.name === domain)?.iri ?? null
    return {
      text,
      variables: contextVariables(),
      indices,
      variable_definition_network: domain,
      variable_definition_domain_iri: selectedDomainIri,
      expression_definition_network: domain,
      expression_definition_domain_iri: selectedDomainIri,
      lhs: lhs || null,
      network_tree: networkTree,
    }
  }, [text, variables, indices, domain, name, variableClass, networkTree, contextVariables])

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

  /** Why Accept is disabled — surfaced inline next to the button,
   *  because title tooltips don't reliably fire on disabled elements. */
  const acceptBlockReason = !nameValid
    ? `Invalid or missing name — ${VARIABLE_NAME_HINT}`
    : !domain
      ? 'Select a domain in the tree'
      : !effectiveClass
        ? 'Pick a class via the axis selections'
        : latexError
          ? `Invalid LaTeX symbol — ${latexError}`
          : !checkResult?.ok
            ? 'Run Check on the expression first'
            : null

  const handleAccept = () => {
    const lhs = name.trim()
    if (!lhs || !domain || !effectiveClass || latexError || !checkResult?.ok) return

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

  const latexSuggestion = name.trim() ? suggestLatexAlias(name) : ''

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
            marginBottom: 16,
            paddingBottom: 12,
            borderBottom: '1px solid #ccc',
          }}
        >
          {/* Row 1: title + actions */}
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
            <h3 style={{ margin: 0 }}>
              {editing ? `Add equation — ${editing.label}` : 'New dependent variable'}
            </h3>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
              {acceptBlockReason && (
                <span style={{ fontSize: 11, color: '#b8860b' }}>{acceptBlockReason}</span>
              )}
              <button type="button" onClick={onClose}>
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAccept}
                disabled={!!acceptBlockReason}
                title={acceptBlockReason ?? undefined}
              >
                {editing ? 'Add equation' : 'Accept'}
              </button>
            </div>
          </div>

          {/* Row 2: domain tree + stacked classification/name fields */}
          <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
            <label
              style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
              title={structuralLocked ? 'Locked — variable is referenced by equations' : undefined}
            >
              Domain:
              <span
                style={
                  structuralLocked
                    ? { pointerEvents: 'none', opacity: 0.55, display: 'inline-flex' }
                    : { display: 'inline-flex' }
                }
              >
                <NetworkTreeSelect
                  tree={networkTree}
                  selected={domain}
                  onSelect={setDomain}
                  maxHeight={220}
                />
              </span>
            </label>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={FIELD_LABEL_STYLE}>Name:</span>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="LHS name"
                  title={VARIABLE_NAME_HINT}
                  style={{
                    width: 120,
                    borderColor: name.trim() && !nameValid ? '#c62828' : undefined,
                  }}
                />
                {name.trim() && !nameValid && (
                  <span style={{ fontSize: 11, color: '#c62828' }}>{VARIABLE_NAME_HINT}</span>
                )}
                {nameValid && collision === 'exact' && (
                  <span style={{ fontSize: 11, color: '#c62828' }}>
                    A variable named {name.trim()} already exists — saving overwrites it
                  </span>
                )}
                {nameValid && collision === 'similar' && (
                  <span style={{ fontSize: 11, color: '#b8860b' }}>
                    Differs only by case from an existing variable — names are case-sensitive
                  </span>
                )}
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={FIELD_LABEL_STYLE}>LaTeX:</span>
                <input
                  type="text"
                  value={latexSym}
                  onChange={(e) => setLatexSym(e.target.value)}
                  placeholder="e.g. \\rho — defaults to name"
                  style={{ width: 140, borderColor: latexError ? '#c62828' : undefined }}
                />
                {latexSuggestion && latexSym.trim() !== latexSuggestion && (
                  <button type="button" onClick={() => setLatexSym(latexSuggestion)}>
                    Use {latexSuggestion}
                  </button>
                )}
                {latexError && (
                  <span style={{ fontSize: 11, color: '#c62828' }}>{latexError}</span>
                )}
              </label>

              {applicableAxes(axes, domain, domains).length ? (
                <AxisClassifications
                  axes={axes}
                  domain={domain}
                  domains={domains}
                  value={classifications}
                  disabled={structuralLocked}
                  onChange={(next) => {
                    setClassifications(next)
                    setVariableClass(deriveType(axes, next))
                  }}
                />
              ) : (
                <label
                  style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                  title={structuralLocked ? 'Locked — variable is referenced by equations' : undefined}
                >
                  <span style={FIELD_LABEL_STYLE}>Class:</span>
                  <select
                    value={effectiveClass}
                    onChange={(e) => setVariableClass(e.target.value)}
                    disabled={structuralLocked}
                  >
                    <option value="">Select…</option>
                    {(isInstantiate ? INSTANTIATE_CLASSES : VARIABLE_CLASSES).map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
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
              networkTree={networkTree}
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
              variables={contextVariables()}
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
