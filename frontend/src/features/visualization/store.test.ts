/**
 * Tests for useVisualizationStore -- shared filters and per-view state.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { useVisualizationStore } from './store'

describe('useVisualizationStore', () => {
  beforeEach(() => {
    // Reset store to defaults before each test
    useVisualizationStore.setState({
      activeView: 'graph',
      jurisdictionFilter: null,
      claimFilter: [],
      confidenceThreshold: 0,
      showGapsOnly: false,
      graphState: { selectedNodeId: null, zoom: 1, panX: 0, panY: 0 },
      matrixState: { sortBy: 'confidence', selectedCell: null },
      narrativeState: { activeLayers: [], selectedSpanId: null },
    })
  })

  it('initializes with default filters', () => {
    const state = useVisualizationStore.getState()
    expect(state.confidenceThreshold).toBe(0)
    expect(state.activeView).toBe('graph')
    expect(state.claimFilter).toEqual([])
    expect(state.jurisdictionFilter).toBeNull()
  })

  it('setActiveView changes view and preserves per-view state', () => {
    const store = useVisualizationStore
    // Set some graph state first
    store.getState().setGraphState({ selectedNodeId: 'node-1', zoom: 2 })
    expect(store.getState().graphState.selectedNodeId).toBe('node-1')

    // Switch to matrix view
    store.getState().setActiveView('matrix')
    expect(store.getState().activeView).toBe('matrix')

    // Graph state should be preserved
    expect(store.getState().graphState.selectedNodeId).toBe('node-1')
    expect(store.getState().graphState.zoom).toBe(2)
  })

  it('setConfidenceThreshold updates shared filter', () => {
    const store = useVisualizationStore
    store.getState().setConfidenceThreshold(0.5)
    expect(store.getState().confidenceThreshold).toBe(0.5)
  })

  it('setJurisdiction and setClaims update shared filters', () => {
    const store = useVisualizationStore
    store.getState().setJurisdiction('California')
    expect(store.getState().jurisdictionFilter).toBe('California')

    store.getState().setClaims([1, 2, 3])
    expect(store.getState().claimFilter).toEqual([1, 2, 3])
  })

  it('per-view state persists across view switches', () => {
    const store = useVisualizationStore

    // Set state in each view
    store.getState().setGraphState({ selectedNodeId: 'g-1' })
    store.getState().setMatrixState({ sortBy: 'alphabetical' })
    store.getState().setNarrativeState({ activeLayers: [10, 20] })

    // Switch views back and forth
    store.getState().setActiveView('matrix')
    store.getState().setActiveView('narrative')
    store.getState().setActiveView('graph')

    // All per-view state should be preserved
    expect(store.getState().graphState.selectedNodeId).toBe('g-1')
    expect(store.getState().matrixState.sortBy).toBe('alphabetical')
    expect(store.getState().narrativeState.activeLayers).toEqual([10, 20])
  })
})
