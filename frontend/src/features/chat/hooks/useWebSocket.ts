import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWSStore } from '../store'
import type { Message, WSEvent } from '../types'

const BACKOFF_MS = [1000, 2000, 4000, 8000, 16000, 30000]

export function useWebSocket(sessionId: string | null, token: string | null): void {
  const queryClient = useQueryClient()
  const setStatus = useWSStore((s) => s.setStatus)
  const setWs = useWSStore((s) => s.setWs)
  const setReconnectAttempt = useWSStore((s) => s.setReconnectAttempt)

  useEffect(() => {
    if (!sessionId || !token) return

    let ws: WebSocket | null = null
    let reconnectTimer: number | null = null
    let attempt = 0
    let disposed = false

    const connect = () => {
      if (disposed) return
      setStatus(attempt === 0 ? 'connecting' : 'reconnecting')
      setReconnectAttempt(attempt)

      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws/intake/${sessionId}?token=${encodeURIComponent(token)}`
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        attempt = 0
        setReconnectAttempt(0)
        setStatus('connected')
        setWs(ws)
        // Refetch messages on (re)connect to catch missed events
        queryClient.invalidateQueries({ queryKey: ['intake', sessionId, 'messages'] })
      }

      ws.onmessage = (e) => {
        let msg: WSEvent
        try {
          msg = JSON.parse(e.data) as WSEvent
        } catch {
          return
        }
        handleEvent(msg, queryClient, sessionId)
      }

      ws.onclose = (e) => {
        setStatus('disconnected')
        setWs(null)
        if (disposed) return
        // Auth failures: don't reconnect (prevents infinite loop)
        if (e.code === 4001 || e.code === 4003) {
          setStatus('error')
          return
        }
        // Exponential backoff with jitter
        const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)]
        const jitter = Math.random() * 300
        reconnectTimer = window.setTimeout(connect, delay + jitter)
        attempt += 1
      }

      ws.onerror = () => setStatus('error')
    }

    connect()

    return () => {
      disposed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws?.close(1000, 'component unmount')
    }
  }, [sessionId, token, queryClient, setStatus, setWs, setReconnectAttempt])
}

function handleEvent(
  msg: WSEvent,
  queryClient: ReturnType<typeof useQueryClient>,
  sessionId: string,
): void {
  const msgKey = ['intake', sessionId, 'messages'] as const

  switch (msg.type) {
    case 'message_ack':
      queryClient.setQueryData<Message[]>([...msgKey], (old = []) =>
        // Return NEW array per Pitfall 2 (reference equality)
        old.map((m) =>
          m.clientId === msg.client_id
            ? { ...m, status: 'sent' as const, id: msg.id, timestamp: msg.timestamp }
            : m,
        ),
      )
      break

    case 'llm_stream':
      queryClient.setQueryData<Message[]>([...msgKey], (old = []) => {
        const existing = old.find((m) => m.id === msg.message_id)
        if (existing) {
          return old.map((m) =>
            m.id === msg.message_id
              ? { ...m, content: m.content + msg.token, status: msg.done ? 'done' as const : 'streaming' as const }
              : m,
          )
        }
        // First token -- create the streaming message
        return [
          ...old,
          {
            id: msg.message_id,
            sessionId,
            sender: 'system' as const,
            modality: 'text' as const,
            content: msg.token,
            timestamp: new Date().toISOString(),
            status: msg.done ? 'done' as const : 'streaming' as const,
          },
        ]
      })
      break

    case 'analysis_progress':
      queryClient.setQueryData(['intake', sessionId, 'progress'], msg.data)
      break

    case 'safety_alert':
      queryClient.invalidateQueries({ queryKey: ['intake', sessionId, 'safety'] })
      break

    case 'fact_extracted':
      queryClient.invalidateQueries({ queryKey: ['intake', sessionId, 'facts'] })
      break

    case 'error':
      console.error('[WS error]', msg.code, msg.message)
      break
  }
}
