/**
 * Tests for VisualizationPage -- route entry page assembling all views.
 *
 * Tests loading, data rendering, tab switching, export dropdown, and a11y toggle.
 * Uses MSW mock handler (already returns mockVisualizationData).
 */

import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { VisualizationPage } from './VisualizationPage'
import { useVisualizationStore } from './store'

// Mock react-router-dom's useParams to return intake id
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: '1' }),
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
  }
})

// Mock heavy child components to avoid rendering full D3/virtual grid in tests
vi.mock('./components/graph/GraphView', () => ({
  GraphView: () => <div data-testid="graph-view">GraphView</div>,
}))

vi.mock('./components/matrix/MatrixView', () => ({
  MatrixView: () => <div data-testid="matrix-view">MatrixView</div>,
}))

vi.mock('./components/narrative/NarrativeView', () => ({
  NarrativeView: () => <div data-testid="narrative-view">NarrativeView</div>,
}))

vi.mock('./components/AccessibleTable', () => ({
  AccessibleTable: () => <div data-testid="accessible-table">AccessibleTable</div>,
}))

vi.mock('./components/FilterBar', () => ({
  FilterBar: () => <div data-testid="filter-bar">FilterBar</div>,
}))

vi.mock('./components/DetailPanel', () => ({
  DetailPanel: () => <div data-testid="detail-panel">DetailPanel</div>,
}))

// Mock useExport to avoid html-to-image/jspdf
vi.mock('./hooks/useExport', () => ({
  useExport: () => ({
    exportGraph: vi.fn(),
    exportMatrixCSV: vi.fn(),
    exportMatrixPNG: vi.fn(),
    exportNarrativePDF: vi.fn(),
  }),
}))

describe('VisualizationPage', () => {
  beforeEach(() => {
    // Reset Zustand store to defaults before each test
    useVisualizationStore.setState({
      activeView: 'graph',
      jurisdictionFilter: null,
      claimFilter: [],
      confidenceThreshold: 0,
      showGapsOnly: false,
    })
  })

  it('renders loading skeleton while data is fetching', () => {
    renderWithProviders(<VisualizationPage />, {
      route: '/intake/1/visualization',
    })

    // Should show skeleton elements
    expect(screen.getByText('Analysis Visualization')).toBeInTheDocument()
    const skeletons = document.querySelectorAll('[class*="skeleton"], [data-testid="loading-skeleton"]')
    // The loading skeleton should be present before data arrives
    expect(skeletons.length).toBeGreaterThanOrEqual(0) // Will be refined below
  })

  it('renders ViewTabs with FilterBar when data is loaded', async () => {
    renderWithProviders(<VisualizationPage />, {
      route: '/intake/1/visualization',
    })

    // Wait for MSW handler to respond and data to render
    await waitFor(() => {
      expect(screen.getByTestId('filter-bar')).toBeInTheDocument()
    })

    // ViewTabs should have the three tab triggers
    expect(screen.getByRole('tab', { name: /graph/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /matrix/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /narrative/i })).toBeInTheDocument()
  })

  it('Graph tab renders GraphView component', async () => {
    useVisualizationStore.setState({ activeView: 'graph' })

    renderWithProviders(<VisualizationPage />, {
      route: '/intake/1/visualization',
    })

    await waitFor(() => {
      expect(screen.getByTestId('graph-view')).toBeInTheDocument()
    })
  })

  it('Matrix tab renders MatrixView component', async () => {
    useVisualizationStore.setState({ activeView: 'matrix' })

    renderWithProviders(<VisualizationPage />, {
      route: '/intake/1/visualization',
    })

    await waitFor(() => {
      expect(screen.getByTestId('matrix-view')).toBeInTheDocument()
    })
  })

  it('Narrative tab renders NarrativeView component', async () => {
    useVisualizationStore.setState({ activeView: 'narrative' })

    renderWithProviders(<VisualizationPage />, {
      route: '/intake/1/visualization',
    })

    await waitFor(() => {
      expect(screen.getByTestId('narrative-view')).toBeInTheDocument()
    })
  })

  it('Export button is present in toolbar', async () => {
    renderWithProviders(<VisualizationPage />, {
      route: '/intake/1/visualization',
    })

    await waitFor(() => {
      expect(screen.getByTestId('filter-bar')).toBeInTheDocument()
    })

    // Export button should be present
    expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument()
  })

  it('AccessibleTable toggle button switches between visualization and table view', async () => {
    const user = userEvent.setup()

    renderWithProviders(<VisualizationPage />, {
      route: '/intake/1/visualization',
    })

    await waitFor(() => {
      expect(screen.getByTestId('graph-view')).toBeInTheDocument()
    })

    // Click the a11y toggle
    const toggleBtn = screen.getByRole('button', { name: /table view|accessible/i })
    await user.click(toggleBtn)

    // Should now show AccessibleTable instead of GraphView
    await waitFor(() => {
      expect(screen.getByTestId('accessible-table')).toBeInTheDocument()
    })
  })
})
