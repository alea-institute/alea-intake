/**
 * SVG link (edge) component for force-directed graph.
 *
 * Renders <line> with stroke opacity and width proportional to confidence.
 */

import type { GraphNode } from '../../types'

interface GraphLinkProps {
  source: GraphNode & { x: number; y: number }
  target: GraphNode & { x: number; y: number }
  confidence: number
  index: number
}

export function GraphLink({ source, target, confidence, index }: GraphLinkProps) {
  return (
    <line
      data-testid={`graph-link-${index}`}
      x1={source.x}
      y1={source.y}
      x2={target.x}
      y2={target.y}
      stroke="var(--color-border, #666)"
      strokeOpacity={0.3 + confidence * 0.7}
      strokeWidth={1 + confidence * 2}
      pointerEvents="none"
    />
  )
}
