import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/store'
import { useWebSocket } from './hooks/useWebSocket'
import { useIntakeMessages } from './hooks/useIntakeSession'
import { useWSStore, usePracticeAreaStore } from './store'
import { usePracticeAreas } from './hooks/usePracticeAreas'
import { createIntake } from './api'
import { MessageList } from './components/MessageList'
import { ChatInput } from './components/ChatInput'
import { ConnectionBanner } from './components/ConnectionBanner'
import { AnalysisProgressPanel } from './components/AnalysisProgressPanel'
import { PracticeAreaChips } from './components/PracticeAreaChips'
import { SafetyBanner } from '@/features/safety/components/SafetyBanner'
import { SafetyDrawer } from '@/features/safety/components/SafetyDrawer'
import { Button } from '@/components/ui/button'
import type { Message, Modality, WSCommand } from './types'

const GENERIC_WELCOME_CONSUMER =
  'Tell me about your legal situation in your own words. You can type, record your voice, or upload documents — whatever is easiest for you.'

const GENERIC_WELCOME_PROFESSIONAL =
  "Enter the client's information. You can use the conversational interface or switch to structured form."

export function ChatPage() {
  const { sessionId: rawSessionId = '' } = useParams()
  const navigate = useNavigate()
  const accessToken = useAuth((s) => s.accessToken)
  const userRole = useAuth((s) => s.user?.role)
  const queryClient = useQueryClient()
  const ws = useWSStore((s) => s.ws)
  const wsStatus = useWSStore((s) => s.status)
  const practiceAreaId = usePracticeAreaStore((s) => s.practiceAreaId)
  const setPracticeArea = usePracticeAreaStore((s) => s.setPracticeArea)
  const resetPracticeArea = usePracticeAreaStore((s) => s.reset)
  const [resolvedSessionId, setResolvedSessionId] = useState(rawSessionId === 'new' ? '' : rawSessionId)
  const [createError, setCreateError] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const creatingRef = useRef(false)

  const sessionId = resolvedSessionId
  const isNewIntake = rawSessionId === 'new' && !resolvedSessionId
  const isProfessional = userRole === 'professional'

  // Resolve welcome copy from the cached practice-area list (no extra fetch).
  const { data: practiceAreas } = usePracticeAreas()
  const selectedArea = practiceAreaId
    ? practiceAreas?.find((p) => p.id === practiceAreaId)
    : undefined
  const welcomeMessage = selectedArea
    ? isProfessional
      ? selectedArea.welcome_message_professional
      : selectedArea.welcome_message_consumer
    : isProfessional
      ? GENERIC_WELCOME_PROFESSIONAL
      : GENERIC_WELCOME_CONSUMER
  const welcomeHeading = selectedArea
    ? `${selectedArea.display_name} intake`
    : 'Start your intake'

  async function handleBeginIntake() {
    if (creatingRef.current) return
    creatingRef.current = true
    setIsCreating(true)
    setCreateError('')
    try {
      const data = await createIntake(practiceAreaId)
      const sid = data.session_id ?? data.id
      if (sid == null) throw new Error('No session_id in intake response')
      const sidStr = String(sid)
      setResolvedSessionId(sidStr)
      navigate(`/chat/${sidStr}`, { replace: true })
    } catch (err) {
      console.error('Failed to create intake:', err)
      setCreateError((err as Error).message || 'Failed to create intake')
      creatingRef.current = false
      setIsCreating(false)
    }
  }

  // When the user finishes/leaves the conversation, clear the practice
  // selection so the next intake starts fresh on Generic.
  useEffect(() => {
    if (resolvedSessionId) return
    return () => {
      resetPracticeArea()
    }
  }, [resolvedSessionId, resetPracticeArea])

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
    const cmd: WSCommand = { type: 'text_message', client_id: clientId, modality, content }
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

  // Pre-flight surface: chip-row + welcome card + Begin button.
  if (isNewIntake) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background px-md py-2xl">
        <div className="w-full max-w-[640px] flex flex-col gap-lg">
          <PracticeAreaChips
            selectedId={practiceAreaId}
            onSelect={setPracticeArea}
          />
          <div
            className="rounded-lg border border-border bg-card text-card-foreground shadow-sm p-xl flex flex-col gap-md"
            data-testid="welcome-card"
          >
            <h1 className="font-display text-[28px] font-semibold leading-[1.2]">
              {welcomeHeading}
            </h1>
            <p className="font-body text-[16px] leading-[1.6] text-foreground/85">
              {welcomeMessage}
            </p>
            {createError ? (
              <p
                role="alert"
                className="text-destructive text-[14px] font-medium"
              >
                {createError}
              </p>
            ) : null}
            <div className="flex justify-end pt-sm">
              <Button
                onClick={handleBeginIntake}
                disabled={isCreating}
                className="min-h-[44px] px-lg"
                size="lg"
              >
                {isCreating ? 'Starting…' : 'Begin intake'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Loading sliver while the new intake's session id resolves (rare —
  // handleBeginIntake already navigates synchronously after success).
  if (!sessionId) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <p className="text-muted-foreground">Loading intake…</p>
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
