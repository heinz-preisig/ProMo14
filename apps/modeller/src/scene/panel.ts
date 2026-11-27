// ---------------------------------------------------------------------------
// Canonical panel — the centre region where model children live, declared in
// scene coordinates (origin at panel centre).  Stored layout positions are
// canonical: the same model document renders identically on every screen.
// The canvas adapts by scaling the view, never by stretching the layout.
// The backend (backend/modeller/service.py) clamps to the same box — the
// constants there must stay in sync.
// ---------------------------------------------------------------------------

export const PANEL = {
  left: -620,
  right: 620,
  top: -320,
  bottom: 320,
} as const

/** Margin strip depth outside the panel — ancestors render left of
 *  ``PANEL.left``, siblings right of ``PANEL.right``, connectors above
 *  ``PANEL.top``. */
export const MARGIN_DEPTH = 80

/** Full scene extent (panel + margins + small outer pad) — the region
 *  fit-to-view scales to. */
export const SCENE = {
  left: PANEL.left - MARGIN_DEPTH - 60,
  right: PANEL.right + MARGIN_DEPTH + 60,
  top: PANEL.top - MARGIN_DEPTH - 60,
  bottom: PANEL.bottom + MARGIN_DEPTH + 60,
} as const

export const PANEL_WIDTH = PANEL.right - PANEL.left
export const PANEL_HEIGHT = PANEL.bottom - PANEL.top
export const SCENE_WIDTH = SCENE.right - SCENE.left
export const SCENE_HEIGHT = SCENE.bottom - SCENE.top

/** Centre of the margins' free column, inside their strip. */
export const MARGIN_X_LEFT = PANEL.left - MARGIN_DEPTH / 2
export const MARGIN_X_RIGHT = PANEL.right + MARGIN_DEPTH / 2
/** Vertical anchor for margin rows — they stack from the scene top. */
export const MARGIN_TOP = SCENE.top + 60
/** Connector lane just above the panel. */
export const CONNECTOR_Y = PANEL.top - MARGIN_DEPTH / 2

const clamp = (v: number, lo: number, hi: number) =>
  Math.max(lo, Math.min(hi, v))

/** Clamp a node centre so the whole bounding box stays inside the panel.
 *  ``halfW``/``halfH`` is the node's graphical half-extent. */
export function clampToPanelBox(
  x: number, y: number, halfW: number, halfH: number,
): { x: number; y: number } {
  return {
    x: clamp(x, PANEL.left + halfW, PANEL.right - halfW),
    y: clamp(y, PANEL.top + halfH, PANEL.bottom - halfH),
  }
}

/** Inset used for stored positions where the node size isn't known at
 *  clamp time (load, backend) — comfortably covers the largest leaf
 *  glyph (env dome r=30, transport 56×40). */
export const STORED_INSET = 40

/** Clamp a stored layout point into the panel — used on load and on the
 *  backend PUT, where half-extents aren't resolvable. */
export function clampStoredPoint(x: number, y: number): { x: number; y: number } {
  return clampToPanelBox(x, y, STORED_INSET, STORED_INSET)
}
