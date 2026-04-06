import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { IntakeTable } from './IntakeTable'

const sample = [
  {
    id: 'i1',
    matterId: 'M-0001',
    consumerName: 'Jane Doe',
    areaOfLaw: 'Family',
    jurisdiction: 'CA',
    status: 'in_progress' as const,
    lastActivity: '2026-04-01T00:00:00Z',
    completeness: 0.6,
  },
]

describe('IntakeTable', () => {
  it('renders rows with matter ID, consumer, status, completeness', () => {
    renderWithProviders(<IntakeTable intakes={sample} />)
    expect(screen.getByText('M-0001')).toBeInTheDocument()
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByText(/60%/)).toBeInTheDocument()
  })

  it('row is keyboard-activatable', () => {
    renderWithProviders(<IntakeTable intakes={sample} />)
    // i18n fallback in test env renders the key template, not the interpolated string
    const row = screen.getByLabelText(/open intake/i)
    expect(row).toHaveAttribute('tabindex', '0')
    expect(row).toHaveAttribute('role', 'button')
  })
})
