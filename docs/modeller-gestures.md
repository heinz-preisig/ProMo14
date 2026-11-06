# Modeller gesture map

Canonical list of canvas gestures in `apps/modeller`.  Gestures are
decided by the **interaction automaton** in `canvas/interaction.ts`
— a pure `transition(mode, event, ctx) → {next, outputs}` table the
Konva adapter (`useCanvasEvents.ts`) feeds and executes.  Dead
gestures emit `swallowed` outputs (console.debug) instead of silent
returns.  Keep this doc in sync with the table.

## Canvas (empty stage)

- **Click** — insert a node of the armed palette type (plain click only;
  modifiers suppressed, 300 ms debounce)
- **Right-click** — clear selection, cancel pending connection
- **Middle-drag** — pan; **wheel** — zoom
- **Shift+drag** — marquee select (leaf and composite centres inside
  the rect; Ctrl adds to the selection)
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
- **Ctrl+click** — toggle in the multi-selection (same rule as leaves)
- **Right-click** — select (Properties, Extract, Ungroup, Dissolve)
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

Left-click arms a source (automaton mode `armed`); right-click on a
leaf connects it **and re-arms the target** — repeated right-clicks
build node → node → node.  Without an explicit arm, the current
leaf selection acts as the implicit source.

An armed gesture dies on **any view change** (zoom, `◂ back`,
breadcrumb) — cross-boundary connects must go through terminals,
not through a forgotten arm.  **Escape** disarms and clears the
selection.

## Panels and actions

- Palette click arms a node type; Submodels click stamps a copy
  (Ctrl+click for the referenced composite — see below)
- Actions: **Extract to submodel** (composite → artefact + `refersTo`),
  **Group** (prompts for a name), **Ungroup** (in-doc comps — children
  move up, shell removed), **Reset all**
- Properties: **Label** (rename any selected node), Fixes, reference
  **Overrides** + **Dissolve** (sever `refersTo`, one-way inline)
- Header `View:` — rename the composite currently open

## Reference view (inside a referenced artefact)

Read-only: pan, zoom, and descending into composites/nested references
stay live; every mutating gesture emits `swallowed('reference view —
read-only')`. `◂ back` in the header returns to the host view.

## Palette (Submodels)

- **Click a line** — stamp an editable **copy** (fresh ids + IRIs;
  ordinary host content, fully editable)
- **Ctrl+click a line** — insert a **referenced** composite
  (`refersTo`; read-only inside; terminals materialised from the
  artefact's declared interface)
