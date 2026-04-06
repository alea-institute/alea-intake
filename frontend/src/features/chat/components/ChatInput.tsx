import { useState, useRef, useCallback, type KeyboardEvent } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Send, MessageSquare, Mic, Paperclip } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Modality } from '../types'
import { cn } from '@/lib/utils'
import { VoiceRecorder } from './VoiceRecorder'
import { DocumentUploader } from './DocumentUploader'

interface Props {
  onSend: (payload: { modality: Modality; content: string }) => void
  onFileSelected?: (file: File) => void
  disabled?: boolean
}

export function ChatInput({ onSend, onFileSelected, disabled }: Props) {
  const { t } = useTranslation(['chat', 'common'])
  const [modality, setModality] = useState<Modality>('text')
  const [content, setContent] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleSubmit() {
    const trimmed = content.trim()
    if (!trimmed) return
    onSend({ modality: 'text', content: trimmed })
    setContent('')
    textareaRef.current?.focus()
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleVoiceRecorded = useCallback(
    (blob: Blob, _mime: string, _durationMs: number) => {
      // Create object URL for the blob and send as voice modality
      const audioUrl = URL.createObjectURL(blob)
      onSend({ modality: 'voice', content: audioUrl })
      setModality('text')
    },
    [onSend],
  )

  const handleDocumentSelected = useCallback(
    (file: File) => {
      if (onFileSelected) {
        onFileSelected(file)
      } else {
        onSend({ modality: 'document', content: file.name })
      }
      setModality('text')
    },
    [onSend, onFileSelected],
  )

  const modalityButtons: Array<{
    key: Modality
    icon: typeof MessageSquare
    labelKey: string
  }> = [
    { key: 'text', icon: MessageSquare, labelKey: 'chat:input.modalityText' },
    { key: 'voice', icon: Mic, labelKey: 'chat:input.modalityVoice' },
    { key: 'document', icon: Paperclip, labelKey: 'chat:input.modalityDocument' },
  ]

  return (
    <div className="sticky bottom-0 bg-background border-t border-border p-md">
      <div className="max-w-[720px] mx-auto">
        <div className="flex items-end gap-sm">
          <TooltipProvider>
            <div className="flex gap-xs" role="radiogroup" aria-label="Input modality">
              {modalityButtons.map(({ key, icon: Icon, labelKey }) => {
                const active = modality === key
                return (
                  <Tooltip key={key}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        role="radio"
                        aria-checked={active}
                        aria-label={t(labelKey)}
                        onClick={() => setModality(key)}
                        className={cn(
                          'inline-flex items-center justify-center rounded min-h-[44px] min-w-[44px] transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 outline-none',
                          active
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-card text-card-foreground hover:bg-secondary border border-border',
                        )}
                      >
                        <Icon className="h-5 w-5" aria-hidden="true" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>{t(labelKey)}</TooltipContent>
                  </Tooltip>
                )
              })}
            </div>
          </TooltipProvider>
          {modality === 'text' && (
            <>
              <Textarea
                ref={textareaRef}
                value={content}
                onChange={(e) => setContent(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('chat:input.placeholder')}
                rows={1}
                disabled={disabled}
                aria-label={t('chat:input.placeholder')}
                className="flex-1 min-h-[44px] max-h-[160px] resize-none font-body text-[16px] leading-[1.5]"
              />
              <Button
                type="button"
                onClick={handleSubmit}
                disabled={disabled || !content.trim()}
                className="min-h-[44px] shrink-0"
                aria-label={t('common:cta.sendMessage')}
              >
                <Send className="h-4 w-4 mr-xs" aria-hidden="true" />
                <span className="hidden sm:inline">{t('common:cta.sendMessage')}</span>
              </Button>
            </>
          )}
        </div>
        {modality === 'voice' && (
          <div className="mt-sm" data-testid="voice-recorder-surface">
            <VoiceRecorder
              onRecorded={handleVoiceRecorded}
              onCancel={() => setModality('text')}
            />
          </div>
        )}
        {modality === 'document' && (
          <div className="mt-sm" data-testid="document-uploader-surface">
            <DocumentUploader
              onFileSelected={handleDocumentSelected}
              onCancel={() => setModality('text')}
            />
          </div>
        )}
      </div>
    </div>
  )
}
