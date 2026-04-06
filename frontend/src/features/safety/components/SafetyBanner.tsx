import { useTranslation } from 'react-i18next'
import { AlertTriangle } from 'lucide-react'
import { useTheme } from '@/shared/components/ThemeProvider'
import { useSafetyAlerts } from '../hooks/useSafetyAlerts'
import { useSafetyUI } from '../store'

interface Props { sessionId: string }

export function SafetyBanner({ sessionId }: Props) {
  const { t } = useTranslation('safety')
  const { theme } = useTheme()
  const { data: alerts = [] } = useSafetyAlerts(sessionId)
  const setDrawerOpen = useSafetyUI((s) => s.setDrawerOpen)

  const critical = alerts.filter((a) => a.tier === 'critical')
  if (critical.length === 0) return null

  const message = t(`critical.banner.${theme}`, 'Your safety comes first. Resources are available.')

  return (
    <button
      type="button"
      onClick={() => setDrawerOpen(true)}
      role="alert"
      aria-live="assertive"
      className="w-full bg-destructive text-destructive-foreground px-md py-sm flex items-center gap-sm text-left min-h-[44px] focus:ring-2 focus:ring-ring focus:ring-offset-2 outline-none hover:brightness-110"
    >
      <AlertTriangle className="h-5 w-5 shrink-0" aria-hidden="true" />
      <span className="flex-1 font-body text-[16px]">{message}</span>
      <span className="font-body text-[14px] underline">{t('critical.viewResources', 'View resources')}</span>
    </button>
  )
}
