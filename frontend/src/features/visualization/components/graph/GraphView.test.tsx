/**
 * Tests for GraphView (SVG container) with GraphNode, GraphLink rendering.
 * Also tests node shape rendering, ARIA, click handling, and ghosted opacity.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GraphView } from './GraphView'
import { useVisualizationStore } from '@/features/visualization/store'
import type { GraphNode, GraphLink } from '@/features/visualization/types'

// Mock useForceSimulation to return deterministic positions
vi.mock('@/features/visualization/hooks/useForceSimulation', () => ({
  useForceSimulation: (nodes: GraphNode[]) => ({
    positions: nodes.map((n, i) => ({
      ...n,
      x: 100 + i * 100,
      y: 200 + i * 50,
    })),
    simulation: { current: { alphaTarget: () => ({ restart: () => {} }), restart: () => {} } },
  }),
}))

const testNodes: GraphNode[] = [
  { id: 'fact-1', type: 'fact', label: 'Broken heater', confidence: 0.9, factId: 1 },
  { id: 'claim-1', type: 'claim', label: 'Warranty of Habitability', confidence: 0.85, claimId: 1 },
  { id: 'element-1', type: 'element', label: 'Defective Condition', confidence: 0.8, elementId: 1 },
  { id: 'gap-1', type: 'gap', label: 'Missing notice evidence', confidence: 0.3, gapId: 1 },
]

const testLinks: GraphLink[] = [
  { source: 'fact-1', target: 'claim-1', confidence: 0.88 },
  { source: 'fact-1', target: 'element-1', confidence: 0.82 },
]

describe('GraphView', () => {
  beforeEach(() => {
    useVisualizationStore.setState({
      graphState: { selectedNodeId: null, zoom: 1, panX: 0, panY: 0 },
    })
  })

  it('renders SVG container with nodes and links when node count < 200', () => {
    const { container } = render(
      <GraphView
        nodes={testNodes}
        links={testLinks}
        ghostedNodeIds={new Set()}
        width={800}
        height={600}
      />
    )

    const svg = container.querySelector('svg')
    expect(svg).toBeTruthy()

    // Should have node groups
    const nodeGroups = container.querySelectorAll('[data-testid^="graph-node-"]')
    expect(nodeGroups.length).toBe(4)

    // Should have link lines
    const linkLines = container.querySelectorAll('[data-testid^="graph-link-"]')
    expect(linkLines.length).toBe(2)
  })

  it('renders facts as circles, claims as rects with rx, elements as polygons per D-02', () => {
    const { container } = render(
      <GraphView
        nodes={testNodes}
        links={testLinks}
        ghostedNodeIds={new Set()}
        width={800}
        height={600}
      />
    )

    // Fact: should have a circle
    const factGroup = container.querySelector('[data-testid="graph-node-fact-1"]')
    expect(factGroup?.querySelector('circle')).toBeTruthy()

    // Claim: should have a rect with rx (rounded)
    const claimGroup = container.querySelector('[data-testid="graph-node-claim-1"]')
    const claimRect = claimGroup?.querySelector('rect')
    expect(claimRect).toBeTruthy()
    expect(claimRect?.getAttribute('rx')).toBeTruthy()

    // Element: should have a polygon (diamond)
    const elemGroup = container.querySelector('[data-testid="graph-node-element-1"]')
    expect(elemGroup?.querySelector('polygon')).toBeTruthy()

    // Gap: should have dashed stroke
    const gapGroup = container.querySelector('[data-testid="graph-node-gap-1"]')
    const gapShape = gapGroup?.querySelector('[stroke-dasharray]')
    expect(gapShape).toBeTruthy()
  })

  it('nodes have ARIA labels with type and confidence per D-14', () => {
    render(
      <GraphView
        nodes={testNodes}
        links={testLinks}
        ghostedNodeIds={new Set()}
        width={800}
        height={600}
      />
    )

    const factNode = screen.getByLabelText(/fact.*broken heater.*90%/i)
    expect(factNode).toBeTruthy()

    const claimNode = screen.getByLabelText(/claim.*warranty of habitability.*85%/i)
    expect(claimNode).toBeTruthy()
  })

  it('clicking a node calls store setGraphState with selectedNodeId', () => {
    const { container } = render(
      <GraphView
        nodes={testNodes}
        links={testLinks}
        ghostedNodeIds={new Set()}
        width={800}
        height={600}
        onNodeClick={(id) => useVisualizationStore.getState().setGraphState({ selectedNodeId: id })}
      />
    )

    const factNode = container.querySelector('[data-testid="graph-node-fact-1"]')
    fireEvent.click(factNode!)

    expect(useVisualizationStore.getState().graphState.selectedNodeId).toBe('fact-1')
  })

  it('ghosted nodes have reduced opacity (0.2)', () => {
    const ghosted = new Set(['claim-1', 'element-1'])
    const { container } = render(
      <GraphView
        nodes={testNodes}
        links={testLinks}
        ghostedNodeIds={ghosted}
        width={800}
        height={600}
      />
    )

    const ghostedNode = container.querySelector('[data-testid="graph-node-claim-1"]')
    expect(ghostedNode?.getAttribute('opacity')).toBe('0.2')

    const normalNode = container.querySelector('[data-testid="graph-node-fact-1"]')
    expect(normalNode?.getAttribute('opacity')).toBe('1')
  })
})
