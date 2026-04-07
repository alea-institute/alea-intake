import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/store'
import { apiFetch } from '@/features/auth/api'
import { useWebSocket } from './hooks/useWebSocket'
import { useIntakeMessages } from './hooks/useIntakeSession'
import { useWSStore } from './store'
import { MessageList } from './components/MessageList'
import { ChatInput } from './components/ChatInput'
import { ConnectionBanner } from './components/ConnectionBanner'
import { AnalysisProgressPanel } from './components/AnalysisProgressPanel'
import { SafetyBanner } from '@/features/safety/components/SafetyBanner'
import { SafetyDrawer } from '@/features/safety/components/SafetyDrawer'
import type { Message, Modality, WSCommand } from './types'

export function ChatPage() {
  const { sessionId: rawSessionId = '' } = useParams()
  const navigate = useNavigate()
  const accessToken = useAuth((s) => s.accessToken)
  const queryClient = useQueryClient()
  const ws = useWSStore((s) => s.ws)
  const wsStatus = useWSStore((s) => s.status)
  const [resolvedSessionId, setResolvedSessionId] = useState(rawSessionId === 'new' ? '' : rawSessionId)
  const [createError, setCreateError] = useState('')
  const creatingRef = useRef(false)

  const sessionId = resolvedSessionId

  // If sessionId is "new", create an intake via API and redirect
  useEffect(() => {
    if (rawSessionId !== 'new' || creatingRef.current || resolvedSessionId) return
    creatingRef.current = true
    apiFetch('/api/v1/intake/', { method: 'POST' })
      .then((res) => {
        if (!res.ok) throw new Error(`Intake creation failed: ${res.status}`)
        return res.json()
      })
      .then((data: { session_id?: number; id?: number }) => {
        const sid = data.session_id ?? data.id
        if (sid == null) throw new Error('No session_id in intake response')
        const sidStr = String(sid)
        setResolvedSessionId(sidStr)
        navigate(`/chat/${sidStr}`, { replace: true })
      })
      .catch((err) => {
        console.error('Failed to create intake:', err)
        setCreateError(err.message || 'Failed to create intake')
        creatingRef.current = false
      })
  }, [rawSessionId, resolvedSessionId, navigate])

  useWebSocket(sessionId, accessToken)
  const { data: messages = [] } = useIntakeMessages(sessionId)

  const handleSend = ({ modality, content }: { modality: Modality; content: string }) => {
    const clientId = crypto.randomUUID()
    const optimistic: Message = {
      id: clientId,
      clientId,
      sessionId,
      sender: 'consumer',
      modality,
      content,
      timestamp: new Date().toISOString(),
      status: 'pending',
    }
    // Optimistic update per D-07
    queryClient.setQueryData<Message[]>(
      ['intake', sessionId, 'messages'],
      (old = []) => [...old, optimistic],
    )
    // Send via WebSocket
    const cmd: WSCommand = { type: 'client_message', client_id: clientId, modality, content }
    ws?.send(JSON.stringify(cmd))
    // Timeout: mark failed if no ack in 5s
    setTimeout(() => {
      queryClient.setQueryData<Message[]>(
        ['intake', sessionId, 'messages'],
        (old = []) =>
          old.map((m) =>
            m.clientId === clientId && m.status === 'pending'
              ? { ...m, status: 'failed' }
              : m,
          ),
      )
    }, 5000)
  }

  const handleStopStream = (messageId: string) => {
    const cmd: WSCommand = { type: 'stream_cancel', message_id: messageId }
    ws?.send(JSON.stringify(cmd))
  }

  const inputDisabled = wsStatus !== 'connected' || !ws || !sessionId

  // Show loading while creating a new intake
  if (!sessionId) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        {createError ? (
          <div className="text-center space-y-2">
            <p className="text-destructive">{createError}</p>
            <button onClick={() => { setCreateError(''); creatingRef.current = false }} className="text-primary underline">Try again</button>
          </div>
        ) : (
          <p className="text-muted-foreground">Creating new intake…</p>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      <SafetyBanner sessionId={sessionId} />
      <ConnectionBanner />
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          <MessageList messages={messages} onStopStream={handleStopStream} />
          <ChatInput onSend={handleSend} disabled={inputDisabled} />
        </div>
        <AnalysisProgressPanel sessionId={sessionId} />
      </div>
      <SafetyDrawer sessionId={sessionId} />
    </div>
  )
}
