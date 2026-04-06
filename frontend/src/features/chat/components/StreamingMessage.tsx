import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Square } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Message } from '../types'
import { useReducedMotion } from '@/shared/hooks/useReducedMotion'

interface Props {
  message: Message
  onStop?: () => void
}

export function StreamingMessage({ message, onStop }: Props) {
  const { t } = useTranslation('chat')
  const reducedMotion = useReducedMotion()
  const isStreaming = message.status === 'streaming'

  return (
    <article
      className="flex items-start gap-md max-w-[720px] self-end flex-row-reverse"
      aria-live="polite"
    >
      <Badge variant="secondary" className="shrink-0 mt-1" aria-label="AI assistant">
        AI
      </Badge>
      <div className="rounded-md px-md py-sm bg-card text-card-foreground shadow-sm border border-border font-body text-[16px] leading-[1.5]">
        <div className="whitespace-pre-wrap">
          {message.content}
          {isStreaming && !reducedMotion && (
            <span
              className="inline-block w-[2px] h-[1em] bg-primary align-middle ml-[1px] animate-pulse"
              aria-hidden="true"
              data-testid="streaming-cursor"
            />
          )}
        </div>
        {isStreaming && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onStop}
            className="mt-sm min-h-[32px]"
            aria-label={t('streaming.stop')}
          >
            <Square className="h-3 w-3 mr-xs" aria-hidden="true" />
            {t('streaming.stop')}
          </Button>
        )}
      </div>
    </article>
  )
}
