import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { ThemeProvider } from '@/shared/components/ThemeProvider'
import { SafetyBanner } from './SafetyBanner'
import { useSafetyUI } from '../store'

function renderSafety(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
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
  beforeEach(() => { useSafetyUI.setState({ drawerOpen: false }) })

  it('renders nothing when no critical alerts', async () => {
    server.use(http.get('/api/v1/intakes/s1/safety', () => HttpResponse.json({ items: [] })))
    const { container } = renderSafety(<SafetyBanner sessionId="s1" />)
    // Wait for query to settle
    await waitFor(() => {
      expect(container.querySelector('[role="alert"]')).toBeNull()
    })
  })

  it('renders banner when critical alert exists', async () => {
    server.use(http.get('/api/v1/intakes/s1/safety', () =>
      HttpResponse.json({ items: [{ tier: 'critical', category: 'dv', message: 'DV detected', resources: [] }] })
    ))
    renderSafety(<SafetyBanner sessionId="s1" />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByText(/safety comes first/i)).toBeInTheDocument()
  })

  it('has NO close button (non-dismissible per D-29)', async () => {
    server.use(http.get('/api/v1/intakes/s1/safety', () =>
      HttpResponse.json({ items: [{ tier: 'critical', category: 'dv', message: 'DV', resources: [] }] })
    ))
    renderSafety(<SafetyBanner sessionId="s1" />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    // No separate close/dismiss button should exist
    expect(screen.queryByRole('button', { name: /close/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument()
  })

  it('opens drawer on click', async () => {
    server.use(http.get('/api/v1/intakes/s1/safety', () =>
      HttpResponse.json({ items: [{ tier: 'critical', category: 'dv', message: 'DV', resources: [] }] })
    ))
    renderSafety(<SafetyBanner sessionId="s1" />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('alert'))
    expect(useSafetyUI.getState().drawerOpen).toBe(true)
  })
})
