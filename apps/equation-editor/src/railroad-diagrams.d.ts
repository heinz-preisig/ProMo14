/** Local types for railroad-diagrams (UMD build — no @types package).
 *  The library assigns its exports in a forEach loop, which static CJS
 *  analysis can't detect — so only the default export is declared here;
 *  destructure from it. */
declare module 'railroad-diagrams' {
  /** A laid-out diagram fragment — call toString() for SVG markup. */
  export interface DiagramItem {
    format(...args: number[]): DiagramItem
    toString(): string
    addTo(parent?: Element): DiagramItem
  }
  export type Item = DiagramItem | string

  export interface Railroad {
    Diagram(...items: Item[]): DiagramItem
    ComplexDiagram(...items: Item[]): DiagramItem
    Sequence(...items: Item[]): DiagramItem
    Choice(normal: number, ...items: Item[]): DiagramItem
    Optional(item: Item, skip?: Item): DiagramItem
    OneOrMore(item: Item, repeat?: Item): DiagramItem
    ZeroOrMore(item: Item, repeat?: Item, skip?: Item): DiagramItem
    Terminal(text: string, opts?: Record<string, unknown>): DiagramItem
    NonTerminal(text: string, opts?: Record<string, unknown>): DiagramItem
    Comment(text: string, opts?: Record<string, unknown>): DiagramItem
    Skip(): DiagramItem
  }
  const rr: Railroad
  export default rr
}
