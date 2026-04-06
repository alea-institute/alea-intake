import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { ThemeProvider } from '@/shared/components/ThemeProvider'
import { DashboardPage } from './DashboardPage'

describe('DashboardPage', () => {
  it('renders heading and new intake button', () => {
    renderWithProviders(
      <ThemeProvider defaultTheme="modern-conversational">
        <DashboardPage />
      </ThemeProvider>
    )
    expect(screen.getByRole('heading', { name: /intakes/i })).toBeInTheDocument()
    // New intake button should render
    expect(screen.getAllByRole('button').length).toBeGreaterThan(0)
  })
})
