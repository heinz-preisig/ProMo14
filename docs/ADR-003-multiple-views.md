# ADR-003: Multiple GraphView Panels on the Canvas

## Status

Draft — under discussion

## Context

Each tree node in ProMo14 has a corresponding `GraphView` computed by `computeGraphView`. The current UI renders a single GraphView at a time, with ancestors on the left margin, siblings on the right margin, and the current tree node’s children in the center.

For drawing arcs between parts of the model that live in different tree branches, users need to see more than one view at the same time. The proposed solution is to let the user open additional GraphView panels directly on the main canvas, each with the same controls (pan, zoom, select, connect, add node) as the primary view.

## Decision

### 1. Multi-panel canvas

The main canvas becomes a container for one or more `GraphView` panels:

- **Primary panel** — always present, shows the focused tree node (`currentViewNodeId`).
- **Secondary panels** — optional panels the user opens (e.g., by double-clicking an ancestor/sibling while holding a modifier key, or via a palette action).

Each panel has its own:

```typescript
interface GraphViewPanel {
  id: string
  viewNodeId: number       // which tree node is shown
  pan: { x: number; y: number }
  scale: number
}
```

### 2. Flat model stays the single source of truth

`modelNodes` and `modelArcs` remain the only persistent semantic data. Arcs drawn between two panels are still stored in `modelArcs` as `sourceIri → targetIri`. No new "view-level" arc type is introduced.

### 3. Cross-panel arcs

When an arc connects two leaves that are visible in two different open panels, the arc is rendered as a connecting line between those panels. If both endpoints are inside the same panel, the arc is rendered inside that panel as before.

- If an endpoint is not currently open in any panel, the arc is treated as an open end in the panel that owns the visible endpoint (same as the current open-arc logic).
- If the same leaf appears in two open panels, the user can start/finish a connection from either one.

### 4. Independent event handling per panel

Each panel owns a `useCanvasEvents` instance (or equivalent) for its own `viewNodeId`, `pan`, `scale`, and `stageSize`. This keeps the existing event logic isolated and reusable; the canvas event layer does not know about the global model, only about the view it serves.

### 5. Synchronization

Because all `GraphView`s are computed from the same `AppState`, opening a panel is simply adding a `{id, viewNodeId, pan, scale}` entry. Any change to the model or tree automatically propagates to all panels via React re-renders and `useMemo`.

## Alternatives considered

- **Cross-view arcs through margins** (ancestors/siblings in a single view): easier, but quickly becomes crowded and does not scale when the user wants to compare distant branches.
- **View-level arcs between tree nodes**: would add a second arc layer and duplicate semantics. Rejected to keep one flat model graph.

## Consequences

- `AppState` will gain a `panels` array alongside `currentViewNodeId`.
- `App.tsx` will render one `Stage` per panel (or one large `Stage` with multiple `Group`s).
- `useCanvasEvents` will be parameterized to target a specific `viewNodeId`, `pan`, `scale`.
- Keyboard shortcuts and global actions (e.g., Delete, Reset) should act on the active panel.
- Need a way to close panels and to identify the "active" panel for new nodes / connections.

## Next steps

1. Decide whether to use one `Stage` or multiple `Stage`s.
2. Add `panels` and `activePanelId` to `AppState`.
3. Make `useCanvasEvents` accept the panel state it should operate on.
4. Render two panels side-by-side.
5. Allow drawing arcs between visible nodes in different panels.
