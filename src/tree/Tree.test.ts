import { describe, it, expect } from 'vitest'
import { TreeOps, createTree } from './Tree'

describe('TreeOps', () => {
  describe('addChild', () => {
    it('adds a child to the root', () => {
      const tree = new TreeOps(createTree())
      const childId = tree.addChild(0, 'Child')
      expect(childId).toBe(1)
      expect(tree.getState().nodes.get(1)).toEqual({
        id: 1, parentId: 0, children: [], label: 'Child',
      })
      expect(tree.getState().nodes.get(0)?.children).toEqual([1])
    })

    it('adds multiple children', () => {
      const tree = new TreeOps(createTree())
      const a = tree.addChild(0, 'A')
      const b = tree.addChild(0, 'B')
      expect(a).toBe(1)
      expect(b).toBe(2)
      expect(tree.getState().nodes.get(0)?.children).toEqual([1, 2])
    })
  })

  describe('getAncestors', () => {
    it('returns empty for root', () => {
      const tree = new TreeOps(createTree())
      expect(tree.getAncestors(0)).toEqual([])
    })

    it('returns parent for child of root', () => {
      const tree = new TreeOps(createTree())
      tree.addChild(0, 'A')
      expect(tree.getAncestors(1)).toEqual([0])
    })

    it('returns ancestors in order (parent, grandparent, ...)', () => {
      const tree = new TreeOps(createTree())
      const a = tree.addChild(0, 'A')
      const b = tree.addChild(a, 'B')
      const c = tree.addChild(b, 'C')
      expect(tree.getAncestors(c)).toEqual([b, a, 0])
    })
  })

  describe('getSiblings', () => {
    it('returns empty for root', () => {
      const tree = new TreeOps(createTree())
      expect(tree.getSiblings(0)).toEqual([])
    })

    it('returns siblings excluding self', () => {
      const tree = new TreeOps(createTree())
      const a = tree.addChild(0, 'A')
      const b = tree.addChild(0, 'B')
      expect(tree.getSiblings(a)).toEqual([b])
      expect(tree.getSiblings(b)).toEqual([a])
    })
  })

  describe('isLeaf', () => {
    it('root is leaf when no children', () => {
      const tree = new TreeOps(createTree())
      expect(tree.isLeaf(0)).toBe(true)
    })

    it('child without children is leaf', () => {
      const tree = new TreeOps(createTree())
      const a = tree.addChild(0, 'A')
      expect(tree.isLeaf(a)).toBe(true)
      expect(tree.isLeaf(0)).toBe(false)
    })
  })

  describe('getDescendants', () => {
    it('returns all descendants', () => {
      const tree = new TreeOps(createTree())
      const a = tree.addChild(0, 'A')   // 1
      const b = tree.addChild(a, 'B')   // 2
      const c = tree.addChild(a, 'C')   // 3
      const d = tree.addChild(b, 'D')   // 4

      expect(tree.getDescendants(0)).toEqual([a, b, c, d])
      expect(tree.getDescendants(a)).toEqual([b, c, d])
      expect(tree.getDescendants(b)).toEqual([d])
    })
  })

  describe('moveID', () => {
    it('moves a node to a new parent', () => {
      const tree = new TreeOps(createTree())
      const a = tree.addChild(0, 'A')
      const b = tree.addChild(0, 'B')
      const c = tree.addChild(a, 'C')

      tree.moveID(c, b)

      expect(tree.getState().nodes.get(a)?.children).toEqual([])
      expect(tree.getState().nodes.get(b)?.children).toEqual([c])
      expect(tree.getState().nodes.get(c)?.parentId).toBe(b)
    })
  })

  describe('getCommonAncestor', () => {
    it('returns self for same node', () => {
      const tree = new TreeOps(createTree())
      expect(tree.getCommonAncestor(0, 0)).toBe(0)
    })

    it('returns parent for siblings', () => {
      const tree = new TreeOps(createTree())
      const a = tree.addChild(0, 'A')
      const b = tree.addChild(0, 'B')
      expect(tree.getCommonAncestor(a, b)).toBe(0)
    })

    it('returns grandparent for cousins', () => {
      const tree = new TreeOps(createTree())
      const a = tree.addChild(0, 'A')
      const b = tree.addChild(0, 'B')
      const c = tree.addChild(a, 'C')
      const d = tree.addChild(b, 'D')
      expect(tree.getCommonAncestor(c, d)).toBe(0)
    })
  })
})
