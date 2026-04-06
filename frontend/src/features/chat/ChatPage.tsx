import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/features/auth/store'
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
  const { sessionId = '' } = useParams()
  const accessToken = useAuth((s) => s.accessToken)
  const queryClient = useQueryClient()
  const ws = useWSStore((s) => s.ws)
  const wsStatus = useWSStore((s) => s.status)

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

  const inputDisabled = wsStatus !== 'connected' || !ws

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
