import { useMemo } from 'react'
import rr from 'railroad-diagrams'
import 'railroad-diagrams/railroad-diagrams.css'

const { Diagram, Sequence, Choice, Optional, ZeroOrMore, Terminal: T, NonTerminal: NT } = rr

/** Railway diagrams for the expression grammar — must match
 *  backend/equation/parser.py. */

// Equation -> 'Instantiate' '(' Identifier ')' | Expression
const equationRule = () =>
  Diagram(
    Choice(
      0,
      Sequence(T('Instantiate'), T('('), NT('identifier'), T(')')),
      NT('expression'),
    ),
  ).toString()

// Expression -> Factor ( INFIX Factor )*   — '*' may carry an index: a * i b
const expressionRule = () =>
  Diagram(
    Sequence(
      NT('factor'),
      ZeroOrMore(
        Sequence(
          Choice(
            0,
            T('+'),
            T('-'),
            Sequence(T('*'), Optional(NT('index'))),
            T(':'),
            T('.'),
            T('^'),
          ),
          NT('factor'),
        ),
      ),
    ),
  ).toString()

// Factor -> '(' Expression ')' | Integral | Product | Root | MaxMin
//         | TotalDiff | ParDiff | reduceSum | UFunc | Function | Identifier
const factorRule = () =>
  Diagram(
    Choice(
      0,
      Sequence(T('('), NT('expression'), T(')')),
      Sequence(
        T('Integral'), T('('), NT('expression'), T('::'), NT('var'),
        T('in'), T('['), NT('var'), T(','), NT('var'), T(']'), T(')'),
      ),
      Sequence(T('Product'), T('('), NT('expression'), T(','), NT('index'), T(')')),
      Sequence(T('Root'), T('('), NT('expression'), T(')')),
      Sequence(
        Choice(0, T('max'), T('min')), T('('),
        NT('expression'), T(','), NT('expression'), T(')'),
      ),
      Sequence(T('TotalDiff'), T('('), NT('expression'), T(','), NT('expression'), T(')')),
      Sequence(T('ParDiff'), T('('), NT('expression'), T(','), NT('expression'), T(')')),
      Sequence(T('reduceSum'), T('('), NT('expression'), T(','), NT('index'), T(')')),
      Sequence(NT('ufunc'), T('('), NT('expression'), T(')')),
      Sequence(
        NT('function'), T('('), NT('expression'),
        ZeroOrMore(Sequence(T(','), NT('expression'))), T(')'),
      ),
      NT('identifier'),
    ),
  ).toString()

/** Stylesheet for the print window — mirrors railroad-diagrams.css so the
 *  SVGs render identically on paper (the imported CSS only applies to the
 *  app document, not the popup). */
const PRINT_CSS = `
svg.railroad-diagram { background-color: hsl(30,20%,95%); }
svg.railroad-diagram path { stroke-width: 3; stroke: black; fill: rgba(0,0,0,0); }
svg.railroad-diagram text { font: bold 14px monospace; text-anchor: middle; }
svg.railroad-diagram text.label { text-anchor: start; }
svg.railroad-diagram text.comment { font: italic 12px monospace; }
svg.railroad-diagram rect { stroke-width: 3; stroke: black; fill: hsl(120,100%,90%); }
body { font-family: sans-serif; padding: 24px; }
h2 { font-size: 18px; margin: 0 0 12px; }
h3 { font-size: 13px; color: #555; margin: 16px 0 4px; }
p.note { font-size: 12px; color: #666; max-width: 560px; }
`

const FOOTNOTE =
  '<code>*</code> may carry an index: <code>a * i b</code> reduces over i. ' +
  'Identifiers are <code>label</code> or <code>network!label</code>; no ' +
  'numeric literals. <code>Instantiate</code> is only valid as the whole ' +
  'right-hand side.'

export interface SyntaxDiagramProps {
  onClose: () => void
}

/** Modal showing the expression grammar as railway diagrams. */
export default function SyntaxDiagram({ onClose }: SyntaxDiagramProps) {
  const rules = useMemo(
    () => [
      { name: 'equation', svg: equationRule() },
      { name: 'expression', svg: expressionRule() },
      { name: 'factor', svg: factorRule() },
    ],
    [],
  )

  /** Open a minimal print window with just the diagrams — a cheat sheet. */
  const print = () => {
    const win = window.open('', '_blank', 'width=900,height=700')
    if (!win) return
    const sections = rules
      .map((r) => `<h3><code>${r.name}</code></h3>${r.svg}`)
      .join('')
    win.document.write(
      '<!doctype html><html><head><title>ProMo expression syntax</title>' +
        `<style>${PRINT_CSS}</style></head><body>` +
        `<h2>ProMo expression syntax</h2>${sections}` +
        `<p class="note">${FOOTNOTE}</p>` +
        '</body></html>',
    )
    win.document.close()
    win.focus()
    win.print()
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 3000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          padding: 20,
          borderRadius: 8,
          maxWidth: '90vw',
          maxHeight: '85vh',
          overflow: 'auto',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
          }}
        >
          <h3 style={{ margin: 0 }}>Expression syntax</h3>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              type="button"
              onClick={print}
              title="Print as a cheat sheet"
              style={{ fontSize: 12, padding: '4px 10px' }}
            >
              Print
            </button>
            <button type="button" onClick={onClose} style={{ fontSize: 16 }}>
              ×
            </button>
          </div>
        </div>
        {rules.map((r) => (
          <div key={r.name} style={{ marginBottom: 16 }}>
            <div
              style={{ fontSize: 12, fontWeight: 'bold', color: '#555', marginBottom: 4 }}
            >
              <code>{r.name}</code>
            </div>
            {/* SVG generated locally by railroad-diagrams — safe to inject */}
            <div dangerouslySetInnerHTML={{ __html: r.svg }} />
          </div>
        ))}
        <div
          style={{ fontSize: 12, color: '#666', maxWidth: 560 }}
          dangerouslySetInnerHTML={{ __html: FOOTNOTE }}
        />
      </div>
    </div>
  )
}
