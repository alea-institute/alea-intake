import { useTranslation } from 'react-i18next'

export function SSOButtons() {
  const { t } = useTranslation('auth')
  const go = (provider: 'google' | 'microsoft') => {
    window.location.href = `/api/v1/auth/oauth/login/${provider}`
  }
  return (
    <div className="space-y-sm">
      <button
        type="button"
        onClick={() => go('google')}
        className="w-full min-h-[44px] border border-border bg-card text-foreground rounded font-medium focus:ring-2 focus:ring-ring focus:ring-offset-2 outline-none hover:bg-secondary"
      >
        {t('signIn.google', 'Continue with Google')}
      </button>
      <button
        type="button"
        onClick={() => go('microsoft')}
        className="w-full min-h-[44px] border border-border bg-card text-foreground rounded font-medium focus:ring-2 focus:ring-ring focus:ring-offset-2 outline-none hover:bg-secondary"
      >
        {t('signIn.microsoft', 'Continue with Microsoft')}
      </button>
    </div>
  )
}
