import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/shared/components/ThemeProvider'
import { SafetyBanner } from './SafetyBanner'
import { useSafetyUI } from '../store'

let alerts: unknown[] = []
function renderSafety(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  qc.setQueryData(['intake','s1','safety'], alerts)
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider defaultTheme="modern-conversational">
        <MemoryRouter>
          {ui}
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('SafetyBanner', () => {
  beforeEach(() => { alerts = []; useSafetyUI.setState({ drawerOpen: false }) })

  it('renders nothing when no critical alerts', async () => {
    const { container } = renderSafety(<SafetyBanner sessionId="s1" />)
    // Wait for query to settle
    await waitFor(() => {
      expect(container.querySelector('[role="alert"]')).toBeNull()
    })
  })

  it('renders banner when critical alert exists', async () => {
    alerts = [{ tier: 'critical', category: 'dv', message: 'DV detected', resources: [] }]
    renderSafety(<SafetyBanner sessionId="s1" />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText(/safety comes first/i)).toBeInTheDocument()
  })

  it('has NO close button (non-dismissible per D-29)', async () => {
    alerts = [{ tier: 'critical', category: 'dv', message: 'DV', resources: [] }]
    renderSafety(<SafetyBanner sessionId="s1" />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    // No separate close/dismiss button should exist
    expect(screen.queryByRole('button', { name: /close/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument()
  })

  it('opens drawer on click', async () => {
    alerts = [{ tier: 'critical', category: 'dv', message: 'DV', resources: [] }]
    renderSafety(<SafetyBanner sessionId="s1" />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('alert'))
    expect(useSafetyUI.getState().drawerOpen).toBe(true)
  })
})
