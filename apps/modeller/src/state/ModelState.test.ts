import { describe, it, expect } from 'vitest'
import { initialState, applyCommand } from './ModelState'
import { defaultOrientation } from '../model/ModelGraph'
import { deserializeState } from '../modelPersistence'
import { computeGraphView } from '../tree/computeGraphView'
import type { ModelDocument } from '../modelPersistence'
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

  describe('insertStamped (copy-and-integrate)', () => {
    const stampDoc = (): ModelDocument => ({
      rootTreeId: 1, nextTreeId: 5, arcCounter: 1,
      nodes: [
        { iri: 'tpl/Node_2', entityType: 'et:A', label: 'A' },
        { iri: 'tpl/Node_3', entityType: 'et:B', label: 'B' },
        { iri: 'tpl/Node_5', entityType: 'et:C', label: 'C' },
      ],
      arcs: [{
        iri: 'tpl/Arc_1', sourceIri: 'tpl/Node_2', targetIri: 'tpl/Node_3',
        arcType: TF, referenceFrom: 'tpl/Node_2', referenceTo: 'tpl/Node_3',
      }],
      composites: [
        {
          treeId: 1, label: 'root', parentTreeId: null,
          children: [
            { id: 2, iri: 'tpl/Node_2' },
            { id: 3, iri: 'tpl/Node_3' },
            { id: 4 },
          ],
          layout: { '2': { x: 10, y: 20 }, '3': { x: 30, y: 40 }, '4': { x: 50, y: 60 } },
          knots: {}, openArcs: [],
        },
        {
          treeId: 4, label: 'Sub', parentTreeId: 1,
          children: [{ id: 5, iri: 'tpl/Node_5' }],
          layout: { '5': { x: 1, y: 2 } }, knots: {},
          openArcs: [{
            iri: 'tpl/oa1', externalIri: 'tpl/Node_5', arcType: '',
            isSource: false, externalEntityType: 'et:C',
          }],
        },
      ],
    })

    const stamped = () => applyCommand(initialState, {
      type: 'insertStamped', id: 1, label: 'tpl',
      parentViewNodeId: 0, x: 0, y: 0,
      stamped: deserializeState(stampDoc()), graphIri: 'host',
    })

    it('copies the subtree with fresh ids and host-minted IRIs', () => {
      const state = stamped()
      // wrapper composite under root
      expect(state.tree.nodes.get(1)?.parentId).toBe(0)
      expect(state.tree.nodes.get(1)?.label).toBe('tpl')
      // stamped children remapped: leaves 2,3 and composite 4 (with leaf 5)
      expect(state.tree.nodes.get(2)?.iri).toBe('host/Node_2')
      expect(state.tree.nodes.get(4)?.children).toEqual([5])
      expect(state.tree.nodes.get(5)?.iri).toBe('host/Node_5')
      // model nodes minted in the host namespace — no template IRIs
      expect(state.modelNodes.size).toBe(3)
      expect([...state.modelNodes.keys()].every((iri) => iri.startsWith('host/Node_'))).toBe(true)
      expect(state.selectedVisibleNodeIds).toEqual(['1'])
    })

    it('remaps arc endpoints, openArc terminals, and view layouts', () => {
      const state = stamped()
      expect(state.modelArcs.size).toBe(1)
      const arc = [...state.modelArcs.values()][0]
      expect(arc.iri).toMatch(/^host\/Arc_/)
      expect(arc.sourceIri).toBe('host/Node_2')
      expect(arc.targetIri).toBe('host/Node_3')
      expect(arc.referenceFrom).toBe('host/Node_2')
      // nested composite's terminal points at the COPIED leaf
      expect(state.openArcs.get(4)?.[0].externalIri).toBe('host/Node_5')
      // stamped root layout lands on the wrapper; Sub's on id 4
      expect(state.layoutStore.get(1)?.get('2')).toEqual({ x: 10, y: 20 })
      expect(state.layoutStore.get(4)?.get('5')).toEqual({ x: 1, y: 2 })
    })

    it('stamps twice with disjoint ids/IRIs', () => {
      let state = stamped()
      state = applyCommand(state, {
        type: 'insertStamped', id: state.tree.nextId + 1, label: 'tpl',
        parentViewNodeId: 0, x: 0, y: 0,
        stamped: deserializeState(stampDoc()), graphIri: 'host',
      })
      expect(state.modelNodes.size).toBe(6)
      expect([...state.modelNodes.keys()].every((iri) => iri.startsWith('host/Node_'))).toBe(true)
      expect(state.modelArcs.size).toBe(2)
    })

    it('copied children render as selectable view nodes inside the group', () => {
      let state = stamped()
      // zoom into the stamped 'Sub' composite (new id 4)
      state = applyCommand(state, { type: 'setView', viewNodeId: 4 })
      const view = computeGraphView(4, state.tree, state.modelNodes,
        state.modelArcs, state.layoutStore, state.openArcs,
        state.knotStore, 800, 600)
      const leaf = view.nodes.find((n) => n.id === '5')
      expect(leaf).toMatchObject({
        type: 'leaf', treeNodeId: 5, modelNodeIri: 'host/Node_5',
      })
      // selection mechanics on that id
      state = applyCommand(state, { type: 'selectNode', id: leaf!.id })
      expect(state.selectedVisibleNodeIds).toEqual(['5'])
    })
  })

  describe('deleteNodes cascade', () => {
    it('deleting a composite removes its whole subtree', () => {
      let state = initialState
      for (const [id, iri] of [[1, 'g/Node_1'], [2, 'g/Node_2']] as const)
        state = applyCommand(state, {
          type: 'insertNode', id, iri, label: `N${id}`,
          entityType: 'et:A', parentViewNodeId: 0, x: 0, y: 0,
        })
      state = applyCommand(state, {
        type: 'groupNodes', parentViewNodeId: 0, treeNodeIds: [1, 2],
      })
      const compositeId = state.tree.nextId
      expect(state.tree.nodes.get(compositeId)?.children).toEqual([1, 2])

      state = applyCommand(state, {
        type: 'deleteNodes',
        nodes: [{ visibleNodeId: String(compositeId), treeNodeId: compositeId }],
      })
      expect(state.modelNodes.size).toBe(0)
      expect(state.tree.nodes.has(compositeId)).toBe(false)
      expect(state.tree.nodes.has(1)).toBe(false)
      expect(state.tree.nodes.get(0)?.children).toEqual([])
    })

    it('deleting a leaf drops terminals declared on it', () => {
      let state = applyCommand(initialState, {
        type: 'insertNode', id: 1, iri: 'g/Node_1', label: 'A',
        entityType: 'et:A', parentViewNodeId: 0, x: 0, y: 0,
      })
      state = applyCommand(state, {
        type: 'exposeTerminal', iri: 'g/oa1', compositeId: 0,
        modelNodeIri: 'g/Node_1', entityType: 'et:A',
      })
      expect(state.openArcs.get(0)?.length).toBe(1)
      state = applyCommand(state, {
        type: 'deleteNodes',
        nodes: [{ visibleNodeId: '1', treeNodeId: 1, modelNodeIri: 'g/Node_1' }],
      })
      expect(state.openArcs.get(0)).toBeUndefined()
    })

    it('deleting a bound occurrence drops arcs bound via its terminals', () => {
      let state = applyCommand(initialState, {
        type: 'insertNode', id: 1, iri: 'g/Node_1', label: 'A',
        entityType: 'et:A', parentViewNodeId: 0, x: 0, y: 0,
      })
      state = applyCommand(state, {
        type: 'insertReferencedComposite', id: 2, label: 'ref',
        parentViewNodeId: 0, x: 0, y: 0, refersTo: 'tpl',
        terminals: [{
          iri: 'tpl/oa1', externalIri: 'tpl/Node_9', arcType: '',
          isSource: false, externalEntityType: 'et:A',
        }],
      })
      state = applyCommand(state, {
        type: 'reconnectOpenArc', openArcIri: 'tpl/oa1',
        newModelNodeIri: 'g/Node_1', arcType: TF,
      })
      const bound = state.modelArcs.get('tpl/oa1')
      expect(bound?.via).toBe(2)
      expect(bound?.sourceIri).toBe('tpl/Node_9')

      state = applyCommand(state, {
        type: 'deleteNodes',
        nodes: [{ visibleNodeId: '2', treeNodeId: 2 }],
      })
      expect(state.modelArcs.get('tpl/oa1')).toBeUndefined()
      // the host leaf's end of the binding dies with the occurrence
      expect(state.modelNodes.has('g/Node_1')).toBe(true)
    })
  })

  describe('exposeTerminal / unexposeTerminal', () => {
    it('declares and removes an open arc on the parent composite', () => {
      let state = applyCommand(initialState, {
        type: 'exposeTerminal', iri: 'g/oa1', compositeId: 0,
        modelNodeIri: 'g/Node_1', entityType: 'et:A',
      })
      const oa = state.openArcs.get(0)!
      expect(oa).toHaveLength(1)
      expect(oa[0]).toMatchObject({
        iri: 'g/oa1', externalIri: 'g/Node_1',
        arcType: '', externalEntityType: 'et:A',
      })
      // repeat is a no-op
      state = applyCommand(state, {
        type: 'exposeTerminal', iri: 'g/oa2', compositeId: 0,
        modelNodeIri: 'g/Node_1', entityType: 'et:A',
      })
      expect(state.openArcs.get(0)).toHaveLength(1)
      state = applyCommand(state, {
        type: 'unexposeTerminal', compositeId: 0, openArcIri: 'g/oa1',
      })
      expect(state.openArcs.get(0)).toBeUndefined()
    })
  })
})
