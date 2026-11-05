# Modeller gesture map

Canonical list of canvas gestures in `apps/modeller` — keep in sync
with `canvas/useCanvasEvents.ts` and the status-bar hints in `App.tsx`.

## Canvas (empty stage)

- **Click** — insert a node of the armed palette type (plain click only;
  modifiers suppressed, 300 ms debounce)
- **Right-click** — clear selection, cancel pending connection
- **Middle-drag** — pan; **wheel** — zoom
- **Shift+drag** — marquee select (leaf centres inside the rect only;
  Ctrl adds to the selection)
- **Delete/Backspace** — remove selection

## Leaf node

- **Click** — select + arm as connection source
- **Ctrl/Shift+click** — toggle in the multi-selection
- **Right-click** — connect armed/selected source to this leaf; without
  a source it selects + arms the leaf
- **Drag** — move (clamped to the centre panel)
- **Double-click** — nothing (leaf tree nodes have no interior)

## Composite

- **Click** — open/navigate in (referenced composite → read-only
  reference view; `◂ back` returns)
- **Ctrl+click or right-click** — select (Properties, Extract,
  Ungroup, Dissolve)
- **Drag** — move
- **Double-click** — same as click (navigate)

## Arc / knot / boundary terminal

- **Arc click** — select; **right-click** — reverse direction
  (token-flow only); **double-click** — add knot at point;
  **Delete** — remove
- **Knot drag** — move; **right-click** — remove
- **Open-arc handle drag** — reposition; drop on a leaf —
  `reconnectOpenArc`

## Connect chaining

Left-click arms a source; right-click on a leaf connects it **and
arms the target** — repeated right-clicks build node → node → node.

## Panels and actions

- Palette click arms a node type; Submodels click inserts a referenced
  composite (terminals materialised from the artefact's interface)
- Actions: **Extract to submodel** (composite → artefact + `refersTo`),
  **Group** (prompts for a name), **Ungroup** (in-doc comps — children
  move up, shell removed), **Reset all**
- Properties: **Label** (rename any selected node), Fixes, reference
  **Overrides** + **Dissolve** (sever `refersTo`, one-way inline)
- Header `View:` — rename the composite currently open

## Reference view (inside a referenced artefact)

Read-only: pan, zoom, and descending into composites/nested references
stay live; every mutating gesture is suppressed. `◂ back` in the
header returns to the host view.
