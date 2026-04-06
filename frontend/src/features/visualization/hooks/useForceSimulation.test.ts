/**
 * Tests for useForceSimulation and useGraphData hooks.
 *
 * TDD RED phase: all tests written before implementation.
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useForceSimulation } from './useForceSimulation'
import { useGraphData } from './useGraphData'
import { useVisualizationStore } from '@/features/visualization/store'
import { mockVisualizationData } from '@/test/fixtures/visualization'
import type { GraphNode, GraphLink } from '../types'

// ---------------------------------------------------------------------------
// useForceSimulation tests
// ---------------------------------------------------------------------------

describe('useForceSimulation', () => {
  const nodes: GraphNode[] = [
    { id: 'f-1', type: 'fact', label: 'Fact one', confidence: 0.9 },
    { id: 'c-1', type: 'claim', label: 'Claim one', confidence: 0.7 },
    { id: 'e-1', type: 'element', label: 'Element one', confidence: 0.5 },
  ]
  const links: GraphLink[] = [
    { source: 'f-1', target: 'c-1', confidence: 0.8 },
    { source: 'f-1', target: 'e-1', confidence: 0.6 },
  ]

  it('returns positioned nodes with x,y coordinates after simulation ticks', async () => {
    const { result } = renderHook(() =>
      useForceSimulation(nodes, links, 800, 600)
    )

    // Wait for at least one tick to set positions
    await waitFor(() => {
      expect(result.current.positions.length).toBe(3)
      const hasPositions = result.current.positions.every(
        (n) => typeof n.x === 'number' && typeof n.y === 'number'
      )
      expect(hasPositions).toBe(true)
    })
  })

  it('stops simulation on unmount (no setState after unmount)', () => {
    const { result, unmount } = renderHook(() =>
      useForceSimulation(nodes, links, 800, 600)
    )

    // Simulation ref should exist
    expect(result.current.simulation).toBeDefined()
    expect(result.current.simulation.current).toBeDefined()

    // Unmount should stop the simulation
    unmount()

    // After unmount, the simulation should have been stopped
    // We verify by checking that no errors are thrown (no setState after unmount)
  })

  it('clones nodes before passing to simulation (input arrays not mutated)', async () => {
    const inputNodes: GraphNode[] = [
      { id: 'a', type: 'fact', label: 'A', confidence: 0.5 },
      { id: 'b', type: 'claim', label: 'B', confidence: 0.5 },
    ]
    const inputLinks: GraphLink[] = [
      { source: 'a', target: 'b', confidence: 0.5 },
    ]

    // Snapshot original state
    const nodesSnapshot = JSON.stringify(inputNodes)
    const linksSnapshot = JSON.stringify(inputLinks)

    renderHook(() => useForceSimulation(inputNodes, inputLinks, 400, 400))

    // Wait a bit for simulation ticks
    await new Promise((r) => setTimeout(r, 100))

    // Original input arrays must not have been mutated
    expect(JSON.stringify(inputNodes)).toBe(nodesSnapshot)
    expect(JSON.stringify(inputLinks)).toBe(linksSnapshot)
  })
})

// ---------------------------------------------------------------------------
// useGraphData tests
// ---------------------------------------------------------------------------

describe('useGraphData', () => {
  // Set up store with default filter state before each test
  afterEach(() => {
    // Reset store to defaults
    useVisualizationStore.setState({
      jurisdictionFilter: null,
      claimFilter: [],
      confidenceThreshold: 0,
      showGapsOnly: false,
    })
  })

  it('transforms VisualizationData into GraphNode[] and GraphLink[] arrays', () => {
    const { result } = renderHook(() => useGraphData(mockVisualizationData))

    expect(Array.isArray(result.current.nodes)).toBe(true)
    expect(Array.isArray(result.current.links)).toBe(true)
    expect(result.current.nodes.length).toBeGreaterThan(0)
    expect(result.current.links.length).toBeGreaterThan(0)
  })

  it('creates nodes for facts, claims, elements, and gaps with correct types', () => {
    const { result } = renderHook(() => useGraphData(mockVisualizationData))

    const types = new Set(result.current.nodes.map((n) => n.type))
    expect(types.has('fact')).toBe(true)
    expect(types.has('claim')).toBe(true)
    expect(types.has('element')).toBe(true)
    expect(types.has('gap')).toBe(true)

    // Check counts match fixture data
    const factNodes = result.current.nodes.filter((n) => n.type === 'fact')
    expect(factNodes.length).toBe(mockVisualizationData.facts.length)

    const claimNodes = result.current.nodes.filter((n) => n.type === 'claim')
    expect(claimNodes.length).toBe(mockVisualizationData.claims.length)

    const gapNodes = result.current.nodes.filter((n) => n.type === 'gap')
    expect(gapNodes.length).toBe(mockVisualizationData.gaps.length)

    // Elements: flatten from all claims
    const totalElements = mockVisualizationData.claims.reduce(
      (sum, c) => sum + c.elements.length,
      0
    )
    const elemNodes = result.current.nodes.filter((n) => n.type === 'element')
    expect(elemNodes.length).toBe(totalElements)
  })

  it('creates links from mappings (fact->claim, fact->element) with confidence scores', () => {
    const { result } = renderHook(() => useGraphData(mockVisualizationData))

    // Should have links from mappings
    const links = result.current.links

    // Each mapping creates a fact->claim link, and if element_id exists, a fact->element link
    const factClaimLinks = links.filter(
      (l) =>
        (typeof l.source === 'string' ? l.source : l.source.id).startsWith('fact-') &&
        (typeof l.target === 'string' ? l.target : l.target.id).startsWith('claim-')
    )
    expect(factClaimLinks.length).toBeGreaterThan(0)

    // Links should have confidence
    links.forEach((l) => {
      expect(typeof l.confidence).toBe('number')
    })
  })

  it('marks filtered nodes as ghosted rather than removing them', () => {
    // Set confidence threshold to filter out lower-confidence items
    useVisualizationStore.setState({ confidenceThreshold: 0.80 })

    const { result } = renderHook(() => useGraphData(mockVisualizationData))

    // All nodes should still be present (not removed)
    const totalExpectedNodes =
      mockVisualizationData.facts.length +
      mockVisualizationData.claims.length +
      mockVisualizationData.claims.reduce((s, c) => s + c.elements.length, 0) +
      mockVisualizationData.gaps.length

    expect(result.current.nodes.length).toBe(totalExpectedNodes)

    // Some nodes should be ghosted (those below threshold)
    expect(result.current.ghostedNodeIds.size).toBeGreaterThan(0)

    // Check: wrongful eviction claim has confidence 0.60, should be ghosted
    expect(result.current.ghostedNodeIds.has('claim-202')).toBe(true)
  })
})
