import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface Props {
  transcript: string
  audioUrl: string
  confidence?: number[]
  onApprove: (editedText: string) => void
  onReRecord: () => void
}

const LOW_CONFIDENCE_THRESHOLD = 0.6

export function TranscriptReview({ transcript, audioUrl, confidence, onApprove, onReRecord }: Props) {
  const { t } = useTranslation('chat')
  const [edited, setEdited] = useState(transcript)

  const lowConfidenceWords = useMemo(() => {
    if (!confidence) return []
    const words = transcript.split(/\s+/)
    return words
      .map((w, i) => ({ word: w, confidence: confidence[i] ?? 1 }))
      .filter(({ confidence: c }) => c < LOW_CONFIDENCE_THRESHOLD)
      .map(({ word }) => word)
  }, [transcript, confidence])

  return (
    <div className="bg-card rounded-md p-md border border-border space-y-md max-w-[720px]">
      <div className="space-y-sm">
        <label htmlFor="transcript-edit" className="font-body text-[14px] text-foreground block">
          {t('voice.reviewLabel', 'Review and edit your transcript')}
        </label>
        <Textarea
          id="transcript-edit"
          value={edited}
          onChange={(e) => setEdited(e.target.value)}
          rows={5}
          className="font-body text-[16px] leading-[1.5]"
          aria-describedby={lowConfidenceWords.length > 0 ? 'low-conf-hint' : undefined}
        />
        {lowConfidenceWords.length > 0 && (
          <p id="low-conf-hint" className="text-[14px] text-muted-foreground">
            {t('voice.lowConfHint', 'Some words may be inaccurate:')}{' '}
            <span className="text-destructive">{lowConfidenceWords.join(', ')}</span>
          </p>
        )}
      </div>
      <div className="space-y-sm">
        <label className="font-body text-[14px] text-foreground block">
          {t('voice.playbackLabel', 'Listen to your recording')}
        </label>
        <audio controls src={audioUrl} className="w-full" aria-label={t('voice.playbackLabel', 'Listen to your recording')}>
          {t('voice.audioUnsupported', 'Your browser does not support audio playback.')}
        </audio>
      </div>
      <div className="flex gap-sm justify-end">
        <Button type="button" variant="outline" onClick={onReRecord} className="min-h-[44px]">
          {t('voice.reRecord', 'Re-record')}
        </Button>
        <Button type="button" onClick={() => onApprove(edited)} className="min-h-[44px]">
          {t('voice.approve', 'Approve and send')}
        </Button>
      </div>
    </div>
  )
}
