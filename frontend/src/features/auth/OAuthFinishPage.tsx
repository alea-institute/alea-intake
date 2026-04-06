import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from './store'

export function OAuthFinishPage() {
  const { t } = useTranslation('auth')
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState('')

  useEffect(() => {
    const code = params.get('code')
    if (!code) {
      setError(
        t('errors.ssoFailed', "We couldn't complete sign-in. Please try again.")
      )
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch('/api/v1/auth/oauth/exchange', {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code }),
        })
        if (!res.ok) throw new Error('exchange failed')
        const { access_token, user } = await res.json()
        if (!cancelled) {
          useAuth.getState().setAuth(access_token, user)
          navigate('/dashboard', { replace: true })
        }
      } catch {
        if (!cancelled) {
          setError(
            t(
              'errors.ssoFailed',
              "We couldn't complete sign-in. Please try again."
            )
          )
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [params, navigate, t])

  return (
    <div className="min-h-screen flex items-center justify-center p-lg">
      {error ? (
        <div className="text-destructive" role="alert">
          {error}
        </div>
      ) : (
        <div className="text-muted-foreground">
          {t('finishing', 'Completing sign-in...')}
        </div>
      )}
    </div>
  )
}
