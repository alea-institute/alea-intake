/**
 * Tests for GraphCanvas -- Canvas fallback for >200 nodes (D-05).
 */

import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import { GraphCanvas } from './GraphCanvas'
import type { GraphNode, GraphLink } from '@/features/visualization/types'

// Mock useForceSimulation
vi.mock('@/features/visualization/hooks/useForceSimulation', () => ({
  useForceSimulation: (nodes: GraphNode[]) => ({
    positions: nodes.map((n, i) => ({
      ...n,
      x: 50 + i * 10,
      y: 50 + i * 10,
    })),
    simulation: { current: null },
  }),
}))

// Generate 200+ nodes for canvas threshold test
function generateLargeGraph(): { nodes: GraphNode[]; links: GraphLink[] } {
  const nodes: GraphNode[] = []
  const links: GraphLink[] = []
  for (let i = 0; i < 250; i++) {
    nodes.push({
      id: `node-${i}`,
      type: i % 4 === 0 ? 'fact' : i % 4 === 1 ? 'claim' : i % 4 === 2 ? 'element' : 'gap',
      label: `Node ${i}`,
      confidence: 0.5 + Math.random() * 0.5,
    })
  }
  for (let i = 1; i < 50; i++) {
    links.push({
      source: `node-0`,
      target: `node-${i}`,
      confidence: 0.7,
    })
  }
  return { nodes, links }
}

describe('GraphCanvas', () => {
  it('renders <canvas> element for canvas fallback', () => {
    const { nodes, links } = generateLargeGraph()
    const { container } = render(
      <GraphCanvas
        nodes={nodes}
        links={links}
        ghostedNodeIds={new Set()}
        width={800}
        height={600}
      />
    )

    const canvas = container.querySelector('canvas')
    expect(canvas).toBeTruthy()
    expect(canvas?.width).toBe(800)
    expect(canvas?.height).toBe(600)
  })
})
