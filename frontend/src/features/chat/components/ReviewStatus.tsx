import { useTranslation } from 'react-i18next'
import { Pause, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ReviewStatusState } from '../types'

interface Props {
  reviewStatus: ReviewStatusState
}

export function ReviewStatus({ reviewStatus }: Props) {
  const { t } = useTranslation('chat')

  if (reviewStatus.status === 'idle' || reviewStatus.status === 'proceeding') {
    return null
  }

  const isReviewing = reviewStatus.status === 'reviewing'
  const label =
    reviewStatus.label ||
    (isReviewing
      ? t('review.reviewing', 'Legal professional is reviewing')
      : t('review.paused', 'Analysis paused for review'))

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex items-center gap-[8px] px-[16px] py-[8px] border-t border-border bg-muted/30',
        'font-body text-[14px] text-muted-foreground',
      )}
    >
      {isReviewing ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        <Pause className="h-4 w-4" aria-hidden="true" />
      )}
      <span>{label}</span>
    </div>
  )
}
