import type { Command } from '../state/ModelState'
import type { GraphView } from '../types'

/**
 * The canvas interaction automaton.
 *
 * Every modal decision that used to live as an implicit flag
 * (pendingConnection, isMarquee, inRef early-returns) is now a pure
 * transition on an explicit mode.  The hook layer is a thin adapter:
 * it normalises Konva events into `Event`, calls `transition`, then
 * runs the emitted outputs (commands → dispatch; effects → async
 * work like connection-rule resolution or ref-doc loading).
 *
 * `swallowed` outputs replace the old silent `return`s — a dead
 * click now says *why* it died.
 */

export interface Pt { x: number; y: number }
export interface Mods { ctrl: boolean; shift: boolean }

export type Mode =
  | { name: 'idle' }
  /** Connect gesture armed — a leaf was clicked/right-clicked and
   *  awaits its target.  Carries the source endpoint. */
  | { name: 'armed'; source: { modelIri: string; entityType: string } }
  /** Shift+drag rubber band in flight. */
  | { name: 'marquee'; origin: Pt; rect: { x: number; y: number; w: number; h: number } }

export const initialInteraction: Mode = { name: 'idle' }

/** View-chrome = ancestor/sibling/connector render nodes. */
export type NodeKind = 'leaf' | 'composite' | 'chrome'

export interface NodeCtx {
  kind: NodeKind
  id: string
  treeNodeId?: number
  modelNodeIri?: string
  entityType?: string
}

export type Event =
  | { kind: 'stageClick'; point: Pt; mods: Mods }
  | { kind: 'nodeClick'; node: NodeCtx; mods: Mods }
  | { kind: 'arcClick'; iri: string }
  | { kind: 'knotClick'; arcIri: string }
  | { kind: 'stageRightClick' }
  | { kind: 'nodeRightClick'; node: NodeCtx }
  | { kind: 'arcRightClick'; arcIri: string; carrier: string | null }
  | { kind: 'knotRightClick'; arcIri: string; knotIndex: number }
  | { kind: 'nodeDoubleClick'; node: NodeCtx; isRef: boolean }
  | { kind: 'arcDoubleClick'; arcIri: string; point: Pt }
  | { kind: 'knotDoubleClick'; arcIri: string; point: Pt }
  | { kind: 'marqueeStart'; point: Pt }
  | { kind: 'marqueeMove'; point: Pt }
  | { kind: 'marqueeEnd'; point: Pt; mods: Mods }
  | { kind: 'dragStartNode'; node: NodeCtx }
  | { kind: 'keyDelete' }
  | { kind: 'keyEscape' }
  | { kind: 'keyReverse' }
  | { kind: 'viewChanged' }

/** Read-only inputs the transition consults — no writes. */
export interface Ctx {
  inRef: boolean
  selectedIds: string[]
  selectedId: string | null
  selectedArcIri: string | null
  selectedArcCarrier: string | null
  graphView: GraphView
}

export type Output =
  | { kind: 'cmd'; cmd: Command }
  /** Adapter mints the IRI/id, clamps to the panel, dispatches. */
  | { kind: 'insertNode'; point: Pt }
  /** Async connection-rule resolution, then insertArc (+ re-arm). */
  | { kind: 'connect'; source: { modelIri: string; entityType: string }; target: { modelIri: string; entityType: string }; chained: boolean }
  /** Adapter resolves the ref scope and navigates. */
  | { kind: 'enterComposite'; treeNodeId: number }
  /** A gesture that did nothing — with the reason. */
  | { kind: 'swallowed'; reason: string }

const cmd = (c: Command): Output => ({ kind: 'cmd', cmd: c })
const swallow = (reason: string): Output => ({ kind: 'swallowed', reason })
const RO = 'reference view — read-only'

export function transition(
  mode: Mode,
  ev: Event,
  ctx: Ctx,
): { next: Mode; out: Output[] } {
  const idle = { next: { name: 'idle' } as Mode }

  // Events legal inside the read-only reference view are navigation
  // only — everything else is swallowed with the reason.
  const ro = () => ({ next: mode, out: [swallow(RO)] })

  switch (ev.kind) {
    case 'stageClick': {
      if (ctx.inRef) return ro()
      if (ev.mods.ctrl || ev.mods.shift) {
        return { next: mode, out: [swallow('modifier click on empty stage')] }
      }
      // Inserting a node also disarms a pending connect.
      return { ...idle, out: [{ kind: 'insertNode', point: ev.point }] }
    }

    case 'nodeClick': {
      const n = ev.node
      if (n.kind === 'leaf') {
        if (ctx.inRef) return ro()
        if (ev.mods.ctrl || ev.mods.shift) {
          return { next: mode, out: [cmd({ type: 'toggleSelectNode', id: n.id })] }
        }
        // Plain click: select and arm this leaf as connect source.
        const next: Mode = n.modelNodeIri && n.entityType
          ? { name: 'armed', source: { modelIri: n.modelNodeIri, entityType: n.entityType } }
          : mode
        return { next, out: [cmd({ type: 'selectNode', id: n.id })] }
      }
      // composite / chrome with a tree id
      if (n.treeNodeId === undefined) {
        return { next: mode, out: [swallow('node without tree id')] }
      }
      if (ev.mods.ctrl || ev.mods.shift) {
        if (ctx.inRef) return ro()
        return { next: mode, out: [cmd({ type: 'toggleSelectNode', id: n.id })] }
      }
      // Plain click navigates — legal inside the reference view.
      return { next: mode, out: [{ kind: 'enterComposite', treeNodeId: n.treeNodeId }] }
    }

    case 'arcClick':
      if (ctx.inRef) return ro()
      return { next: mode, out: [cmd({ type: 'selectArc', iri: ev.iri })] }

    case 'knotClick':
      if (ctx.inRef) return ro()
      return { next: mode, out: [cmd({ type: 'selectArc', iri: ev.arcIri ?? null })] }

    case 'stageRightClick':
      if (ctx.inRef) return ro()
      // Deselect and disarm.
      return { ...idle, out: [cmd({ type: 'selectNode', id: null })] }

    case 'nodeRightClick': {
      const n = ev.node
      // §13 (2026-11-06): armed completion writes a HOST arc — legal
      // inside a referenced view (the ref stays untouched; the
      // foreign endpoint is a boundary crossing like extract's).
      // Every other gesture in ref view stays read-only.
      const refCompletion = ctx.inRef && mode.name === 'armed'
        && n.kind === 'leaf' && !!n.modelNodeIri && !!n.entityType
      if (ctx.inRef && !refCompletion) return ro()

      if (mode.name === 'armed') {
        if (n.kind === 'leaf' && n.modelNodeIri && n.entityType) {
          if (n.modelNodeIri === mode.source.modelIri) {
            // Right-click on the armed source: cancel the gesture.
            return { ...idle, out: [cmd({ type: 'selectNode', id: null })] }
          }
          if (ctx.inRef) {
            // No chained re-arm from a foreign leaf — the next hop
            // could bind two artefact-internal nodes, which the host
            // must not own.  Finish and idle instead.
            return {
              ...idle,
              out: [{
                kind: 'connect',
                source: mode.source,
                target: { modelIri: n.modelNodeIri, entityType: n.entityType },
                chained: false,
              }],
            }
          }
          // Connect and re-arm on the target — chained connect.
          return {
            next: { name: 'armed', source: { modelIri: n.modelNodeIri, entityType: n.entityType } },
            out: [
              {
                kind: 'connect',
                source: mode.source,
                target: { modelIri: n.modelNodeIri, entityType: n.entityType },
                chained: true,
              },
              cmd({ type: 'selectNode', id: n.id }),
            ],
          }
        }
        // Non-leaf target under an armed gesture: select it, keep armed.
        return { next: mode, out: [cmd({ type: 'selectNode', id: n.id })] }
      }

      // Idle: a selected leaf acts as the implicit connect source.
      if (ctx.selectedId && ctx.selectedId !== n.id) {
        const src = ctx.graphView.nodes.find((g) => g.id === ctx.selectedId)
        if (
          src?.type === 'leaf' && src.modelNodeIri && src.entityType
          && n.kind === 'leaf' && n.modelNodeIri && n.entityType
        ) {
          return {
            ...idle,
            out: [
              {
                kind: 'connect',
                source: { modelIri: src.modelNodeIri, entityType: src.entityType },
                target: { modelIri: n.modelNodeIri, entityType: n.entityType },
                chained: false,
              },
              cmd({ type: 'selectNode', id: null }),
            ],
          }
        }
        if (n.kind === 'leaf') {
          return { ...idle, out: [cmd({ type: 'selectNode', id: null })] }
        }
        // Non-leaf target: fall through to plain select below.
      }

      if (n.kind === 'leaf' && n.modelNodeIri && n.entityType) {
        return {
          next: { name: 'armed', source: { modelIri: n.modelNodeIri, entityType: n.entityType } },
          out: [cmd({ type: 'selectNode', id: n.id })],
        }
      }
      return { next: mode, out: [cmd({ type: 'selectNode', id: n.id })] }
    }

    case 'arcRightClick':
      if (ctx.inRef) return ro()
      if (ev.carrier === 'token-flow') {
        return { next: mode, out: [cmd({ type: 'reverseArcOrientation', iri: ev.arcIri })] }
      }
      return { next: mode, out: [swallow(`arc is ${ev.carrier ?? 'untyped'} — only token-flow arcs reverse`)] }

    case 'knotRightClick':
      if (ctx.inRef) return ro()
      return { next: mode, out: [cmd({ type: 'removeKnot', arcIri: ev.arcIri, knotIndex: ev.knotIndex })] }

    case 'nodeDoubleClick': {
      const n = ev.node
      if (ctx.inRef) {
        // Nested navigation stays legal; a referenced composite's
        // first click already navigated — double-firing would desync.
        if (ev.isRef) return { next: mode, out: [swallow('ref composite — first click navigated')] }
        if (n.kind !== 'leaf' && n.treeNodeId !== undefined) {
          return { next: mode, out: [{ kind: 'enterComposite', treeNodeId: n.treeNodeId }] }
        }
        return ro()
      }
      if (n.kind === 'leaf') return { next: mode, out: [swallow('double-click on leaf')] }
      if (n.treeNodeId === undefined) return { next: mode, out: [swallow('node without tree id')] }
      if (ev.isRef) return { next: mode, out: [swallow('ref composite — first click navigated')] }
      return { next: mode, out: [{ kind: 'enterComposite', treeNodeId: n.treeNodeId }] }
    }

    case 'arcDoubleClick':
      if (ctx.inRef) return ro()
      return { next: mode, out: [cmd({ type: 'addKnot', arcIri: ev.arcIri, x: ev.point.x, y: ev.point.y })] }

    case 'knotDoubleClick':
      if (ctx.inRef) return ro()
      return { next: mode, out: [cmd({ type: 'addKnot', arcIri: ev.arcIri, x: ev.point.x, y: ev.point.y })] }

    case 'marqueeStart':
      if (ctx.inRef) return ro()
      return {
        next: { name: 'marquee', origin: ev.point, rect: { x: ev.point.x, y: ev.point.y, w: 0, h: 0 } },
        out: [],
      }

    case 'marqueeMove': {
      if (mode.name !== 'marquee') return { next: mode, out: [swallow('move outside marquee')] }
      const o = mode.origin
      return {
        next: {
          name: 'marquee',
          origin: o,
          rect: {
            x: Math.min(o.x, ev.point.x),
            y: Math.min(o.y, ev.point.y),
            w: Math.abs(ev.point.x - o.x),
            h: Math.abs(ev.point.y - o.y),
          },
        },
        out: [],
      }
    }

    case 'marqueeEnd': {
      if (mode.name !== 'marquee') return { next: mode, out: [swallow('mouseup outside marquee')] }
      const m = mode.rect
      if (m.w <= 2 && m.h <= 2) {
        return { ...idle, out: [swallow('marquee too small')] }
      }
      const boxed = ctx.graphView.nodes
        .filter((n) =>
          (n.type === 'leaf' || n.type === 'composite') &&
          n.x >= m.x && n.x <= m.x + m.w &&
          n.y >= m.y && n.y <= m.y + m.h)
        .map((n) => n.id)
      const ids = ev.mods.ctrl ? [...ctx.selectedIds, ...boxed] : boxed
      return { ...idle, out: [cmd({ type: 'selectNodes', ids })] }
    }

    case 'dragStartNode': {
      if (ctx.inRef) return ro()
      // Dragging an unselected node selects it first (standard).
      if (!ctx.selectedIds.includes(ev.node.id)) {
        return { next: mode, out: [cmd({ type: 'selectNode', id: ev.node.id })] }
      }
      return { next: mode, out: [] }
    }

    case 'keyDelete': {
      if (ctx.inRef) return ro()
      const nodes = ctx.selectedIds
        .map((id) => ctx.graphView.nodes.find((n) => n.id === id))
        .filter((n): n is NonNullable<typeof n> =>
          n !== undefined && n.treeNodeId !== undefined
          && (n.type === 'leaf' || n.type === 'composite'))
        .map((n) => ({ visibleNodeId: n.id, treeNodeId: n.treeNodeId!, modelNodeIri: n.modelNodeIri }))
      if (nodes.length) return { next: mode, out: [cmd({ type: 'deleteNodes', nodes })] }
      if (ctx.selectedArcIri) return { next: mode, out: [cmd({ type: 'deleteArc', iri: ctx.selectedArcIri })] }
      return { next: mode, out: [swallow('delete with empty selection')] }
    }

    case 'keyEscape':
      // Clear the selection AND disarm a pending connect.
      return { ...idle, out: [cmd({ type: 'selectNodes', ids: [] })] }

    case 'keyReverse':
      if (ctx.inRef) return ro()
      if (ctx.selectedArcIri && ctx.selectedArcCarrier === 'token-flow') {
        return { next: mode, out: [cmd({ type: 'reverseArcOrientation', iri: ctx.selectedArcIri })] }
      }
      return { next: mode, out: [swallow('r without a selected token-flow arc')] }

    case 'viewChanged':
      // §13 (2026-11-06): an armed connect is branch-independent —
      // old ProMo's beginArc/finishArc.  The armed source is a model
      // IRI, not a view object, so it survives navigation; every
      // other mid-flight gesture still dies with the view.
      return mode.name === 'armed'
        ? { next: mode, out: [] }
        : { ...idle, out: [] }
  }
}

/**
 * Hotkeys belong to the canvas — a keystroke aimed at a form
 * control (rename fields, dialog inputs) must not reach the
 * automaton.  The window listener bails on editable targets;
 * without this, Backspace in the rename box deletes the selected
 * subtree and 'r' fires keyReverse mid-typing.
 */
export function editableTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null
  return !!el && (
    el.tagName === 'INPUT' ||
    el.tagName === 'TEXTAREA' ||
    el.tagName === 'SELECT' ||
    el.isContentEditable === true)
}
