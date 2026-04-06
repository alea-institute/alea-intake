import { useTranslation } from 'react-i18next'
import { useWSStore } from '../store'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'

export function ConnectionBanner() {
  const { t } = useTranslation(['chat', 'common'])
  const status = useWSStore((s) => s.status)

  if (status === 'connected' || status === 'connecting') return null

  const message =
    status === 'error'
      ? t('common:errors.sessionExpired')
      : t('common:errors.websocketDisconnect')

  return (
    <Alert
      variant={status === 'error' ? 'destructive' : 'default'}
      role="status"
      aria-live="assertive"
      className={cn('rounded-none border-x-0 border-t-0')}
    >
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}
