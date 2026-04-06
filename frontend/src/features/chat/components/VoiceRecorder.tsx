import { useWavesurfer } from '@wavesurfer/react'
import RecordPlugin from 'wavesurfer.js/dist/plugins/record.esm.js'
import { useRef, useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Mic, Square, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface Props {
  onRecorded: (blob: Blob, mime: string, durationMs: number) => void
  onCancel: () => void
  maxDurationMs?: number
}

const DEFAULT_MAX_DURATION = 180_000 // 3 min

function pickMimeType(): string {
  if (typeof MediaRecorder === 'undefined') return 'audio/webm'
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus'
  if (MediaRecorder.isTypeSupported('audio/webm')) return 'audio/webm'
  if (MediaRecorder.isTypeSupported('audio/mp4')) return 'audio/mp4'
  return 'audio/webm' // fallback; may fail on Safari
}

function formatTime(ms: number): string {
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export { pickMimeType }

export function VoiceRecorder({ onRecorded, onCancel, maxDurationMs = DEFAULT_MAX_DURATION }: Props) {
  const { t } = useTranslation(['chat', 'common'])
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [recording, setRecording] = useState(false)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const recordPluginRef = useRef<ReturnType<typeof RecordPlugin.create> | null>(null)
  const elapsedRef = useRef(0)

  const { wavesurfer } = useWavesurfer({
    container: containerRef,
    waveColor: 'hsl(var(--primary))',
    progressColor: 'hsl(var(--primary) / 0.5)',
    height: 64,
    cursorWidth: 0,
  })

  useEffect(() => {
    if (!wavesurfer) return
    const mime = pickMimeType()
    const record = wavesurfer.registerPlugin(
      RecordPlugin.create({ scrollingWaveform: true, renderRecordedAudio: false, mimeType: mime }),
    )
    recordPluginRef.current = record

    record.on('record-progress', (ms: number) => {
      setElapsedMs(ms)
      elapsedRef.current = ms
    })
    record.on('record-end', (blob: Blob) => {
      setRecording(false)
      onRecorded(blob, blob.type || mime, elapsedRef.current)
    })

    return () => {
      try { record.destroy() } catch { /* cleanup */ }
    }
  }, [wavesurfer, onRecorded])

  // Auto-stop at max duration
  useEffect(() => {
    if (recording && elapsedMs >= maxDurationMs) {
      recordPluginRef.current?.stopRecording()
    }
  }, [recording, elapsedMs, maxDurationMs])

  const startRecording = useCallback(async () => {
    setError(null)
    try {
      await recordPluginRef.current?.startRecording()
      setRecording(true)
      setElapsedMs(0)
    } catch {
      setError(t('chat:voice.micDenied', 'Microphone access was denied. Please enable microphone permission and try again.'))
    }
  }, [t])

  const stopRecording = () => recordPluginRef.current?.stopRecording()

  const cancel = () => {
    if (recording) {
      try { recordPluginRef.current?.stopRecording() } catch { /* cleanup */ }
    }
    setRecording(false)
    setElapsedMs(0)
    onCancel()
  }

  return (
    <div className="bg-card rounded-md p-md border border-border space-y-md">
      <div ref={containerRef} aria-label={t('chat:voice.waveformLabel', 'Voice recording waveform')} className="min-h-[64px]" />
      <div className="flex items-center justify-between gap-md">
        <span className="font-body text-[14px] text-muted-foreground" aria-live="polite">
          {formatTime(elapsedMs)} / {formatTime(maxDurationMs)}
        </span>
        <div className="flex gap-sm">
          <Button
            type="button"
            variant="outline"
            onClick={cancel}
            className="min-h-[44px] min-w-[44px]"
            aria-label={t('chat:voice.cancel', 'Cancel recording')}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            type="button"
            onClick={recording ? stopRecording : startRecording}
            className={cn('min-h-[44px] min-w-[44px]', recording && 'bg-destructive text-destructive-foreground hover:bg-destructive/90')}
            aria-label={recording ? t('chat:voice.stop', 'Stop recording') : t('common:cta.startRecording')}
            aria-pressed={recording}
          >
            {recording ? <Square className="h-4 w-4" aria-hidden="true" /> : <Mic className="h-4 w-4" aria-hidden="true" />}
          </Button>
        </div>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
