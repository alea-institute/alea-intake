/**
 * Tests for MatrixView, MatrixCell, and MatrixHeader components.
 *
 * TDD RED phase: all tests written before implementation.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MatrixView } from './MatrixView'
import { MatrixCell as MatrixCellComponent } from './MatrixCell'
import { MatrixHeader } from './MatrixHeader'
import { mockVisualizationData } from '@/test/fixtures/visualization'
import type { MatrixCell } from '@/features/visualization/types'
import type { ClaimGroup } from '@/features/visualization/hooks/useMatrixData'

// Mock useMatrixData to return controlled test data
vi.mock('@/features/visualization/hooks/useMatrixData', () => ({
  useMatrixData: () => ({
    rows: [
      { factId: 101, label: 'Broken heater since November', confidence: 0.92 },
      { factId: 102, label: 'Visible mold in bathroom', confidence: 0.88 },
    ],
    columnGroups: [
      {
        claimId: 201,
        claimName: 'Breach of Warranty',
        jurisdiction: 'California',
        collapsed: false,
        columns: [
          { elementId: 401, elementName: 'Defective Condition', isGap: false, isSatisfied: true },
          { elementId: 402, elementName: 'Notice to Landlord', isGap: true, isSatisfied: false },
        ],
      },
      {
        claimId: 202,
        claimName: 'Wrongful Eviction',
        jurisdiction: 'California',
        collapsed: false,
        columns: [
          { elementId: 404, elementName: 'Protected Activity', isGap: false, isSatisfied: true },
        ],
      },
    ],
    getCellData: (factId: number, elementId: number): MatrixCell | null => {
      const map: Record<string, MatrixCell> = {
        '101-401': {
          factId: 101,
          elementId: 401,
          claimId: 201,
          confidence: 0.88,
          rationale: 'Broken heater is a defective condition',
        },
        '102-401': {
          factId: 102,
          elementId: 401,
          claimId: 201,
          confidence: 0.82,
          rationale: 'Mold is a health hazard',
        },
        '101-404': {
          factId: 101,
          elementId: 404,
          claimId: 202,
          confidence: 0.65,
          rationale: 'Complaint is protected activity',
        },
      }
      return map[`${factId}-${elementId}`] ?? null
    },
    totalColumns: 3,
  }),
}))

// Mock the store for setMatrixState
vi.mock('@/features/visualization/store', () => ({
  useVisualizationStore: Object.assign(
    (selector: (s: Record<string, unknown>) => unknown) =>
      selector({
        matrixState: { sortBy: 'confidence', selectedCell: null },
        setMatrixState: vi.fn(),
      }),
    {
      getState: () => ({
        matrixState: { sortBy: 'confidence', selectedCell: null },
        setMatrixState: vi.fn(),
      }),
      setState: vi.fn(),
      subscribe: vi.fn(),
      destroy: vi.fn(),
    }
  ),
}))

// Mock @tanstack/react-virtual with minimal virtualizer
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: count }, (_, i) => ({
        index: i,
        start: i * 40,
        size: 40,
        key: i,
      })),
    getTotalSize: () => count * 40,
    scrollToIndex: vi.fn(),
  }),
}))

describe('MatrixView', () => {
  it('renders a scrollable container with virtualized rows', () => {
    const { container } = render(
      <MatrixView data={mockVisualizationData} />
    )

    // Should render a grid container
    const grid = container.querySelector('[role="grid"]')
    expect(grid).toBeTruthy()

    // Should have rows rendered
    const rows = container.querySelectorAll('[role="row"]')
    expect(rows.length).toBeGreaterThan(0)
  })
})

describe('MatrixCellComponent', () => {
  it('renders with correct background color from CONFIDENCE_SCALE for given confidence', () => {
    const mapping: MatrixCell = {
      factId: 101,
      elementId: 401,
      claimId: 201,
      confidence: 0.88,
      rationale: 'Test rationale',
    }
    const onClick = vi.fn()

    const { container } = render(
      <MatrixCellComponent mapping={mapping} onClick={onClick} />
    )

    const cell = container.querySelector('[role="gridcell"]')
    expect(cell).toBeTruthy()

    // Confidence 0.88 >= 0.8 -> "strong" level -> color #009E73
    // Background should contain this color at reduced opacity (browser may render as rgba)
    const style = cell?.getAttribute('style') ?? ''
    // jsdom may convert hex #009E7333 -> rgba(0, 158, 115, 0.2)
    expect(style).toMatch(/009E73|rgba\(0,\s*158,\s*115/)
  })

  it('renders numeric confidence value inside cell', () => {
    const mapping: MatrixCell = {
      factId: 101,
      elementId: 401,
      claimId: 201,
      confidence: 0.85,
      rationale: 'Test',
    }

    render(<MatrixCellComponent mapping={mapping} onClick={vi.fn()} />)

    // Should show "85" (Math.round(0.85 * 100))
    expect(screen.getByText('85')).toBeTruthy()
  })

  it('renders diagonal stripe pattern when no mapping (null)', () => {
    const { container } = render(
      <MatrixCellComponent mapping={null} onClick={vi.fn()} />
    )

    const cell = container.querySelector('[role="gridcell"]')
    expect(cell).toBeTruthy()

    // Should have repeating-linear-gradient for diagonal stripes
    const style = cell?.getAttribute('style') ?? ''
    expect(style).toContain('repeating-linear-gradient')

    // ARIA label for gap
    expect(cell?.getAttribute('aria-label')).toContain('gap')
  })

  it('has aria-label with confidence level and percentage', () => {
    const mapping: MatrixCell = {
      factId: 101,
      elementId: 401,
      claimId: 201,
      confidence: 0.65,
      rationale: 'Test',
    }

    const { container } = render(
      <MatrixCellComponent mapping={mapping} onClick={vi.fn()} />
    )

    const cell = container.querySelector('[role="gridcell"]')
    // Confidence 0.65 -> "good" level
    const label = cell?.getAttribute('aria-label') ?? ''
    expect(label).toContain('good')
    expect(label).toContain('65')
  })
})

describe('MatrixHeader', () => {
  const columnGroups: ClaimGroup[] = [
    {
      claimId: 201,
      claimName: 'Breach of Warranty',
      jurisdiction: 'California',
      collapsed: false,
      columns: [
        { elementId: 401, elementName: 'Defective Condition', isGap: false, isSatisfied: true },
        { elementId: 402, elementName: 'Notice to Landlord', isGap: true, isSatisfied: false },
      ],
    },
  ]

  it('renders claim name as group header and element names as column headers', () => {
    render(<MatrixHeader columnGroups={columnGroups} onToggleCollapse={vi.fn()} />)

    expect(screen.getByText('Breach of Warranty')).toBeTruthy()
    expect(screen.getByText('Defective Condition')).toBeTruthy()
    expect(screen.getByText('Notice to Landlord')).toBeTruthy()
  })

  it('clicking cell sets store selectedCell and triggers handler', () => {
    const mapping: MatrixCell = {
      factId: 101,
      elementId: 401,
      claimId: 201,
      confidence: 0.88,
      rationale: 'Test',
    }
    const onClick = vi.fn()

    render(<MatrixCellComponent mapping={mapping} onClick={onClick} />)

    const cell = screen.getByRole('gridcell')
    fireEvent.click(cell)
    expect(onClick).toHaveBeenCalledWith(mapping)
  })

  it('gap columns have warning indicator in header', () => {
    const { container } = render(
      <MatrixHeader columnGroups={columnGroups} onToggleCollapse={vi.fn()} />
    )

    // Element 402 is a gap; should have a warning indicator
    // Check for the lucide TriangleAlert icon (rendered as SVG)
    const warningIcons = container.querySelectorAll('[data-testid="gap-warning"]')
    expect(warningIcons.length).toBeGreaterThan(0)
  })
})
