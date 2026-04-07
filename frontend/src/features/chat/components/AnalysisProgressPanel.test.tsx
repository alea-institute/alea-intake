import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AnalysisProgressPanel } from './AnalysisProgressPanel'

function renderWithCache(data?: unknown) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  if (data) qc.setQueryData(['intake', 's1', 'progress'], data)
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AnalysisProgressPanel sessionId="s1" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AnalysisProgressPanel', () => {
  it('renders nothing when no progress data', () => {
    const { container } = renderWithCache(undefined)
    expect(container.querySelector('[data-testid="progress-skeleton"]')).toBeFalsy()
    expect(container.querySelector('aside')).toBeFalsy()
  })

  it('renders progress bar, percentage, iteration, and next stage when data is loaded', () => {
    renderWithCache({
      stage: 2, totalStages: 5, stageName: 'Fact mapping',
      iteration: 3, completeness: 0.6, nextStage: 'Gap analysis',
    })
    // Progress percentage rendered
    expect(screen.getByText(/60%/)).toBeInTheDocument()
    // Iteration number rendered
    expect(screen.getByText('3')).toBeInTheDocument()
    // Next stage rendered
    expect(screen.getByText(/Gap analysis/)).toBeInTheDocument()
    // Progress bar present
    expect(screen.getByRole('progressbar')).toBeInTheDocument()
  })

  it('progress bar has aria-valuenow', () => {
    renderWithCache({ stage: 1, totalStages: 5, stageName: 'Issue spotting', iteration: 1, completeness: 0.2 })
    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '20')
  })
})
