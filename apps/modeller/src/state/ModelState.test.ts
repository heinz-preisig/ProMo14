import { describe, it, expect } from 'vitest'
import { initialState, applyCommand } from './ModelState'
import { defaultOrientation } from '../model/ModelGraph'
import type { ModelArc } from '../types'

const TF = 'promo:ArcType/token-flow'
const REF = 'promo:ArcType/reference'

describe('defaultOrientation (§15)', () => {
  const arc = (from: string, to: string, refFrom?: string, refTo?: string): ModelArc =>
    ({ iri: `${from}->${to}`, sourceIri: from, targetIri: to, arcType: TF, referenceFrom: refFrom, referenceTo: refTo })

  it('returns undefined for non-token-flow arcs (inherent direction)', () => {
    expect(defaultOrientation(REF, 'a', 'b', false, false, [])).toBeUndefined()
  })

  it('defaults to draw order when no transport is involved', () => {
    expect(defaultOrientation(TF, 'a', 'b', false, false, []))
      .toEqual({ referenceFrom: 'a', referenceTo: 'b' })
  })

  it('first arc on a transport follows draw order', () => {
    // capacity → transport drawn: points into the transport
    expect(defaultOrientation(TF, 'cap', 'T', false, true, []))
      .toEqual({ referenceFrom: 'cap', referenceTo: 'T' })
    // transport → capacity drawn: points out of the transport
    expect(defaultOrientation(TF, 'T', 'cap', true, false, []))
      .toEqual({ referenceFrom: 'T', referenceTo: 'cap' })
  })

  it('second arc on a transport complements the first (through-path)', () => {
    // existing arc points INTO T → new arc points OUT
    const existing = [arc('cap1', 'T')]
    expect(defaultOrientation(TF, 'T', 'cap2', true, false, existing))
      .toEqual({ referenceFrom: 'T', referenceTo: 'cap2' })
    // existing arc points OUT of T → new arc points IN
    const existingOut = [arc('T', 'cap1')]
    expect(defaultOrientation(TF, 'cap2', 'T', false, true, existingOut))
      .toEqual({ referenceFrom: 'cap2', referenceTo: 'T' })
  })

  it('respects explicit (reversed) orientation of existing arcs', () => {
    // existing arc drawn T→cap but reversed to cap→T (points INTO T)
    const existing = [arc('T', 'cap1', 'cap1', 'T')]
    expect(defaultOrientation(TF, 'cap2', 'T', false, true, existing))
      .toEqual({ referenceFrom: 'T', referenceTo: 'cap2' })
  })

  it('transport↔transport arcs follow draw order', () => {
    expect(defaultOrientation(TF, 'T1', 'T2', true, true, []))
      .toEqual({ referenceFrom: 'T1', referenceTo: 'T2' })
  })
})

describe('applyCommand', () => {
  describe('reconnectOpenArc', () => {
    it('reattaches an open arc to a new leaf and removes the open entry', () => {
      let state = initialState

      // Create two leaves and connect them.
      state = applyCommand(state, {
        type: 'insertNode',
        id: 1,
        iri: 'promo:Model/Node_1',
        label: 'A',
        entityType: 'promo:TypeA',
        parentViewNodeId: 0,
        x: 0,
        y: 0,
      })
      state = applyCommand(state, {
        type: 'insertNode',
        id: 2,
        iri: 'promo:Model/Node_2',
        label: 'B',
        entityType: 'promo:TypeB',
        parentViewNodeId: 0,
        x: 0,
        y: 0,
      })
      state = applyCommand(state, {
        type: 'insertArc',
        iri: 'promo:Arc/Arc_1',
        sourceIri: 'promo:Model/Node_1',
        targetIri: 'promo:Model/Node_2',
        arcType: 'promo:ArcType1',
      })

      expect(state.modelArcs.size).toBe(1)

      // Zoom into leaf 1: this converts it to a composite and creates an open arc.
      state = applyCommand(state, {
        type: 'insertNode',
        id: 3,
        iri: 'promo:Model/Node_3',
        label: 'Detail',
        entityType: 'promo:TypeA',
        parentViewNodeId: 1,
        x: 0,
        y: 0,
      })

      expect(state.modelArcs.size).toBe(0)
      expect(state.openArcs.get(1)?.length).toBe(1)

      // Reconnect the dangling end to the new child leaf.
      state = applyCommand(state, {
        type: 'reconnectOpenArc',
        openArcIri: 'promo:Arc/Arc_1',
        newModelNodeIri: 'promo:Model/Node_3',
      })

      expect(state.modelArcs.size).toBe(1)
      expect(state.openArcs.get(1)).toBeUndefined()
      expect(state.selectedModelArcIri).toBe('promo:Arc/Arc_1')

      const arc = state.modelArcs.get('promo:Arc/Arc_1')!
      expect(arc.sourceIri).toBe('promo:Model/Node_3')
      expect(arc.targetIri).toBe('promo:Model/Node_2')
      expect(arc.arcType).toBe('promo:ArcType1')
    })
  })

  describe('reverseArcOrientation (§15)', () => {
    const twoNodes = () => {
      let state = initialState
      state = applyCommand(state, {
        type: 'insertNode', id: 1, iri: 'promo:Model/Node_1', label: 'A',
        entityType: 'promo:TypeA', parentViewNodeId: 0, x: 0, y: 0,
      })
      state = applyCommand(state, {
        type: 'insertNode', id: 2, iri: 'promo:Model/Node_2', label: 'B',
        entityType: 'promo:TypeB', parentViewNodeId: 0, x: 0, y: 0,
      })
      return state
    }

    it('reverses a draw-order arc into an explicit reverse', () => {
      let state = applyCommand(twoNodes(), {
        type: 'insertArc', iri: 'promo:Arc/Arc_1',
        sourceIri: 'promo:Model/Node_1', targetIri: 'promo:Model/Node_2',
        arcType: TF,
      })
      state = applyCommand(state, { type: 'reverseArcOrientation', iri: 'promo:Arc/Arc_1' })
      const arc = state.modelArcs.get('promo:Arc/Arc_1')!
      // draw order untouched; reference direction flipped
      expect(arc.sourceIri).toBe('promo:Model/Node_1')
      expect(arc.targetIri).toBe('promo:Model/Node_2')
      expect(arc.referenceFrom).toBe('promo:Model/Node_2')
      expect(arc.referenceTo).toBe('promo:Model/Node_1')
    })

    it('reverses an explicitly oriented arc back', () => {
      let state = applyCommand(twoNodes(), {
        type: 'insertArc', iri: 'promo:Arc/Arc_1',
        sourceIri: 'promo:Model/Node_1', targetIri: 'promo:Model/Node_2',
        arcType: TF,
        referenceFrom: 'promo:Model/Node_2', referenceTo: 'promo:Model/Node_1',
      })
      state = applyCommand(state, { type: 'reverseArcOrientation', iri: 'promo:Arc/Arc_1' })
      const arc = state.modelArcs.get('promo:Arc/Arc_1')!
      expect(arc.referenceFrom).toBe('promo:Model/Node_1')
      expect(arc.referenceTo).toBe('promo:Model/Node_2')
    })
  })

  describe('open arcs preserve orientation (§15)', () => {
    it('carries refToExternal through leaf→composite and restores it on reconnect', () => {
      let state = initialState
      state = applyCommand(state, {
        type: 'insertNode', id: 1, iri: 'promo:Model/Node_1', label: 'A',
        entityType: 'promo:TypeA', parentViewNodeId: 0, x: 0, y: 0,
      })
      state = applyCommand(state, {
        type: 'insertNode', id: 2, iri: 'promo:Model/Node_2', label: 'B',
        entityType: 'promo:TypeB', parentViewNodeId: 0, x: 0, y: 0,
      })
      // Token-flow arc with reference direction INTO Node_1 (reversed
      // vs draw order): refToExternal (→ Node_2) = false.
      state = applyCommand(state, {
        type: 'insertArc', iri: 'promo:Arc/Arc_1',
        sourceIri: 'promo:Model/Node_1', targetIri: 'promo:Model/Node_2',
        arcType: TF,
        referenceFrom: 'promo:Model/Node_2', referenceTo: 'promo:Model/Node_1',
      })

      // Leaf 1 becomes a composite — the arc goes open.
      state = applyCommand(state, {
        type: 'insertNode', id: 3, iri: 'promo:Model/Node_3', label: 'Detail',
        entityType: 'promo:TypeA', parentViewNodeId: 1, x: 0, y: 0,
      })
      const open = state.openArcs.get(1)![0]
      expect(open.refToExternal).toBe(false)

      // Reconnect: reference direction restored — still pointing at the
      // (new) internal node, i.e. away from the external one.
      state = applyCommand(state, {
        type: 'reconnectOpenArc',
        openArcIri: 'promo:Arc/Arc_1',
        newModelNodeIri: 'promo:Model/Node_3',
      })
      const arc = state.modelArcs.get('promo:Arc/Arc_1')!
      expect(arc.referenceFrom).toBe('promo:Model/Node_2')
      expect(arc.referenceTo).toBe('promo:Model/Node_3')
    })
  })
})
