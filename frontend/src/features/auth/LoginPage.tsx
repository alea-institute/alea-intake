import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { login, apiFetch } from './api'
import { SSOButtons } from './components/SSOButtons'

/**
 * After login, check consent status and route accordingly.
 * If consent is already granted, go to dashboard; otherwise go to /consent.
 */
async function getPostLoginRoute(): Promise<string> {
  try {
    const res = await apiFetch('/api/v1/consent/status')
    if (res.ok) {
      const data: { has_active_consent?: boolean } = await res.json()
      if (!data.has_active_consent) return '/consent'
    }
  } catch {
    // On failure, let RequireConsent guard handle it downstream
  }
  return '/dashboard'
}

export function LoginPage() {
  const { t } = useTranslation(['auth', 'common'])
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(email, password)
      const dest = await getPostLoginRoute()
      navigate(dest)
    } catch {
      setError(
        t(
          'auth:errors.invalidCredentials',
          "That email and password combination didn't match. Please try again."
        )
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-md">
      <div className="w-full max-w-md bg-card rounded-lg shadow-sm p-lg space-y-lg border border-border">
        <h1 className="font-display text-[28px] text-foreground">
          {t('auth:signIn.heading', 'Sign in to continue')}
        </h1>
        <form onSubmit={handleSubmit} className="space-y-md">
          <div className="space-y-sm">
            <label
              htmlFor="email"
              className="text-sm font-medium text-foreground"
            >
              {t('auth:signIn.emailLabel', 'Email address')}
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full min-h-[44px] px-md rounded border border-input bg-background text-foreground focus:ring-2 focus:ring-ring focus:ring-offset-2 outline-none"
            />
          </div>
          <div className="space-y-sm">
            <label
              htmlFor="password"
              className="text-sm font-medium text-foreground"
            >
              {t('auth:signIn.passwordLabel', 'Password')}
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full min-h-[44px] px-md rounded border border-input bg-background text-foreground focus:ring-2 focus:ring-ring focus:ring-offset-2 outline-none"
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="w-full min-h-[44px] bg-primary text-primary-foreground rounded font-medium focus:ring-2 focus:ring-ring focus:ring-offset-2 outline-none disabled:opacity-50"
          >
            {t('common:cta.signIn', 'Sign in')}
          </button>
        </form>
        <div className="relative text-center text-sm text-muted-foreground">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-border" />
          </div>
          <span className="relative bg-card px-md">
            {t('auth:signIn.ssoSeparator', 'Or continue with')}
          </span>
        </div>
        <SSOButtons />
      </div>
    </div>
  )
}
