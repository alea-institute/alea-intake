import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Progress } from '@/components/ui/progress'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AnalysisProgress } from '../types'

interface Props { sessionId: string }

export function AnalysisProgressPanel({ sessionId }: Props) {
  const { t } = useTranslation('chat')
  const [expanded, setExpanded] = useState(true)

  const { data: progress } = useQuery<AnalysisProgress | undefined>({
    queryKey: ['intake', sessionId, 'progress'],
    queryFn: () => undefined, // populated by WebSocket handler only
    enabled: false,            // never fetch via HTTP
    staleTime: Infinity,
  })

  // Show nothing when there's no active analysis — the panel only appears
  // once WebSocket pushes progress data for an in-flight analysis.
  if (!progress) {
    return null
  }

  const pct = Math.round((progress.completeness ?? 0) * 100)

  return (
    <aside
      className={cn(
        'bg-card border-b md:border-b-0 md:border-l border-border transition-all',
        'md:min-w-[280px] md:max-w-[320px]',
      )}
      aria-label={t('progress.title')}
    >
      {/* Mobile-collapsible header */}
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between px-md py-sm md:hidden min-h-[44px] text-left focus:ring-2 focus:ring-ring outline-none"
        aria-expanded={expanded}
        aria-controls="analysis-progress-content"
      >
        <span className="font-display text-[16px]">{t('progress.title')}</span>
        {expanded ? <ChevronUp className="h-4 w-4" aria-hidden="true" /> : <ChevronDown className="h-4 w-4" aria-hidden="true" />}
      </button>

      {/* Desktop title */}
      <div className="hidden md:block px-md pt-md">
        <h2 className="font-display text-[20px]">{t('progress.title')}</h2>
      </div>

      {/* Content (always visible on desktop, collapsible on mobile) */}
      <div
        id="analysis-progress-content"
        className={cn('p-md space-y-md', !expanded && 'hidden md:block')}
        aria-live="polite"
      >
        <div>
          <p className="font-body text-[14px] text-muted-foreground mb-xs">
            {t('progress.stage', { n: progress.stage, total: progress.totalStages, name: progress.stageName })}
          </p>
          <Progress value={pct} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} />
          <p className="font-body text-[14px] text-muted-foreground mt-xs">{pct}% complete</p>
        </div>
        <div className="text-[14px] space-y-xs">
          <p>
            <span className="text-muted-foreground">{t('progress.iteration', 'Iteration')}: </span>
            <span className="font-medium">{progress.iteration}</span>
          </p>
          {progress.nextStage && (
            <p className="text-muted-foreground">
              {t('progress.next', 'Next')}: <span className="text-foreground">{progress.nextStage}</span>
            </p>
          )}
        </div>
      </div>
    </aside>
  )
}
