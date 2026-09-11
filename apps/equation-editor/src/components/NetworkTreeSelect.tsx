import { useState } from 'react'
import type { NetworkTree } from '../types'

export interface NetworkTreeSelectProps {
  tree: NetworkTree
  selected: string
  onSelect: (network: string) => void
}

function childrenOf(tree: NetworkTree, parent: string): string[] {
  return tree[parent] ?? []
}

function TreeNode({
  name,
  tree,
  selected,
  onSelect,
  depth,
}: {
  name: string
  tree: NetworkTree
  selected: string
  onSelect: (network: string) => void
  depth: number
}) {
  const [expanded, setExpanded] = useState(true)
  const children = childrenOf(tree, name)
  const isSelected = name === selected

  return (
    <div>
      <div
        onClick={() => onSelect(name)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: '2px 4px',
          marginLeft: depth * 16,
          cursor: 'pointer',
          borderRadius: 3,
          background: isSelected ? '#bbdefb' : 'transparent',
          fontWeight: isSelected ? 'bold' : 'normal',
          fontSize: 12,
        }}
      >
        {children.length > 0 && (
          <span
            onClick={(e) => {
              e.stopPropagation()
              setExpanded((x) => !x)
            }}
            style={{ userSelect: 'none', width: 12 }}
          >
            {expanded ? '▾' : '▸'}
          </span>
        )}
        {children.length === 0 && <span style={{ width: 12 }} />}
        {name}
      </div>
      {expanded && children.length > 0 && (
        <div>
          {children.map((child) => (
            <TreeNode
              key={child}
              name={child}
              tree={tree}
              selected={selected}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function NetworkTreeSelect({
  tree,
  selected,
  onSelect,
}: NetworkTreeSelectProps) {
  const roots = childrenOf(tree, 'root')
  // If 'root' is not the only root or user can select it, include it.
  const top = ['root', ...roots.filter((r) => r !== 'root')]

  return (
    <div
      style={{
        border: '1px solid #ccc',
        borderRadius: 4,
        padding: 4,
        maxHeight: 160,
        overflowY: 'auto',
        background: '#fff',
      }}
    >
      {top.map((r) => (
        <TreeNode
          key={r}
          name={r}
          tree={tree}
          selected={selected}
          onSelect={onSelect}
          depth={0}
        />
      ))}
    </div>
  )
}
