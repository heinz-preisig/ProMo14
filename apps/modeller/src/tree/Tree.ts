import type { TreeNode, Tree as TreeState } from '../types'

/**
 * Tree operations adapted from treeid.py.
 * Wraps the immutable Tree state with mutation helpers.
 */
export class TreeOps {
  private tree: TreeState

  constructor(tree: TreeState) {
    // Deep clone to ensure immutability
    this.tree = {
      rootId: tree.rootId,
      nextId: tree.nextId,
      nodes: new Map([...tree.nodes].map(([id, node]) => [id, { ...node, children: [...node.children] }])),
    }
  }

  /** Return the current state (for useState updates). */
  getState(): TreeState {
    return this.tree
  }

  /** Return a new TreeOps with cloned state (for immutable updates). */
  clone(): TreeOps {
    return new TreeOps(this.tree)
  }

  /** Add a child to the given parent. Returns the new child's ID. */
  addChild(parentId: number, label: string, iri?: string, explicitId?: number): number {
    const newId = explicitId ?? this.tree.nextId + 1
    const parent = this.tree.nodes.get(parentId)
    if (!parent) throw new Error(`Parent ${parentId} not found`)

    const newNode: TreeNode = {
      id: newId,
      parentId,
      children: [],
      label,
      iri,
    }

    this.tree.nodes.set(newId, newNode)
    parent.children.push(newId)
    this.tree.nextId = Math.max(this.tree.nextId, newId)

    return newId
  }

  /** Get all ancestors of a node (parent first, then grandparent, ... up to root). */
  getAncestors(nodeId: number): number[] {
    const node = this.tree.nodes.get(nodeId)
    if (!node) return []

    const ancestors: number[] = []
    let current = node.parentId
    while (current !== null) {
      ancestors.push(current)
      const parent = this.tree.nodes.get(current)
      current = parent?.parentId ?? null
    }
    return ancestors
  }

  /** Get all siblings of a node (children of parent excluding self). */
  getSiblings(nodeId: number): number[] {
    const node = this.tree.nodes.get(nodeId)
    if (!node || node.parentId === null) return []

    const parent = this.tree.nodes.get(node.parentId)
    if (!parent) return []

    return parent.children.filter((id) => id !== nodeId)
  }

  /** Check if a node is a leaf (no children). */
  isLeaf(nodeId: number): boolean {
    const node = this.tree.nodes.get(nodeId)
    return node ? node.children.length === 0 : false
  }

  /** Get all leaves in the tree. */
  getLeaves(): number[] {
    const leaves: number[] = []
    for (const [id, node] of this.tree.nodes) {
      if (node.children.length === 0) leaves.push(id)
    }
    return leaves
  }

  /** Get all descendants of a node (recursive). */
  getDescendants(nodeId: number): number[] {
    const node = this.tree.nodes.get(nodeId)
    if (!node) return []

    const result: number[] = []
    const queue = [...node.children]
    while (queue.length > 0) {
      const id = queue.shift()!
      result.push(id)
      const child = this.tree.nodes.get(id)
      if (child) queue.push(...child.children)
    }
    return result
  }

  /** Remove a leaf node from the tree. Returns true if removed. */
  removeNode(nodeId: number): boolean {
    const node = this.tree.nodes.get(nodeId)
    if (!node) return false
    if (node.children.length > 0) return false // can only remove leaves

    // Remove from parent's children
    if (node.parentId !== null) {
      const parent = this.tree.nodes.get(node.parentId)
      if (parent) {
        parent.children = parent.children.filter((id) => id !== nodeId)
      }
    }

    // Remove from nodes map
    this.tree.nodes.delete(nodeId)
    return true
  }

  /** Move a node (and its subtree) to a new parent. */
  moveID(nodeId: number, newParentId: number): void {
    const node = this.tree.nodes.get(nodeId)
    if (!node) throw new Error(`Node ${nodeId} not found`)
    if (nodeId === this.tree.rootId) throw new Error('Cannot move root')

    // Remove from old parent's children
    if (node.parentId !== null) {
      const oldParent = this.tree.nodes.get(node.parentId)
      if (oldParent) {
        oldParent.children = oldParent.children.filter((id) => id !== nodeId)
      }
    }

    // Add to new parent's children
    const newParent = this.tree.nodes.get(newParentId)
    if (!newParent) throw new Error(`New parent ${newParentId} not found`)
    newParent.children.push(nodeId)
    node.parentId = newParentId
  }

  /** Find the common ancestor of two nodes (closest to both). */
  getCommonAncestor(a: number, b: number): number | null {
    if (a === b) return a

    const aPath = new Set([a, ...this.getAncestors(a)])
    const bAncestors = [b, ...this.getAncestors(b)]

    for (const id of bAncestors) {
      if (aPath.has(id)) return id
    }
    return null
  }

  /** Get the path from a node up to the common ancestor (inclusive of node, exclusive of ancestor). */
  getPathToAncestor(nodeId: number, ancestorId: number): number[] {
    const path: number[] = []
    let current: number | null = nodeId

    while (current !== null && current !== ancestorId) {
      path.push(current)
      const node = this.tree.nodes.get(current)
      current = node?.parentId ?? null
    }

    return path
  }
}

/** Create a new empty tree with a root node. */
export function createTree(rootLabel = 'Root'): TreeState {
  return {
    rootId: 0,
    nextId: 0,
    nodes: new Map([
      [0, { id: 0, parentId: null, children: [], label: rootLabel }],
    ]),
  }
}
