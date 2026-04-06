import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ChatPage } from './ChatPage'
import { ConnectionBanner } from './components/ConnectionBanner'
import { useAuth } from '@/features/auth/store'
import { useWSStore } from './store'
import type { ReactNode } from 'react'

// Stub WebSocket that auto-connects via microtask
class StubWS {
  static instances: StubWS[] = []
  onopen?: () => void
  onmessage?: (e: { data: string }) => void
  onclose?: (e: { code: number }) => void
  onerror?: () => void
  readyState = 0
  send = vi.fn()
  close = vi.fn()
  url: string
  constructor(url: string) {
    this.url = url
    StubWS.instances.push(this)
    queueMicrotask(() => {
      this.readyState = 1
      this.onopen?.()
    })
  }
}

function renderChatAt(sessionId: string) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  })
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
  return {
    ...render(
      <MemoryRouter initialEntries={[`/chat/${sessionId}`]}>
        <Routes>
          <Route path="/chat/:sessionId" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>,
      { wrapper: Wrapper },
    ),
    queryClient: qc,
  }
}

function renderBanner() {
  return render(<ConnectionBanner />)
}

describe('ChatPage', () => {
  beforeEach(() => {
    StubWS.instances = []
    vi.stubGlobal('WebSocket', StubWS)
    useAuth.getState().setAuth('tok', {
      id: 'u1',
      email: 'a@b',
      role: 'consumer',
      org_id: 'o1',
    })
    useWSStore.setState({ status: 'connecting', ws: null, reconnectAttempt: 0 })
    server.use(
      http.get('http://localhost:3000/api/v1/intakes/s1/messages', () =>
        HttpResponse.json({ items: [] }),
      ),
    )
  })

  it('renders MessageList and ChatInput', async () => {
    renderChatAt('s1')
    await waitFor(() => expect(screen.getByRole('log')).toBeInTheDocument())
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('creates optimistic pending message on send', async () => {
    renderChatAt('s1')
    // Wait for WebSocket to connect (StubWS fires onopen via microtask)
    await waitFor(() => expect(useWSStore.getState().status).toBe('connected'))
    // Now the send button should be enabled
    await userEvent.type(screen.getByRole('textbox'), 'hello{Enter}')
    await waitFor(() => expect(screen.getByText('hello')).toBeInTheDocument())
    // Check the "Sending..." indicator is visible
    expect(screen.getByText(/sending/i)).toBeInTheDocument()
  })
})

describe('ConnectionBanner', () => {
  it('shows banner with aria-live assertive when disconnected', () => {
    useWSStore.setState({ status: 'disconnected', ws: null, reconnectAttempt: 0 })
    renderBanner()
    const banner = screen.getByRole('status')
    expect(banner).toBeInTheDocument()
    expect(banner).toHaveAttribute('aria-live', 'assertive')
  })

  it('shows banner when reconnecting', () => {
    useWSStore.setState({ status: 'reconnecting', ws: null, reconnectAttempt: 2 })
    renderBanner()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('hides banner when connected', () => {
    useWSStore.setState({ status: 'connected', ws: null, reconnectAttempt: 0 })
    renderBanner()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('hides banner when connecting', () => {
    useWSStore.setState({ status: 'connecting', ws: null, reconnectAttempt: 0 })
    renderBanner()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
