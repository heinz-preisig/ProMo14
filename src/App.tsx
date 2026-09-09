import { useState, useEffect, useMemo, useReducer } from 'react'
import { Stage, Layer, Line, Group } from 'react-konva'
import type { NodeType, ArcType } from './types'
import type { NodeGraphicalDefinition, ArcGraphicalDefinition } from './semantic/contracts'
import { placeholderCatalogue, placeholderRuleResolver } from './semantic/placeholderCatalogue'
import { resolveConnection } from './semantic/connectionService'
import type { Iri } from './semantic/contracts'
import type { Command } from './state/ModelState'
import { computeGraphView } from './tree/computeGraphView'
import type { AppState } from './state/ModelState'
import { initialState, applyCommand } from './state/ModelState'
import { useCanvasEvents } from './canvas/useCanvasEvents'
import { buildScene } from './scene/buildScene'
import { SceneRenderer } from './scene/SceneRenderer'
import type { SceneObject } from './scene/types'

const TOOLBAR_HEIGHT = 40
const BOTTOM_BAR_HEIGHT = 24
const PALETTE_WIDTH = 140

const NODE_TYPES = placeholderCatalogue.getBaseEntities().map((entity) => {
  const g = placeholderCatalogue.getGraphicalDefinition(entity.graphicalDefinitionIri!) as NodeGraphicalDefinition
  return { id: entity.iri, label: entity.label, fill: g.fill, stroke: g.stroke }
})

const ARC_TYPES = placeholderCatalogue.getArcTypes().map((arcType) => {
  const g = placeholderCatalogue.getGraphicalDefinition(arcType.graphicalDefinitionIri!) as ArcGraphicalDefinition
  return { id: arcType.iri, label: arcType.label, stroke: g.stroke, dash: g.dash }
})

function reducer(state: AppState, cmd: Command): AppState {
  // console.log('Command:', cmd)
  return applyCommand(state, cmd)
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState)

  const [draggingOpenArc, setDraggingOpenArc] = useState<{
    openArcIri: string
    fixedX: number
    fixedY: number
    currentX: number
    currentY: number
  } | null>(null)

  // --- Palette state (UI only, not part of model) ---
  const [activeNodeType, setActiveNodeType] = useState<NodeType>('promo:TypeA')
  const [activeArcType, setActiveArcType] = useState<ArcType>('promo:ArcType1')

  const [stageSize, setStageSize] = useState({
    width: window.innerWidth - PALETTE_WIDTH * 2,
    height: window.innerHeight - TOOLBAR_HEIGHT - BOTTOM_BAR_HEIGHT,
  })

  // --- View transform (pan / zoom) ---
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [scale, setScale] = useState(1)

  // --- Hovered node for connection feedback ---
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)
  const [hoveredObject, setHoveredObject] = useState<SceneObject | null>(null)

  // --- Pending connection source (persists across view changes) ---
  const [pendingConnection, setPendingConnection] = useState<{
    sourceModelIri: string
    sourceEntityType: string
  } | null>(null)

  useEffect(() => {
    const handleResize = () => {
      setStageSize({
        width: window.innerWidth - PALETTE_WIDTH * 2,
        height: window.innerHeight - TOOLBAR_HEIGHT - BOTTOM_BAR_HEIGHT,
      })
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // --- Compute current GraphView on demand ---
  const graphView = useMemo(
    () => computeGraphView(state.currentViewNodeId, state.tree, state.modelNodes, state.modelArcs, state.layoutStore, state.openArcs, state.knotStore, stageSize.width, stageSize.height),
    [state.currentViewNodeId, state.tree, state.modelNodes, state.modelArcs, state.layoutStore, state.openArcs, state.knotStore, stageSize.width, stageSize.height]
  )

  // --- Compute connection-rule feedback for hovered target ---
  const { hoveredHighlight, validArcTypes } = useMemo(() => {
    // Use pendingConnection as source if set (cross-view), else selectedVisibleNodeId (same-view)
    const sourceEntityType = pendingConnection?.sourceEntityType
      ?? (state.selectedVisibleNodeId
        ? graphView.nodes.find((n) => n.id === state.selectedVisibleNodeId)?.entityType
        : undefined)
    const hasSource = !!(pendingConnection || state.selectedVisibleNodeId)
    if (!hasSource || !hoveredNodeId || sourceEntityType === undefined) {
      return { hoveredHighlight: null, validArcTypes: [] as Iri[] }
    }
    const targetNode = graphView.nodes.find((n) => n.id === hoveredNodeId)
    if (targetNode?.type !== 'leaf' || !targetNode.entityType) {
      return { hoveredHighlight: null, validArcTypes: [] as Iri[] }
    }
    // Don't show feedback if hovering the pending source itself
    if (pendingConnection && targetNode.modelNodeIri === pendingConnection.sourceModelIri) {
      return { hoveredHighlight: null, validArcTypes: [] as Iri[] }
    }
    const result = resolveConnection(
      sourceEntityType,
      targetNode.entityType,
      placeholderCatalogue,
      placeholderRuleResolver,
    )
    if (result.status === 'forbidden') {
      return { hoveredHighlight: 'invalid' as const, validArcTypes: [] as Iri[] }
    }
    return {
      hoveredHighlight: 'valid' as const,
      validArcTypes: result.connections.map((c) => c.arcTypeIri),
    }
  }, [state.selectedVisibleNodeId, hoveredNodeId, graphView, pendingConnection])

  // --- Three-panel zone boundaries ---
  const leftZoneX = -stageSize.width / 2 + 80
  const rightZoneX = stageSize.width / 2 - 80
  const zoneTop = -stageSize.height / 2
  const zoneBottom = stageSize.height / 2

  // --- Build unified scene object list ---
  const sceneObjects = useMemo(
    () => buildScene({
      graphView,
      selectedNodeId: state.selectedVisibleNodeId,
      selectedArcIri: state.selectedModelArcIri,
      draggingOpenArc,
      hoveredNodeId,
      hoveredHighlight,
      catalogue: placeholderCatalogue,
    }),
    [graphView, state.selectedVisibleNodeId, state.selectedModelArcIri, draggingOpenArc, hoveredNodeId, hoveredHighlight]
  )

  // --- Canvas event handlers (isolated from rendering) ---
  const {
    handleStageClick,
    handleStageRightClick,
    handleStageMouseDown,
    handleStageMouseMove,
    handleStageMouseUp,
    handleStageWheel,
    groupSelectedNodes,
    sceneHandlers,
  } = useCanvasEvents(state, graphView, stageSize, activeNodeType, activeArcType, dispatch, pan, setPan, scale, setScale, setDraggingOpenArc, setHoveredNodeId, setHoveredObject, pendingConnection, setPendingConnection)

  const selectedVisibleNode = graphView.nodes.find((n) => n.id === state.selectedVisibleNodeId)
  const selectedArc = graphView.arcs.find((a) => a.modelArcIri === state.selectedModelArcIri)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%' }}>
      {/* Top bar */}
      <div
        style={{
          height: TOOLBAR_HEIGHT,
          padding: '0 16px',
          background: '#e0e0e0',
          display: 'flex',
          gap: 16,
          alignItems: 'center',
          boxSizing: 'border-box',
        }}
      >
        <strong>ProMo14</strong>
        <span style={{ fontSize: 13, color: '#555' }}>Model: untitled</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, fontSize: 13 }}>
          <span style={{ color: '#555' }}>View: {state.tree.nodes.get(state.currentViewNodeId)?.label ?? 'Root'}</span>
          <button style={{ fontSize: 12 }}>Save</button>
          <button style={{ fontSize: 12 }}>Screenshot</button>
        </div>
      </div>

      {/* Middle area: palette + canvas + properties */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left palette */}
        <div
          style={{
            width: PALETTE_WIDTH,
            background: '#f0f0f0',
            borderRight: '1px solid #ccc',
            padding: 8,
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            boxSizing: 'border-box',
          }}
        >
          <strong style={{ fontSize: 12 }}>Palette</strong>
          <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Select type, then click canvas</div>
          {NODE_TYPES.map((t) => {
            const isActive = activeNodeType === t.id
            return (
              <button
                key={t.id}
                onClick={() => setActiveNodeType(t.id)}
                style={{
                  fontSize: 12,
                  padding: '6px 8px',
                  textAlign: 'left',
                  cursor: 'pointer',
                  background: isActive ? '#fff' : '#e8e8e8',
                  border: isActive ? `2px solid ${t.stroke}` : '1px solid #bbb',
                  borderRadius: 4,
                }}
              >
                <span
                  style={{
                    display: 'inline-block',
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: t.fill,
                    border: `1.5px solid ${t.stroke}`,
                    marginRight: 6,
                    verticalAlign: 'middle',
                  }}
                />
                {t.label}
              </button>
            )
          })}

          <div style={{ marginTop: 8, borderTop: '1px solid #ccc', paddingTop: 8 }}>
            <strong style={{ fontSize: 12 }}>Arc type</strong>
            <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Select type, then connect nodes</div>
            {ARC_TYPES.map((t) => {
              const isActive = activeArcType === t.id
              return (
                <button
                  key={t.id}
                  onClick={() => setActiveArcType(t.id)}
                  style={{
                    fontSize: 12,
                    padding: '6px 8px',
                    textAlign: 'left',
                    cursor: 'pointer',
                    background: isActive ? '#fff' : '#e8e8e8',
                    border: isActive ? `2px solid #333` : '1px solid #bbb',
                    borderRadius: 4,
                    width: '100%',
                  }}
                >
                  <span
                    style={{
                      display: 'inline-block',
                      width: 24,
                      height: 0,
                      borderTop: `2px ${t.dash ? 'dashed' : 'solid'} ${t.stroke}`,
                      marginRight: 6,
                      verticalAlign: 'middle',
                    }}
                  />
                  {t.label}
                </button>
              )
            })}
          </div>

          <div style={{ marginTop: 8, borderTop: '1px solid #ccc', paddingTop: 8 }}>
            <strong style={{ fontSize: 12 }}>Actions</strong>
            <button
              onClick={groupSelectedNodes}
              disabled={!state.selectedVisibleNodeId}
              style={{
                fontSize: 12,
                padding: '6px 8px',
                width: '100%',
                cursor: state.selectedVisibleNodeId ? 'pointer' : 'not-allowed',
                background: state.selectedVisibleNodeId ? '#e8f4fd' : '#eee',
                border: '1px solid #bbb',
                borderRadius: 4,
                marginTop: 4,
              }}
            >
              Group selected
            </button>
            <button
              onClick={() => dispatch({ type: 'reset' })}
              style={{
                fontSize: 12,
                padding: '6px 8px',
                width: '100%',
                cursor: 'pointer',
                background: '#ffebee',
                border: '1px solid #ef9a9a',
                borderRadius: 4,
                marginTop: 8,
                color: '#c62828',
              }}
            >
              Reset all
            </button>
          </div>
        </div>

        {/* Canvas */}
        <Stage
          width={stageSize.width}
          height={stageSize.height}
          onClick={handleStageClick}
          onContextMenu={handleStageRightClick}
          onMouseDown={handleStageMouseDown}
          onMouseMove={handleStageMouseMove}
          onMouseUp={handleStageMouseUp}
          onWheel={handleStageWheel}
          style={{ flex: 1, background: '#fafafa' }}
        >
          {/* Center the coordinate system: (0,0) is at canvas center */}
          <Layer>
            <Group x={stageSize.width / 2 + pan.x} y={stageSize.height / 2 + pan.y} scaleX={scale} scaleY={scale}>
              {/* Three-panel separators */}
              <Line
                points={[leftZoneX, zoneTop, leftZoneX, zoneBottom]}
                stroke="#ccc"
                strokeWidth={1}
                dash={[4, 4]}
                listening={false}
              />
              <Line
                points={[rightZoneX, zoneTop, rightZoneX, zoneBottom]}
                stroke="#ccc"
                strokeWidth={1}
                dash={[4, 4]}
                listening={false}
              />
              <SceneRenderer objects={sceneObjects} handlers={sceneHandlers} />
              {draggingOpenArc && (
                <Line
                  key="open-arc-drag-line"
                  points={[
                    draggingOpenArc.fixedX,
                    draggingOpenArc.fixedY,
                    draggingOpenArc.currentX,
                    draggingOpenArc.currentY,
                  ]}
                  stroke="#c0392b"
                  strokeWidth={2}
                  dash={[4, 4]}
                  listening={false}
                />
              )}
            </Group>
          </Layer>
        </Stage>

        {/* Right properties panel */}
        <div
          style={{
            width: 140,
            background: '#f0f0f0',
            borderLeft: '1px solid #ccc',
            padding: 8,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            boxSizing: 'border-box',
          }}
        >
          <strong style={{ fontSize: 12 }}>Properties</strong>
          {selectedVisibleNode && (
            <div style={{ fontSize: 11 }}>
              <div>ID: {selectedVisibleNode.id}</div>
              <div>Type: {selectedVisibleNode.type}</div>
              {selectedVisibleNode.modelNodeIri && (
                <div>IRI: {selectedVisibleNode.modelNodeIri}</div>
              )}
              {selectedVisibleNode.treeNodeId !== undefined && (
                <div>Tree: {selectedVisibleNode.treeNodeId}</div>
              )}
              <div>x: {selectedVisibleNode.x.toFixed(1)}</div>
              <div>y: {selectedVisibleNode.y.toFixed(1)}</div>
            </div>
          )}
          {selectedArc && (
            <div style={{ fontSize: 11 }}>
              <div>Arc: {selectedArc.modelArcIri}</div>
              <div>Type: {selectedArc.arcType}</div>
              <div>From: {selectedArc.sourceId}</div>
              <div>To: {selectedArc.targetId}</div>
            </div>
          )}
          {validArcTypes.length > 0 && (
            <div style={{ fontSize: 11, borderTop: '1px solid #ccc', paddingTop: 8 }}>
              <strong style={{ fontSize: 12 }}>Valid arc types</strong>
              <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>Click to select, then right-click target</div>
              {validArcTypes.map((arcIri) => {
                const arcDef = ARC_TYPES.find((t) => t.id === arcIri)
                const isActive = activeArcType === arcIri
                return (
                  <button
                    key={arcIri}
                    onClick={() => setActiveArcType(arcIri)}
                    style={{
                      fontSize: 12,
                      padding: '4px 6px',
                      textAlign: 'left',
                      cursor: 'pointer',
                      background: isActive ? '#fff' : '#e8e8e8',
                      border: isActive ? '2px solid #2ecc71' : '1px solid #bbb',
                      borderRadius: 4,
                      width: '100%',
                      marginBottom: 2,
                    }}
                  >
                    {arcDef?.label ?? arcIri}
                  </button>
                )
              })}
            </div>
          )}
          {hoveredHighlight === 'invalid' && (
            <div style={{ fontSize: 11, color: '#c62828', borderTop: '1px solid #ccc', paddingTop: 8 }}>
              Connection not allowed
            </div>
          )}
          {/* Hover info (when nothing is selected) */}
          {!selectedVisibleNode && !selectedArc && hoveredObject && (
            <div style={{ fontSize: 11, borderTop: '1px solid #ccc', paddingTop: 8, color: '#555' }}>
              <strong style={{ fontSize: 12, color: '#333' }}>Hover</strong>
              {hoveredObject.kind === 'node' && (
                <>
                  <div>{hoveredObject.label}</div>
                  <div>Type: {hoveredObject.nodeType}</div>
                  {hoveredObject.entityType && <div>Entity: {hoveredObject.entityType}</div>}
                  {hoveredObject.modelNodeIri && <div>IRI: {hoveredObject.modelNodeIri}</div>}
                  <div>x: {hoveredObject.x.toFixed(1)}, y: {hoveredObject.y.toFixed(1)}</div>
                </>
              )}
              {hoveredObject.kind === 'arc' && (
                <>
                  <div>Arc: {hoveredObject.arcIri}</div>
                </>
              )}
              {hoveredObject.kind === 'knot' && (
                <>
                  <div>Knot #{hoveredObject.knotIndex}</div>
                  <div>Arc: {hoveredObject.arcIri}</div>
                  <div>x: {hoveredObject.x.toFixed(1)}, y: {hoveredObject.y.toFixed(1)}</div>
                </>
              )}
              {hoveredObject.kind === 'openArcHandle' && (
                <>
                  <div>Open arc handle</div>
                  <div>Arc: {hoveredObject.openArcIri}</div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bottom status bar */}
      <div
        style={{
          height: 24,
          padding: '0 16px',
          background: '#e8e8e8',
          display: 'flex',
          alignItems: 'center',
          fontSize: 12,
          borderTop: '1px solid #ccc',
          boxSizing: 'border-box',
        }}
      >
        <span style={{ color: '#555' }}>
          {hoveredHighlight === 'valid'
            ? `Valid target — right-click to connect (${validArcTypes.length} arc type${validArcTypes.length > 1 ? 's' : ''})`
            : hoveredHighlight === 'invalid'
              ? 'Invalid target — connection not allowed'
              : pendingConnection && !state.selectedVisibleNodeId
                ? `Source selected (${pendingConnection.sourceModelIri}) — navigate to target view, right-click a leaf to connect`
                : hoveredObject?.kind === 'knot'
                  ? 'Drag to move — double-click to add knot — right-click to remove'
                  : hoveredObject?.kind === 'arc'
                    ? 'Click to select — Delete to remove'
                    : hoveredObject?.kind === 'openArcHandle'
                      ? 'Drag to reconnect to a nearby node'
                      : hoveredObject?.kind === 'node' && !state.selectedVisibleNodeId
                        ? 'Click to select — double-click to zoom — right-click to connect'
                        : state.selectedVisibleNodeId
                          ? 'Right-click a leaf to connect — double-click composite to zoom — Delete to remove'
                          : state.selectedModelArcIri
                            ? 'Delete to remove — drag knots to route'
                            : 'Click canvas to add node — double-click composite to zoom — Delete to remove'}
        </span>
        <span style={{ marginLeft: 'auto', color: '#555' }}>
          {state.modelNodes.size} model nodes, {state.modelArcs.size} arcs (next node: {state.tree.nextId + 1})
        </span>
      </div>
    </div>
  )
}
