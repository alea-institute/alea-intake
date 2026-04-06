import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { createElement } from 'react'
import { useWebSocket } from './useWebSocket'
import { useWSStore } from '../store'

// Minimal WebSocket mock — fires onopen asynchronously via queueMicrotask
// (survives fake timers since microtasks are not affected by vi.useFakeTimers)
class MockWebSocket {
  static instances: MockWebSocket[] = []
  url: string
  readyState = 0
  onopen?: () => void
  onmessage?: (e: { data: string }) => void
  onclose?: (e: { code: number }) => void
  onerror?: () => void
  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
    queueMicrotask(() => {
      this.readyState = 1
      this.onopen?.()
    })
  }
  send = vi.fn()
  close(code = 1000) {
    this.readyState = 3
    this.onclose?.({ code })
  }
  simulate(event: unknown) {
    this.onmessage?.({ data: JSON.stringify(event) })
  }
}

function makeWrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children)
}

describe('useWebSocket', () => {
  let qc: QueryClient
  beforeEach(() => {
    vi.stubGlobal('WebSocket', MockWebSocket)
    MockWebSocket.instances = []
    useWSStore.setState({ status: 'connecting', ws: null, reconnectAttempt: 0 })
    qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  })
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('connects to correct URL with token', async () => {
    renderHook(() => useWebSocket('s1', 'tok-abc'), { wrapper: makeWrapper(qc) })
    await waitFor(() =>
      expect(MockWebSocket.instances[0].url).toContain('/api/ws/intake/s1?token=tok-abc'),
    )
  })

  it('transitions to connected status on open', async () => {
    renderHook(() => useWebSocket('s1', 'tok'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(useWSStore.getState().status).toBe('connected'))
  })

  it('resets reconnect attempt on open', async () => {
    renderHook(() => useWebSocket('s1', 'tok'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(useWSStore.getState().reconnectAttempt).toBe(0))
  })

  it('updates message status on message_ack', async () => {
    qc.setQueryData(['intake', 's1', 'messages'], [
      {
        id: 'pending',
        clientId: 'c1',
        sessionId: 's1',
        sender: 'consumer',
        modality: 'text',
        content: 'hi',
        timestamp: 't',
        status: 'pending',
      },
    ])
    renderHook(() => useWebSocket('s1', 'tok'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(MockWebSocket.instances[0].readyState).toBe(1))
    act(() =>
      MockWebSocket.instances[0].simulate({
        type: 'message_ack',
        client_id: 'c1',
        id: 'srv-1',
        timestamp: 'T',
      }),
    )
    const msgs = qc.getQueryData(['intake', 's1', 'messages']) as Array<{ status: string; id: string }>
    expect(msgs[0].status).toBe('sent')
    expect(msgs[0].id).toBe('srv-1')
  })

  it('appends llm_stream tokens to streaming message', async () => {
    qc.setQueryData(['intake', 's1', 'messages'], [])
    renderHook(() => useWebSocket('s1', 'tok'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(MockWebSocket.instances[0].readyState).toBe(1))
    act(() =>
      MockWebSocket.instances[0].simulate({
        type: 'llm_stream',
        message_id: 'm1',
        token: 'Hel',
        done: false,
      }),
    )
    act(() =>
      MockWebSocket.instances[0].simulate({
        type: 'llm_stream',
        message_id: 'm1',
        token: 'lo',
        done: true,
      }),
    )
    const msgs = qc.getQueryData(['intake', 's1', 'messages']) as Array<{ content: string; status: string }>
    expect(msgs[0].content).toBe('Hello')
    expect(msgs[0].status).toBe('done')
  })

  it('does not reconnect on close code 4001 (auth failure)', async () => {
    renderHook(() => useWebSocket('s1', 'tok'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(MockWebSocket.instances[0].readyState).toBe(1))
    // Switch to fake timers AFTER connection is established
    vi.useFakeTimers()
    act(() => MockWebSocket.instances[0].close(4001))
    vi.advanceTimersByTime(5000)
    expect(MockWebSocket.instances).toHaveLength(1) // no new instance created
    expect(useWSStore.getState().status).toBe('error')
    vi.useRealTimers()
  })

  it('returns new array reference on setQueryData (Pitfall 2)', async () => {
    const initial = [
      {
        id: 'pending',
        clientId: 'c2',
        sessionId: 's1',
        sender: 'consumer',
        modality: 'text',
        content: 'x',
        timestamp: 't',
        status: 'pending',
      },
    ]
    qc.setQueryData(['intake', 's1', 'messages'], initial)
    renderHook(() => useWebSocket('s1', 'tok'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(MockWebSocket.instances[0].readyState).toBe(1))
    act(() =>
      MockWebSocket.instances[0].simulate({
        type: 'message_ack',
        client_id: 'c2',
        id: 'srv-2',
        timestamp: 'T2',
      }),
    )
    const updated = qc.getQueryData(['intake', 's1', 'messages'])
    expect(updated).not.toBe(initial)
  })

  it('updates analysis_progress in React Query cache', async () => {
    renderHook(() => useWebSocket('s1', 'tok'), { wrapper: makeWrapper(qc) })
    await waitFor(() => expect(MockWebSocket.instances[0].readyState).toBe(1))
    act(() =>
      MockWebSocket.instances[0].simulate({
        type: 'analysis_progress',
        data: { stage: 2, totalStages: 5, stageName: 'Research', iteration: 1, completeness: 0.4 },
      }),
    )
    const progress = qc.getQueryData(['intake', 's1', 'progress']) as { stage: number }
    expect(progress.stage).toBe(2)
  })
})
