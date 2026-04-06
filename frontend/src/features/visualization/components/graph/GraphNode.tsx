/**
 * SVG node component for force-directed graph (D-02).
 *
 * Renders shape by node type:
 *   - fact: circle (r proportional to confidence)
 *   - claim: rounded rectangle (rx=4)
 *   - element: diamond polygon (4 points)
 *   - gap: circle with dashed stroke border
 *
 * Color from NODE_TYPE_COLORS palette. Ghosted nodes at 0.2 opacity.
 * ARIA: role="img", aria-label with type/label/confidence, tabIndex=0.
 * Mobile: 44px minimum hit target via invisible larger circle.
 */

import { NODE_TYPE_COLORS } from '../../palette'
import type { GraphNode as GraphNodeType } from '../../types'

interface GraphNodeProps {
  node: GraphNodeType & { x: number; y: number }
  ghosted: boolean
  selected: boolean
  onClick: (id: string) => void
}

export function GraphNode({ node, ghosted, selected, onClick }: GraphNodeProps) {
  const x = node.x
  const y = node.y
  const color = NODE_TYPE_COLORS[node.type]
  const opacity = ghosted ? 0.2 : 1
  const confidencePercent = Math.round(node.confidence * 100)
  const ariaLabel = `${node.type}: ${node.label}, confidence ${confidencePercent}%`

  // Truncate label for display
  const displayLabel =
    node.label.length > 15 ? node.label.slice(0, 15) + '...' : node.label

  function handleClick() {
    onClick(node.id)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onClick(node.id)
    }
  }

  return (
    <g
      data-testid={`graph-node-${node.id}`}
      opacity={opacity}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="img"
      aria-label={ariaLabel}
      tabIndex={0}
      style={{ cursor: 'pointer', outline: 'none' }}
    >
      {/* Invisible hit target for mobile (44px min) */}
      <circle
        cx={x}
        cy={y}
        r={22}
        fill="transparent"
        stroke="none"
        pointerEvents="all"
      />

      {/* Actual shape */}
      {node.type === 'fact' && (
        <FactShape x={x} y={y} confidence={node.confidence} color={color} selected={selected} />
      )}
      {node.type === 'claim' && (
        <ClaimShape x={x} y={y} confidence={node.confidence} color={color} selected={selected} />
      )}
      {node.type === 'element' && (
        <ElementShape x={x} y={y} confidence={node.confidence} color={color} selected={selected} />
      )}
      {node.type === 'gap' && (
        <GapShape x={x} y={y} confidence={node.confidence} color={color} selected={selected} />
      )}

      {/* Label text below node */}
      <text
        x={x}
        y={y + (node.type === 'claim' ? 25 + node.confidence * 10 : 20 + node.confidence * 10)}
        textAnchor="middle"
        fontSize={10}
        fill="currentColor"
        pointerEvents="none"
      >
        {displayLabel}
      </text>
    </g>
  )
}

// ---------------------------------------------------------------------------
// Shape sub-components
// ---------------------------------------------------------------------------

interface ShapeProps {
  x: number
  y: number
  confidence: number
  color: string
  selected: boolean
}

/** Fact: circle with r proportional to confidence */
function FactShape({ x, y, confidence, color, selected }: ShapeProps) {
  const r = 6 + confidence * 14
  return (
    <circle
      cx={x}
      cy={y}
      r={r}
      fill={color}
      stroke={selected ? '#fff' : 'none'}
      strokeWidth={selected ? 2 : 0}
    />
  )
}

/** Claim: rounded rectangle proportional to confidence */
function ClaimShape({ x, y, confidence, color, selected }: ShapeProps) {
  const w = 20 + confidence * 30
  const h = 14 + confidence * 16
  return (
    <rect
      x={x - w / 2}
      y={y - h / 2}
      width={w}
      height={h}
      rx={4}
      ry={4}
      fill={color}
      stroke={selected ? '#fff' : 'none'}
      strokeWidth={selected ? 2 : 0}
    />
  )
}

/** Element: diamond (4-point polygon) */
function ElementShape({ x, y, confidence, color, selected }: ShapeProps) {
  const size = 8 + confidence * 12
  const points = [
    `${x},${y - size}`,       // top
    `${x + size},${y}`,       // right
    `${x},${y + size}`,       // bottom
    `${x - size},${y}`,       // left
  ].join(' ')
  return (
    <polygon
      points={points}
      fill={color}
      stroke={selected ? '#fff' : 'none'}
      strokeWidth={selected ? 2 : 0}
    />
  )
}

/** Gap: circle with dashed border (no fill) */
function GapShape({ x, y, confidence, color }: ShapeProps) {
  const r = 6 + confidence * 14
  return (
    <circle
      cx={x}
      cy={y}
      r={r}
      fill="none"
      stroke={color}
      strokeWidth={2}
      strokeDasharray="4,2"
    />
  )
}
