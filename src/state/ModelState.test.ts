import { describe, it, expect } from 'vitest'
import { initialState, applyCommand } from './ModelState'

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
})
