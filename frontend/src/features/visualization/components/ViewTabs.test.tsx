/**
 * Tests for ViewTabs component -- tab rendering and view switching.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { ViewTabs } from './ViewTabs'
import { useVisualizationStore } from '../store'

describe('ViewTabs', () => {
  beforeEach(() => {
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

  it('renders three tabs: Graph, Matrix, Narrative', () => {
    renderWithProviders(
      <ViewTabs
        graphView={<div>Graph content</div>}
        matrixView={<div>Matrix content</div>}
        narrativeView={<div>Narrative content</div>}
      />
    )

    expect(screen.getByRole('tab', { name: 'Graph' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Matrix' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Narrative' })).toBeInTheDocument()
  })

  it('calls setActiveView when a tab is clicked', async () => {
    const user = userEvent.setup()

    renderWithProviders(
      <ViewTabs
        graphView={<div>Graph content</div>}
        matrixView={<div>Matrix content</div>}
        narrativeView={<div>Narrative content</div>}
      />
    )

    await user.click(screen.getByRole('tab', { name: 'Matrix' }))
    expect(useVisualizationStore.getState().activeView).toBe('matrix')

    await user.click(screen.getByRole('tab', { name: 'Narrative' }))
    expect(useVisualizationStore.getState().activeView).toBe('narrative')

    await user.click(screen.getByRole('tab', { name: 'Graph' }))
    expect(useVisualizationStore.getState().activeView).toBe('graph')
  })

  it('shows the active view content', () => {
    renderWithProviders(
      <ViewTabs
        graphView={<div data-testid="graph-view">Graph content</div>}
        matrixView={<div data-testid="matrix-view">Matrix content</div>}
        narrativeView={<div data-testid="narrative-view">Narrative content</div>}
      />
    )

    // Graph is the default active view
    expect(screen.getByTestId('graph-view')).toBeInTheDocument()
  })
})
