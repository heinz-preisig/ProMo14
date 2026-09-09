import { Circle, Line, Text, Group, Rect } from 'react-konva'
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

  if (isComposite) {
    return (
      <Group
        key={obj.id}
        x={obj.x}
        y={obj.y}
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
      {...eventProps}
    >
      {obj.highlight && (
        <Circle
          radius={obj.radius + 4}
          fill="transparent"
          stroke={obj.highlight === 'valid' ? '#2ecc71' : '#e74c3c'}
          strokeWidth={3}
          listening={false}
        />
      )}
      <Circle
        radius={obj.radius}
        fill={obj.fill}
        stroke={obj.stroke}
        strokeWidth={2}
      />
      <Text
        text={obj.label}
        fontSize={12}
        fill={obj.fill === '#3498db' ? '#fff' : '#333'}
        align="center"
        width={obj.radius * 2}
        x={-obj.radius}
        y={-6}
      />
    </Group>
  )
}

function renderArc(
  obj: SceneObject & { kind: 'arc' },
  handlers: SceneInteractionHandlers
) {
  const aPoints = arrowPoints(obj.arrowX, obj.arrowY, obj.arrowAngle)
  return (
    <Group
      key={obj.id}
      onClick={(e: KonvaEventObject<MouseEvent>) => handlers.onClick(obj, e)}
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
