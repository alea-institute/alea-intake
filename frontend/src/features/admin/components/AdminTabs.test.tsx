import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { AdminTabs } from './AdminTabs'

describe('AdminTabs', () => {
  it('renders 7 tab triggers', () => {
    renderWithProviders(<AdminTabs />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(7)
  })

  it('Organization tab is active by default', () => {
    renderWithProviders(<AdminTabs />)
    const orgTab = screen.getByRole('tab', { name: /organization/i })
    expect(orgTab).toHaveAttribute('data-state', 'active')
  })

  it('clicking Research Tools tab switches active content', async () => {
    renderWithProviders(<AdminTabs />)
    const researchTab = screen.getByRole('tab', { name: /research/i })
    await userEvent.click(researchTab)
    expect(researchTab).toHaveAttribute('data-state', 'active')
  })
})
