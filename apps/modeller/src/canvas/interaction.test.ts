import { describe, it, expect } from 'vitest'
import { transition, initialInteraction } from './interaction'
import type { Mode, Ctx, Output } from './interaction'
import type { GraphView } from '../types'

/** Minimal Ctx builder — tests override the fields they exercise. */
const ctx = (over: Partial<Ctx> = {}): Ctx => ({
  inRef: false,
  selectedIds: [],
  selectedId: null,
  selectedArcIri: null,
  selectedArcCarrier: null,
  graphView: { treeNodeId: 0, nodes: [], arcs: [], openArcs: [] } as GraphView,
  ...over,
})

const leaf = (id = '5', iri = 'g/Node_5', et = 'et:A') =>
  ({ kind: 'leaf' as const, id, treeNodeId: 5, modelNodeIri: iri, entityType: et })
const comp = (id = '4') => ({ kind: 'composite' as const, id, treeNodeId: 4 })
const armed = (iri = 'g/Node_1'): Mode => ({ name: 'armed', source: { modelIri: iri, entityType: 'et:A' } })

const cmds = (out: Output[]) => out.filter((o) => o.kind === 'cmd').map((o) => (o as { cmd: { type: string } }).cmd.type)
const kinds = (out: Output[]) => out.map((o) => o.kind)

describe('interaction automaton', () => {
  it('plain leaf click selects and arms the connect gesture', () => {
    const r = transition(initialInteraction, { kind: 'nodeClick', node: leaf(), mods: { ctrl: false, shift: false } }, ctx())
    expect(cmds(r.out)).toEqual(['selectNode'])
    expect(r.next).toEqual({ name: 'armed', source: { modelIri: 'g/Node_5', entityType: 'et:A' } })
  })

  it('Ctrl+click toggles without arming', () => {
    const r = transition(armed(), { kind: 'nodeClick', node: leaf(), mods: { ctrl: true, shift: false } }, ctx())
    expect(cmds(r.out)).toEqual(['toggleSelectNode'])
    expect(r.next).toEqual(armed())   // armed survives a selection gesture
  })

  it('plain composite click navigates; Ctrl+click toggles it', () => {
    const nav = transition(initialInteraction, { kind: 'nodeClick', node: comp(), mods: { ctrl: false, shift: false } }, ctx())
    expect(kinds(nav.out)).toEqual(['enterComposite'])
    const sel = transition(initialInteraction, { kind: 'nodeClick', node: comp(), mods: { ctrl: true, shift: false } }, ctx())
    expect(cmds(sel.out)).toEqual(['toggleSelectNode'])
  })

  it('armed + right-click leaf connects and re-arms (chained)', () => {
    const r = transition(armed(), { kind: 'nodeRightClick', node: leaf('5', 'g/Node_5') }, ctx())
    const conn = r.out.find((o) => o.kind === 'connect')
    expect(conn).toMatchObject({ source: { modelIri: 'g/Node_1' }, target: { modelIri: 'g/Node_5' }, chained: true })
    expect(r.next).toEqual({ name: 'armed', source: { modelIri: 'g/Node_5', entityType: 'et:A' } })
  })

  it('armed + right-click self cancels', () => {
    const r = transition(armed('g/Node_5'), { kind: 'nodeRightClick', node: leaf('5', 'g/Node_5') }, ctx())
    expect(cmds(r.out)).toEqual(['selectNode'])
    expect(r.next).toEqual({ name: 'idle' })
  })

  it('idle + right-click uses the selected leaf as implicit source', () => {
    const gv = {
      treeNodeId: 0, arcs: [], openArcs: [],
      nodes: [
        { id: '1', type: 'leaf', x: 0, y: 0, label: '', treeNodeId: 1, modelNodeIri: 'g/Node_1', entityType: 'et:A' },
        { id: '5', type: 'leaf', x: 0, y: 0, label: '', treeNodeId: 5, modelNodeIri: 'g/Node_5', entityType: 'et:A' },
      ],
    } as GraphView
    const r = transition(
      initialInteraction,
      { kind: 'nodeRightClick', node: leaf('5', 'g/Node_5') },
      ctx({ selectedId: '1', selectedIds: ['1'], graphView: gv }),
    )
    const conn = r.out.find((o) => o.kind === 'connect')
    expect(conn).toMatchObject({ source: { modelIri: 'g/Node_1' }, target: { modelIri: 'g/Node_5' }, chained: false })
  })

  it('viewChanged kills an armed gesture — no cross-boundary arcs', () => {
    const r = transition(armed(), { kind: 'viewChanged' }, ctx())
    expect(r.next).toEqual({ name: 'idle' })
  })

  it('Escape disarms and clears selection', () => {
    const r = transition(armed(), { kind: 'keyEscape' }, ctx())
    expect(cmds(r.out)).toEqual(['selectNodes'])
    expect(r.next).toEqual({ name: 'idle' })
  })

  it('read-only ref view: mutation swallowed, navigation survives', () => {
    const ro = ctx({ inRef: true })
    const dead = transition(initialInteraction, { kind: 'nodeClick', node: leaf(), mods: { ctrl: false, shift: false } }, ro)
    expect(dead.out[0]).toMatchObject({ kind: 'swallowed', reason: expect.stringContaining('read-only') })
    const nav = transition(initialInteraction, { kind: 'nodeClick', node: comp(), mods: { ctrl: false, shift: false } }, ro)
    expect(kinds(nav.out)).toEqual(['enterComposite'])
  })

  it('marquee boxes leaves AND composites', () => {
    const gv = {
      treeNodeId: 0, arcs: [], openArcs: [],
      nodes: [
        { id: '1', type: 'leaf', x: 0, y: 0, label: '', treeNodeId: 1 },
        { id: '4', type: 'composite', x: 50, y: 50, label: '', treeNodeId: 4 },
        { id: '9', type: 'leaf', x: 500, y: 500, label: '', treeNodeId: 9 },
      ],
    } as GraphView
    let m = transition(initialInteraction, { kind: 'marqueeStart', point: { x: -10, y: -10 } }, ctx())
    m = transition(m.next, { kind: 'marqueeMove', point: { x: 100, y: 100 } }, ctx())
    const end = transition(m.next, { kind: 'marqueeEnd', point: { x: 100, y: 100 }, mods: { ctrl: false, shift: true } }, ctx({ graphView: gv }))
    expect(cmds(end.out)).toEqual(['selectNodes'])
    const sel = end.out[0] as { cmd: { ids: string[] } }
    expect(sel.cmd.ids).toEqual(['1', '4'])   // 9 is outside the box
  })
})
