import { useEffect, useRef } from 'react'
import { ChatMessage } from './ChatMessage'
import { StreamingMessage } from './StreamingMessage'
import type { Message } from '../types'

interface Props {
  messages: Message[]
  onStopStream?: (messageId: string) => void
}

export function MessageList({ messages, onStopStream }: Props) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, messages[messages.length - 1]?.content.length])

  return (
    <div
      className="flex-1 overflow-y-auto px-md py-lg"
      role="log"
      aria-live="polite"
      aria-label="Conversation"
    >
      <div className="max-w-[720px] mx-auto flex flex-col gap-md">
        {messages.map((m) =>
          m.status === 'streaming' ? (
            <StreamingMessage
              key={m.id}
              message={m}
              onStop={() => onStopStream?.(m.id)}
            />
          ) : (
            <ChatMessage key={m.id} message={m} />
          ),
        )}
        <div ref={endRef} aria-hidden="true" />
      </div>
    </div>
  )
}
