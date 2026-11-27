import { Circle, Ellipse, Line, Text, Group, Rect, Shape, Ring } from 'react-konva'
import type { KonvaEventObject } from 'konva/lib/Node'
import type { SceneObject, SceneInteractionHandlers } from './types'
import { arrowPoints } from './buildScene'

interface Props {
  objects: SceneObject[]
  handlers: SceneInteractionHandlers
}

export function SceneRenderer({ objects, handlers }: Props) {
  return (
    <>
      {objects.map((obj) => renderObject(obj, handlers))}
    </>
  )
}

function renderObject(
  obj: SceneObject,
  handlers: SceneInteractionHandlers
): React.ReactNode {
  switch (obj.kind) {
    case 'node':
      return renderNode(obj, handlers)
    case 'arc':
      return renderArc(obj, handlers)
    case 'openArc':
      return renderOpenArc(obj)
    case 'openArcHandle':
      return renderHandle(obj, handlers)
    case 'knot':
      return renderKnot(obj, handlers)
    default:
      return null
  }
}

function renderNode(
  obj: SceneObject & { kind: 'node' },
  handlers: SceneInteractionHandlers
) {
  const isComposite = obj.nodeType === 'composite'
  const eventProps: Record<string, unknown> = {}

  if (obj.interactions.clickable) {
    eventProps.onClick = (e: KonvaEventObject<MouseEvent>) => handlers.onClick(obj, e)
  }
  if (obj.interactions.rightClickable) {
    eventProps.onContextMenu = (e: KonvaEventObject<MouseEvent>) => handlers.onRightClick(obj, e)
  }
  if (obj.interactions.doubleClickable) {
    eventProps.onDblClick = (e: KonvaEventObject<MouseEvent>) => handlers.onDoubleClick(obj, e)
  }
  eventProps.onMouseEnter = (e: KonvaEventObject<MouseEvent>) => handlers.onMouseEnter(obj, e)
  eventProps.onMouseLeave = (e: KonvaEventObject<MouseEvent>) => handlers.onMouseLeave(obj, e)
  if (obj.interactions.draggable) {
    eventProps.draggable = true
    eventProps.dragDistance = 10
    eventProps.onDragStart = (e: KonvaEventObject<DragEvent>) => handlers.onDragStart(obj, e)
    eventProps.onDragMove = (e: KonvaEventObject<DragEvent>) => handlers.onDragMove(obj, e)
    eventProps.onDragEnd = (e: KonvaEventObject<DragEvent>) => handlers.onDragEnd(obj, e)
  }

  const opacity = obj.dimmed ? 0.3 : 1

  // Leaf glyph geometry from the node's bounding box — the shape is
  // declared by the archetype graphical; the renderer only knows the
  // half-extent + shape tag (designer graphics reuse this path).
  const he = obj.halfExtent ?? { x: obj.radius, y: obj.radius }
  const shape = obj.shape ?? 'circle'
  const dash = obj.strokeDash

  const glyph = () => {
    switch (shape) {
      case 'ellipse':
        return (
          <Ellipse
            radiusX={he.x}
            radiusY={he.y}
            fill={obj.fill}
            stroke={obj.stroke}
            strokeWidth={2}
            dash={dash}
          />
        )
      case 'rectangle':
      case 'roundedRectangle':
        return (
          <Rect
            width={he.x * 2}
            height={he.y * 2}
            x={-he.x}
            y={-he.y}
            fill={obj.fill}
            stroke={obj.stroke}
            strokeWidth={2}
            dash={dash}
            cornerRadius={shape === 'roundedRectangle' ? 6 : 0}
          />
        )
      case 'diamond':
        return (
          <Line
            points={[0, -he.y, he.x, 0, 0, he.y, -he.x, 0]}
            closed
            fill={obj.fill}
            stroke={obj.stroke}
            strokeWidth={2}
            dash={dash}
          />
        )
      case 'halfCircle':
        // Open dome: top half of a circle, bottom chord left open.
        // The bounding box is r×r/2 — the arc's circle centre sits at
        // (0, he.y) so the dome fills [-he.x..he.x] × [-he.y..he.y].
        return (
          <Shape
            sceneFunc={(ctx, shp) => {
              const r = he.x
              ctx.beginPath()
              ctx.arc(0, he.y, r, Math.PI, 2 * Math.PI, false)
              ctx.closePath()
              ctx.fillShape(shp)
              if (dash) {
                // stroke the arc only (open ends) — dash on the chord
                // would fake a closed boundary.
                ctx.beginPath()
                ctx.arc(0, he.y, r, Math.PI, 2 * Math.PI, false)
                ctx.strokeShape(shp)
              } else {
                ctx.strokeShape(shp)
              }
            }}
            fill={obj.fill}
            stroke={obj.stroke}
            strokeWidth={2}
            dash={dash}
          />
        )
      case 'ring':
        // Annulus — boundary shell.  The label sits in the hole;
        // arcs attach to the outer circle (default rim math).
        return (
          <Ring
            outerRadius={he.x}
            innerRadius={obj.innerRadius ?? he.x * 0.6}
            fill={obj.fill}
            stroke={obj.stroke}
            strokeWidth={2}
            dash={dash}
          />
        )
      case 'circle':
      case 'symbol':
      default:
        return (
          <Circle
            radius={he.x}
            fill={obj.fill}
            stroke={obj.stroke}
            strokeWidth={2}
            dash={dash}
          />
        )
    }
  }

  // Label: the dome is half-height — its name sits under the open side.
  const labelY = shape === 'halfCircle' ? he.y + 4 : -6
  const labelW = Math.max(he.x * 2, obj.radius * 2)

  if (isComposite) {
    return (
      <Group
        key={obj.id}
        x={obj.x}
        y={obj.y}
        opacity={opacity}
        {...eventProps}
      >
        {obj.highlight && (
          <Rect
            width={(obj.width ?? 80) + 8}
            height={(obj.height ?? 60) + 8}
            x={-(obj.width ?? 80) / 2 - 4}
            y={-(obj.height ?? 60) / 2 - 4}
            fill="transparent"
            stroke={obj.highlight === 'valid' ? '#2ecc71' : '#e74c3c'}
            strokeWidth={3}
            cornerRadius={6}
            listening={false}
          />
        )}
        <Rect
          width={obj.width ?? 80}
          height={obj.height ?? 60}
          x={-(obj.width ?? 80) / 2}
          y={-(obj.height ?? 60) / 2}
          fill={obj.fill}
          stroke={obj.stroke}
          strokeWidth={2}
          cornerRadius={4}
        />
        <Text
          text={obj.label}
          fontSize={12}
          fill={obj.fill === '#3498db' ? '#fff' : '#333'}
          align="center"
          width={obj.width ?? 80}
          x={-(obj.width ?? 80) / 2}
          y={-6}
        />
      </Group>
    )
  }

  return (
    <Group
      key={obj.id}
      x={obj.x}
      y={obj.y}
      opacity={opacity}
      {...eventProps}
    >
      {obj.highlight && (
        he.x === he.y ? (
          <Circle
            radius={he.x + 4}
            fill="transparent"
            stroke={obj.highlight === 'valid' ? '#2ecc71' : '#e74c3c'}
            strokeWidth={3}
            listening={false}
          />
        ) : (
          <Rect
            width={he.x * 2 + 8}
            height={he.y * 2 + 8}
            x={-he.x - 4}
            y={-he.y - 4}
            fill="transparent"
            stroke={obj.highlight === 'valid' ? '#2ecc71' : '#e74c3c'}
            strokeWidth={3}
            cornerRadius={6}
            listening={false}
          />
        )
      )}
      {glyph()}
      <Text
        text={obj.label}
        fontSize={12}
        fill={obj.fill === '#3498db' ? '#fff' : '#333'}
        align="center"
        width={labelW}
        x={-labelW / 2}
        y={labelY}
        listening={false}
      />
    </Group>
  )
}

/** Midpoint of the arc's middle segment — anchor for the token label. */
function arcMidpoint(points: number[]): { x: number; y: number } {
  const n = points.length / 2
  const mid = Math.floor((n - 1) / 2)
  return {
    x: (points[2 * mid] + points[2 * mid + 2]) / 2,
    y: (points[2 * mid + 1] + points[2 * mid + 3]) / 2,
  }
}

function renderArc(
  obj: SceneObject & { kind: 'arc' },
  handlers: SceneInteractionHandlers
) {
  const aPoints = arrowPoints(obj.arrowX, obj.arrowY, obj.arrowAngle)
  const tokenPos = obj.token ? arcMidpoint(obj.points) : null
  return (
    <Group
      key={obj.id}
      onClick={(e: KonvaEventObject<MouseEvent>) => handlers.onClick(obj, e)}
      onContextMenu={obj.interactions.rightClickable ? (e: KonvaEventObject<MouseEvent>) => handlers.onRightClick(obj, e) : undefined}
      onDblClick={obj.interactions.doubleClickable ? (e: KonvaEventObject<MouseEvent>) => handlers.onDoubleClick(obj, e) : undefined}
      onMouseEnter={(e: KonvaEventObject<MouseEvent>) => handlers.onMouseEnter(obj, e)}
      onMouseLeave={(e: KonvaEventObject<MouseEvent>) => handlers.onMouseLeave(obj, e)}
    >
      <Line
        points={obj.points}
        stroke="transparent"
        strokeWidth={obj.hitStrokeWidth}
        listening
      />
      <Line
        points={obj.points}
        stroke={obj.stroke}
        strokeWidth={obj.strokeWidth}
        dash={obj.dash}
      />
      <Line
        points={aPoints}
        closed
        fill={obj.stroke}
        stroke={obj.stroke}
        strokeWidth={obj.strokeWidth}
      />
      {tokenPos && (
        <Text
          x={tokenPos.x - 30}
          y={tokenPos.y - 18}
          width={60}
          align="center"
          text={obj.token}
          fontSize={11}
          fill={obj.stroke}
          listening={false}
        />
      )}
    </Group>
  )
}

function renderOpenArc(obj: SceneObject & { kind: 'openArc' }) {
  const aPoints = arrowPoints(obj.arrowX, obj.arrowY, obj.arrowAngle)
  const midX = (obj.points[0] + obj.points[obj.points.length - 2]) / 2
  const midY = (obj.points[1] + obj.points[obj.points.length - 1]) / 2
  return (
    <Group key={obj.id}>
      <Line
        points={obj.points}
        stroke="transparent"
        strokeWidth={obj.hitStrokeWidth}
        listening
      />
      <Line
        points={obj.points}
        stroke="#c0392b"
        strokeWidth={12}
        opacity={0.35}
      />
      <Line
        points={obj.points}
        stroke={obj.stroke}
        strokeWidth={obj.strokeWidth}
        dash={obj.dash}
      />
      <Line
        points={aPoints}
        closed
        fill={obj.stroke}
        stroke={obj.stroke}
        strokeWidth={obj.strokeWidth}
      />
      <Text
        text="OPEN"
        x={midX - 16}
        y={midY - 7}
        fontSize={11}
        fill="#c0392b"
      />
    </Group>
  )
}

function renderKnot(
  obj: SceneObject & { kind: 'knot' },
  handlers: SceneInteractionHandlers
) {
  return (
    <Circle
      key={obj.id}
      x={obj.x}
      y={obj.y}
      radius={obj.radius}
      fill={obj.fill}
      stroke={obj.stroke}
      strokeWidth={obj.strokeWidth}
      draggable
      dragDistance={5}
      onClick={(e: KonvaEventObject<MouseEvent>) => {
        e.cancelBubble = true
        handlers.onClick(obj, e)
      }}
      onDblClick={(e: KonvaEventObject<MouseEvent>) => {
        e.cancelBubble = true
        handlers.onDoubleClick(obj, e)
      }}
      onContextMenu={(e: KonvaEventObject<MouseEvent>) => {
        e.evt.preventDefault()
        e.cancelBubble = true
        handlers.onRightClick(obj, e)
      }}
      onDragStart={(e: KonvaEventObject<DragEvent>) => handlers.onDragStart(obj, e)}
      onDragMove={(e: KonvaEventObject<DragEvent>) => handlers.onDragMove(obj, e)}
      onDragEnd={(e: KonvaEventObject<DragEvent>) => handlers.onDragEnd(obj, e)}
      onMouseEnter={(e: KonvaEventObject<MouseEvent>) => handlers.onMouseEnter(obj, e)}
      onMouseLeave={(e: KonvaEventObject<MouseEvent>) => handlers.onMouseLeave(obj, e)}
    />
  )
}

function renderHandle(
  obj: SceneObject & { kind: 'openArcHandle' },
  handlers: SceneInteractionHandlers
) {
  return (
    <Circle
      key={obj.id}
      x={obj.x}
      y={obj.y}
      radius={obj.radius}
      fill={obj.fill}
      stroke={obj.stroke}
      strokeWidth={obj.strokeWidth}
      shadowColor="#000"
      shadowBlur={4}
      shadowOpacity={0.35}
      draggable
      dragDistance={5}
      onDragStart={(e: KonvaEventObject<DragEvent>) => handlers.onDragStart(obj, e)}
      onDragMove={(e: KonvaEventObject<DragEvent>) => handlers.onDragMove(obj, e)}
      onDragEnd={(e: KonvaEventObject<DragEvent>) => handlers.onDragEnd(obj, e)}
      onClick={(e: KonvaEventObject<MouseEvent>) => {
        e.cancelBubble = true
        handlers.onClick(obj, e)
      }}
    />
  )
}
