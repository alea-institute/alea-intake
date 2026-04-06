import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { MessageSquare, Mic, Paperclip } from 'lucide-react'
import type { Message, Modality } from '../types'
import { cn } from '@/lib/utils'

const modalityIcon: Record<Modality, typeof MessageSquare> = {
  text: MessageSquare,
  voice: Mic,
  document: Paperclip,
}

interface Props {
  message: Message
}

export function ChatMessage({ message }: Props) {
  const isConsumer = message.sender === 'consumer'
  const Icon = modalityIcon[message.modality]
  const initials = isConsumer ? 'You' : 'AI'

  const formatted = new Date(message.timestamp).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })

  return (
    <article
      className={cn(
        'flex items-start gap-md max-w-[720px] w-full',
        isConsumer ? 'flex-row self-start' : 'flex-row-reverse self-end',
      )}
      aria-label={`Message from ${isConsumer ? 'you' : 'assistant'}`}
    >
      {isConsumer ? (
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="bg-secondary text-secondary-foreground text-sm font-body">
            {initials}
          </AvatarFallback>
        </Avatar>
      ) : (
        <Badge variant="secondary" className="shrink-0 mt-1" aria-label="AI assistant">
          AI
        </Badge>
      )}
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className={cn(
                'rounded-md px-md py-sm bg-card text-card-foreground shadow-sm font-body text-[16px] leading-[1.5]',
                'border border-border',
                message.status === 'pending' && 'opacity-50',
                message.status === 'failed' && 'border-destructive',
              )}
            >
              <div className="flex items-center gap-xs mb-xs text-muted-foreground text-[14px]">
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="sr-only">Modality: {message.modality}</span>
              </div>
              <div className="whitespace-pre-wrap">{message.content}</div>
              {message.status === 'pending' && (
                <span
                  className="ml-sm text-[14px] text-muted-foreground"
                  role="status"
                  aria-live="polite"
                >
                  Sending...
                </span>
              )}
            </div>
          </TooltipTrigger>
          <TooltipContent>{formatted}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </article>
  )
}
