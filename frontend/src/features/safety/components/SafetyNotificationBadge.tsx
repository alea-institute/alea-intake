import { useTranslation } from 'react-i18next'
import { Bell } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { useSafetyAlerts } from '../hooks/useSafetyAlerts'
import { useSafetyUI } from '../store'

interface Props { sessionId: string }

export function SafetyNotificationBadge({ sessionId }: Props) {
  const { t } = useTranslation('safety')
  const { data: alerts = [] } = useSafetyAlerts(sessionId)
  const setDrawerOpen = useSafetyUI((s) => s.setDrawerOpen)

  const elevated = alerts.filter((a) => a.tier === 'elevated')
  if (elevated.length === 0) return null

  return (
    <button
      type="button"
      onClick={() => setDrawerOpen(true)}
      className="relative min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded hover:bg-secondary focus:ring-2 focus:ring-ring focus:ring-offset-2 outline-none"
      aria-label={t('elevated.badgeLabel', '{{count}} resources available', { count: elevated.length })}
    >
      <Bell className="h-5 w-5" aria-hidden="true" />
      <Badge variant="secondary" className="absolute -top-1 -right-1 h-5 min-w-[20px] px-1 text-[12px]">
        {elevated.length}
      </Badge>
    </button>
  )
}
