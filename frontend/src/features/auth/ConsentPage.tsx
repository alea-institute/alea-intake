import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { apiFetch } from './api'

/**
 * Consent gate — shown after login when the user has no active consent.
 * Requires explicit opt-in for AI processing and data storage before
 * any intake API calls will succeed (backend returns 403 otherwise).
 */
export function ConsentPage() {
  const { t } = useTranslation(['auth', 'common'])
  const navigate = useNavigate()
  const [aiProcessing, setAiProcessing] = useState(false)
  const [dataStorage, setDataStorage] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const allChecked = aiProcessing && dataStorage

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!allChecked) return
    setError('')
    setSubmitting(true)
    try {
      const res = await apiFetch('/api/v1/consent/grant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          consent_version: '1.0',
          consent_items: {
            ai_processing: true,
            data_storage: true,
          },
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail ?? 'Consent submission failed')
      }
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t('auth:errors.consentFailed', 'Could not record consent. Please try again.')
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-md">
      <div className="w-full max-w-lg bg-card rounded-lg shadow-sm p-lg space-y-lg border border-border">
        <h1 className="font-display text-[28px] text-foreground">
          {t('auth:consent.heading', 'Before we begin')}
        </h1>
        <p className="font-body text-[14px] text-muted-foreground leading-relaxed">
          {t(
            'auth:consent.description',
            'To proceed, please review and accept the following terms. Your data will be handled in accordance with our privacy policy.'
          )}
        </p>

        <form onSubmit={handleSubmit} className="space-y-md">
          <label className="flex items-start gap-sm cursor-pointer min-h-[44px] py-xs">
            <input
              type="checkbox"
              checked={aiProcessing}
              onChange={(e) => setAiProcessing(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-input accent-primary"
            />
            <span className="text-sm text-foreground leading-relaxed">
              {t(
                'auth:consent.aiProcessing',
                'I consent to AI-assisted processing of my intake information to generate legal analysis and recommendations.'
              )}
            </span>
          </label>

          <label className="flex items-start gap-sm cursor-pointer min-h-[44px] py-xs">
            <input
              type="checkbox"
              checked={dataStorage}
              onChange={(e) => setDataStorage(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-input accent-primary"
            />
            <span className="text-sm text-foreground leading-relaxed">
              {t(
                'auth:consent.dataStorage',
                'I consent to secure storage and processing of my personal data as described in the privacy policy.'
              )}
            </span>
          </label>

          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={!allChecked || submitting}
            className="w-full min-h-[44px] bg-primary text-primary-foreground rounded font-medium focus:ring-2 focus:ring-ring focus:ring-offset-2 outline-none disabled:opacity-50"
          >
            {submitting
              ? t('auth:consent.submitting', 'Submitting...')
              : t('auth:consent.agree', 'Agree and continue')}
          </button>
        </form>
      </div>
    </div>
  )
}
