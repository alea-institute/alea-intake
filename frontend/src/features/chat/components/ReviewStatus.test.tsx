import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { ReviewStatus } from './ReviewStatus'
import type { ReviewStatusState } from '../types'

describe('ReviewStatus', () => {
  it('shows "Legal professional is reviewing" when status=reviewing', () => {
    const status: ReviewStatusState = {
      status: 'reviewing',
      label: 'Legal professional is reviewing',
    }
    renderWithProviders(<ReviewStatus reviewStatus={status} />)
    expect(screen.getByText(/legal professional is reviewing/i)).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows "Analysis paused for review" when status=paused', () => {
    const status: ReviewStatusState = {
      status: 'paused',
      label: 'Analysis paused for review',
    }
    renderWithProviders(<ReviewStatus reviewStatus={status} />)
    expect(screen.getByText(/analysis paused for review/i)).toBeInTheDocument()
  })

  it('is hidden when status=idle', () => {
    const status: ReviewStatusState = {
      status: 'idle',
      label: '',
    }
    const { container } = renderWithProviders(<ReviewStatus reviewStatus={status} />)
    // Should render nothing
    expect(container.textContent).toBe('')
  })

  it('has ARIA role=status for accessibility', () => {
    const status: ReviewStatusState = {
      status: 'reviewing',
      label: 'Legal professional is reviewing',
    }
    renderWithProviders(<ReviewStatus reviewStatus={status} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})
