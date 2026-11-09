import { useCallback, useEffect, useRef, useState } from 'react'
import { checkExpression, generateExpression, parseExpression } from '../api'
import type { AstNode, CheckRequest, CheckResponse, ClassificationAxis, CodegenTarget, Domain, EquationClass, EquationRecord, Index, NetworkTree, SavedEquation, TokenRecord, Variable } from '../types'
import TokenSection, { normaliseTokenVector } from './TokenSection'
import AxisClassifications, {
  applicableAxes,
  kindTag,
  FIELD_LABEL_STYLE,
  findTermIri,
} from '../axisClassifications'
import { nextEquationId, nextInternalId } from '../variableUtils'
import { useVariableLock } from '../useVariableLock'
import ExpressionInput, { type ExpressionInputHandle } from './ExpressionInput'
import LaTeXPreview from './LaTeXPreview'
import NetworkTreeSelect from './NetworkTreeSelect'
import ResultPanel from './ResultPanel'
import VariablePalette from './VariablePalette'
import {
  findNameCollision,
  isValidVariableName,
  VARIABLE_NAME_HINT,
} from '../validation'
import { indexShortLabel, suggestLatexAlias, validateLatexAlias } from '../latex'

/** Bound-value kinds allowed on the LHS of ``Instantiate(proto)`` — an
 *  instance is a bound-value slot, not a computed quantity (§24). */
const BOUND_KINDS = ['constant', 'parameter']

const UNIT_LABELS = ['time', 'length', 'amount', 'mass', 'temperature', 'current', 'light', 'nil']

/** Class the backend auto-assigns to ``Instantiate(proto)`` RHS — not a
 *  picker option; shown (disabled) when the RHS is an Instantiate. */
const AUTO_CLASS = 'instantiate'

export interface DependentVariableEditorProps {
  open: boolean
  onClose: () => void
  variables: Variable[]
  indices: Index[]
  networkTree: NetworkTree
  axes: ClassificationAxis[]
  domains: Domain[]
  /** Equation-class nodes from /context — the picker's options. */
  equationClasses: EquationClass[]
  /** promo:Token catalogue for the carriesToken/tokenVector pickers. */
  tokenCatalogue?: TokenRecord[]
  initialDomain: string
  initialClassifications: Record<string, string>
  /** When set, the editor attaches the equation to this existing
   *  variable instead of minting a new one — fields are prefilled and
   *  structural ones lock while the variable is used (§18). */
  editing?: Variable | null
  /** When set, the editor rewrites this stored equation on ``editing``
   *  instead of appending a new one (edit-equation mode). */
  editingEquation?: { id: string; record: EquationRecord } | null
  onDefaultsChange?: (domain: string, classifications: Record<string, string>) => void
  onAccept: (v: Variable, eq: SavedEquation) => void
  /** Persist the variable record alone (no new equation) — enables
   *  saving field edits like the LaTeX symbol while attaching. */
  onSaveVariable?: (v: Variable) => void
}

export default function DependentVariableEditor({
  open,
  onClose,
  variables,
  indices,
  networkTree,
  axes,
  domains,
  equationClasses,
  tokenCatalogue = [],
  initialDomain,
  initialClassifications,
  editing,
  editingEquation,
  onDefaultsChange,
  onAccept,
  onSaveVariable,
}: DependentVariableEditorProps) {
  const [domain, setDomain] = useState(initialDomain)
  const [classifications, setClassifications] = useState<Record<string, string>>({})
  const [name, setName] = useState('')
  const [latexSym, setLatexSym] = useState('')
  const [latexError, setLatexError] = useState<string | null>(null)

  const [text, setText] = useState('')
  const [ast, setAst] = useState<AstNode | null>(null)
  const [eqClass, setEqClass] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)
  const [checkResult, setCheckResult] = useState<CheckResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [doc, setDoc] = useState('')
  // §34: port-ness is a declaration on the variable, not a separate
  // kind — a dependent variable may also be connectable.
  const [isPort, setIsPort] = useState(false)
  // Manual signature — used only when no equation derives one
  // (declared vars: terminals, parameters, constants).
  const [units, setUnits] = useState<number[]>([0, 0, 0, 0, 0, 0, 0, 0])
  const [selectedIndices, setSelectedIndices] = useState<Set<string>>(new Set())
  // §24 token declarations: carriesToken (network membership, port
  // licensing) and tokenVector (algebraic signature, exponent map).
  const [carriesTokens, setCarriesTokens] = useState<Set<string>>(new Set())
  const [tokenVector, setTokenVector] = useState<Record<string, number>>({})
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
      setName(editing?.label ?? '')
      setLatexSym(editing?.aliases?.latex ?? '')
      const eqRec = editingEquation?.record
      setText(eqRec?.rhs ?? '')
      setAst(null)
      setParseError(null)
      setCheckResult(null)
      setError(null)
      setDoc(editing?.doc ?? '')
      setCarriesTokens(new Set(editing?.tokens ?? []))
      setTokenVector(editing?.token_vector ?? {})
      setIsPort(editing?.port_variable ?? false)
      setUnits([...(editing?.units ?? [0, 0, 0, 0, 0, 0, 0, 0])])
      setSelectedIndices(new Set(editing?.index_structures ?? []))
      // Stored class may be a label or an IRI — match both.
      setEqClass(
        equationClasses.find(
          (c) => c.iri === eqRec?.equation_class || c.label === eqRec?.equation_class,
        )?.iri
          ?? equationClasses.find((c) => c.label === 'generic')?.iri
          ?? '',
      )
      setLoading(false)
      setGenCode(null)
      setGenLoading(false)
    }
  }, [open, editing, editingEquation])

  useEffect(() => {
    setAst(null)
    setParseError(null)
    setCheckResult(null)
    setError(null)
    setGenCode(null)
  }, [name, domain, classifications, text, latexSym])

  useEffect(() => {
    setLatexError(validateLatexAlias(latexSym))
  }, [latexSym])

  const toggleToken = (iri: string) => {
    setCarriesTokens((prev) => {
      const next = new Set(prev)
      if (next.has(iri)) next.delete(iri)
      else next.add(iri)
      return next
    })
  }

  const toggleIndex = (iri: string) => {
    setSelectedIndices((prev) => {
      const next = new Set(prev)
      if (next.has(iri)) next.delete(iri)
      else next.add(iri)
      return next
    })
  }

  const setTokenExponent = (iri: string, value: string) => {
    setTokenVector((prev) => {
      const next = { ...prev }
      if (value.trim() === '' || Number(value) === 0) delete next[iri]
      else next[iri] = Number(value)
      return next
    })
  }

  // §24 suggestion: the checked equation's derived signature — the
  // variable adopts it (algebraic), while carriesToken stays the
  // user's pick (network membership is definitional, never derived).
  const tokenSuggestion =
    checkResult?.ok && checkResult.tokens && Object.keys(checkResult.tokens).length
      ? { vector: checkResult.tokens, pretty: checkResult.tokens_pretty ?? '' }
      : null

  const applyTokenSuggestion = () => {
    if (!tokenSuggestion) return
    const vec = normaliseTokenVector(tokenSuggestion.vector, tokenCatalogue)
    setTokenVector(vec)
    // Unambiguous case — a single +1 entry IS the network membership
    // (F_conv / n pattern).  Multi-entry vectors stay the user's pick.
    const entries = Object.entries(vec).filter(([, e]) => e !== 0)
    if (entries.length === 1 && entries[0][1] === 1) {
      setCarriesTokens((prev) => new Set([...prev, entries[0][0]]))
    }
  }

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
  const instantiateClassIri =
    equationClasses.find((c) => c.label === AUTO_CLASS)?.iri ?? ''
  // Instantiate RHS pins the class; otherwise the picked value stands.
  const effectiveEqClass = isInstantiate ? instantiateClassIri : eqClass
  // Structural fields lock while the edited variable is used — the
  // Instantiate kind-forcing must not bypass the lock either.
  // `used` resolves async, so also treat "has stored equations" as
  // locked — a variable's own defining equations count as references
  // (§18 lhs refs) and make the lock deterministic from open.
  const hasStoredEquations = !!editing &&
    Object.keys(editing.equations ?? {}).length > 0
  const structuralLocked = !!editing && (used || hasStoredEquations)

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
        // Instantiate LHS must be a bound-value kind — sync the
        // function pick (parameter lives on the function axis) so the
        // request below already carries an allowed kind (ADR-008, §24).
        if (
          !structuralLocked &&
          parseRes.ast.type === 'Instantiate' &&
          !BOUND_KINDS.includes(kindTag(axes, classifications))
        ) {
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
  }, [text, variables, indices, domain, name, classifications, networkTree])

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
      // §26: the store owns minting — a new variable sends an empty
      // IRI and gets ``{graph}#{internal_id}`` back from the server.
      iri: editing?.iri ?? '',
      label: lhs,
      network: domain,
      domain_iri: selectedDomainIri,
      // A locked variable keeps its stored signature — the checker's
      // units/indices belong to the new equation, not the variable,
      // and applying them trips the §18 mutability guard.  An UNUSED
      // (or new) variable still adopts the checker signature — the
      // first equation defines it.
      // Signature priority: stored (locked) > checker > manual pick
      // when no RHS is given — the declared-variable path.
      units: structuralLocked
        ? editing?.units ?? [0, 0, 0, 0, 0, 0, 0, 0]
        : checkResult?.units
          ?? (text.trim() ? editing?.units : undefined)
          ?? units,
      index_structures: structuralLocked
        ? editing?.index_structures ?? []
        : checkResult?.indices
          ?? (text.trim() ? editing?.index_structures : undefined)
          ?? Array.from(selectedIndices),
      internal_id: editing?.internal_id ?? nextInternalId(variables),
      port_variable: isPort,
      classifications,
      tokens: Array.from(carriesTokens),
      token_vector: Object.keys(tokenVector).length ? { ...tokenVector } : undefined,
      aliases,
      doc,
    }
  }, [name, domain, variables, checkResult, latexSym, doc, editing,
      classifications, structuralLocked, carriesTokens, tokenVector, isPort,
      units, selectedIndices, text])

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
  }, [text, variables, indices, domain, name, classifications, networkTree, contextVariables])

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
      : latexError
        ? `Invalid LaTeX symbol — ${latexError}`
        : !checkResult?.ok
          ? 'Run Check on the expression first'
          : null

  const handleAccept = () => {
    const lhs = name.trim()
    if (!lhs || !domain || latexError || !checkResult?.ok) return

    const draft = draftVariable()

    // Edit-equation mode: rewrite the stored entry — the backend
    // re-canonicalises rhs/incidence/latex on the variable POST.
    if (editingEquation && editing) {
      const stored = editing.equations?.[editingEquation.id]
      if (stored) {
        draft.equations = {
          ...draft.equations,
          [editingEquation.id]: {
            ...stored,
            rhs: text.trim(),
            equation_class: effectiveEqClass || stored.equation_class || 'generic',
            incidence_list: checkResult.incidence ?? stored.incidence_list ?? [],
            modified: new Date().toISOString(),
            rhs_latex: null,
          },
        }
      }
      onSaveVariable?.(draft)
      onClose()
      return
    }

    // Sequential E_n — same smallest-free mint as saveVariable's store
    // key, so the pending id matches the persisted record's identity.
    const eq: SavedEquation = {
      id: nextEquationId(variables),
      lhs,
      text,
      ast,
      check: checkResult,
      equation_class: effectiveEqClass || undefined,
    }

    onAccept(draft, eq)
    onClose()
  }

  const exprRef = useRef<ExpressionInputHandle>(null)
  // Palette chips insert at the textarea caret (tracked inside
  // ExpressionInput), not the end — falls back to append only
  // while the input isn't mounted.
  const insertText = useCallback((token: string) => {
    if (exprRef.current) exprRef.current.insert(token)
    else setText((prev) => prev + token)
  }, [])

  const latexSuggestion = name.trim() ? suggestLatexAlias(name) : ''

  // Variable-only edits (LaTeX symbol, doc, domain, classifications) vs
  // the attached record — enables "Save variable" without an equation.
  const variableDirty = !!editing && (
    name.trim() !== editing.label ||
    domain !== (editing.network ?? '') ||
    doc !== (editing.doc ?? '') ||
    latexSym !== (editing.aliases?.latex ?? '') ||
    JSON.stringify(classifications) !== JSON.stringify(editing.classifications ?? {}) ||
    isPort !== (editing.port_variable ?? false) ||
    JSON.stringify(units) !== JSON.stringify(editing.units ?? [0, 0, 0, 0, 0, 0, 0, 0]) ||
    JSON.stringify(Array.from(selectedIndices)) !==
      JSON.stringify(editing.index_structures ?? []) ||
    JSON.stringify([...carriesTokens].sort()) !==
      JSON.stringify([...(editing.tokens ?? [])].sort()) ||
    JSON.stringify(Object.entries(tokenVector).sort()) !==
      JSON.stringify(Object.entries(editing.token_vector ?? {}).sort())
  )

  // A new variable with an empty RHS is equation-less by intent —
  // parameters and constants are authored exactly this way.
  const handleSaveVariable = () => {
    if (latexError || !nameValid || !domain) return
    if (editing) {
      if (!variableDirty) return
      onSaveVariable?.(draftVariable())
      return
    }
    if (text.trim()) return
    onSaveVariable?.(draftVariable())
    onClose()
  }

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
              {editingEquation
                ? `Edit equation ${editingEquation.id} — ${editing?.label ?? ''}`
                : editing
                  ? `Add equation — ${editing.label}`
                  : 'New variable'}
            </h3>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
              {acceptBlockReason && (
                <span style={{ fontSize: 11, color: '#b8860b' }}>{acceptBlockReason}</span>
              )}
              <button type="button" onClick={onClose}>
                Cancel
              </button>
              {onSaveVariable && (editing || !text.trim()) && (
                <button
                  type="button"
                  onClick={handleSaveVariable}
                  disabled={
                    editing
                      ? !variableDirty || !!latexError || !name.trim()
                      : !nameValid || !domain || !!latexError
                  }
                  title={
                    editing
                      ? 'Save variable changes (name, LaTeX symbol, domain, classifications) without adding an equation'
                      : 'Create the variable without an equation (parameters, constants)'
                  }
                >
                  Save variable
                </button>
              )}
              <button
                type="button"
                onClick={handleAccept}
                disabled={!!acceptBlockReason}
                title={acceptBlockReason ?? undefined}
              >
                {editingEquation ? 'Save equation' : editing ? 'Add equation' : 'Accept'}
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
                <>
                  <AxisClassifications
                    axes={axes}
                    domain={domain}
                    domains={domains}
                    value={classifications}
                    disabled={structuralLocked}
                    onChange={setClassifications}
                  />
                  <span style={{ fontSize: 12, color: '#555' }}>
                    kind: {kindTag(axes, classifications) || 'unclassified'}
                  </span>
                </>
              ) : (
                <span style={{ fontSize: 12, color: '#8d6e00' }}>
                  No classification axes apply in this domain.
                </span>
              )}

              <label
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}
                title={
                  'Connectable across an entity boundary — supplied to a ' +
                  'peer through a contact arc (§34: preference, not gate; ' +
                  'a port variable may still own equations)'
                }
              >
                <input
                  type="checkbox"
                  checked={isPort}
                  disabled={structuralLocked}
                  onChange={(e) => setIsPort(e.target.checked)}
                />
                Port (connectable)
              </label>

              {/* Declared-variable signature — no RHS means no checker
                  derivation, so units/indices are picked manually. */}
              {!structuralLocked && !text.trim() && (
                <>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span style={{ fontSize: 12 }}>Units (SI vector)</span>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                      {UNIT_LABELS.map((label, i) => (
                        <label
                          key={label}
                          style={{ display: 'flex', flexDirection: 'column', gap: 2 }}
                        >
                          <span style={{ fontSize: 10, color: '#666' }}>{label}</span>
                          <input
                            type="number"
                            step="1"
                            value={units[i]}
                            onChange={(e) => {
                              const next = [...units]
                              next[i] = Number(e.target.value)
                              setUnits(next)
                            }}
                            style={{ width: '100%' }}
                          />
                        </label>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <span style={{ fontSize: 12 }}>Index structures</span>
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 4,
                        maxHeight: 140,
                        overflowY: 'auto',
                        border: '1px solid #ccc',
                        borderRadius: 4,
                        padding: 8,
                      }}
                    >
                      {indices.map((i) => (
                        <label
                          key={i.iri}
                          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                        >
                          <input
                            type="checkbox"
                            checked={selectedIndices.has(i.iri)}
                            onChange={() => toggleIndex(i.iri)}
                          />
                          <span
                            title={`${i.iri}${i.aliases?.internal_code ? ' / ' + i.aliases.internal_code : ''}`}
                          >
                            {indexShortLabel(i)} ({i.label})
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              )}

              <TokenSection
                tokenCatalogue={tokenCatalogue}
                carriesTokens={carriesTokens}
                tokenVector={tokenVector}
                onToggleToken={toggleToken}
                onSetExponent={setTokenExponent}
                suggestion={tokenSuggestion}
                onApplySuggestion={applyTokenSuggestion}
              />
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
              indices={indices}
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
              ref={exprRef}
              value={text}
              onChange={setText}
              onCheck={handleCheck}
              disabled={loading}
            />

            <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={FIELD_LABEL_STYLE}>Equation class:</span>
              <select
                value={effectiveEqClass}
                onChange={(e) => setEqClass(e.target.value)}
                disabled={isInstantiate || equationClasses.length === 0}
                title={
                  isInstantiate
                    ? 'Instantiate() right-hand sides are always class `instantiate`'
                    : 'How this equation is used: generic algebra, a balance, an empirical correlation, a user function, or an t=0 initialisation'
                }
              >
                {isInstantiate ? (
                  <option value={instantiateClassIri}>{AUTO_CLASS} (auto)</option>
                ) : (
                  <>
                    <option value="">generic</option>
                    {equationClasses
                      .filter((c) => c.label !== AUTO_CLASS)
                      .map((c) => (
                        <option key={c.iri} value={c.iri}>
                          {c.label}
                        </option>
                      ))}
                  </>
                )}
              </select>
            </label>

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

            <ResultPanel result={checkResult} loading={loading} indices={indices} label={name.trim()} variables={variables} />

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
