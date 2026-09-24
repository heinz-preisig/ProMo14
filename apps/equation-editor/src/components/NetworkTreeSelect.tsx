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
  // True roots: keys no other key lists as a child.  The backend hangs
  // every parentless network under 'root', so this is normally just
  // ['root'] — rendering root's children again as top-level nodes would
  // duplicate every branch below the fold.
  const childNames = new Set(Object.values(tree).flat())
  const top = Object.keys(tree).filter((k) => !childNames.has(k))

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
