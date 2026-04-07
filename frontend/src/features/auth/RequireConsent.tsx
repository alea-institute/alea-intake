import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { apiFetch } from './api'

type ConsentState = 'loading' | 'granted' | 'required'

/**
 * Route guard — checks consent status after authentication.
 * If no active consent exists, redirects to /consent.
 * Renders children (Outlet) only when consent is confirmed.
 */
export function RequireConsent() {
  const [state, setState] = useState<ConsentState>('loading')

  useEffect(() => {
    let cancelled = false
    apiFetch('/api/v1/consent/status')
      .then((res) => {
        if (!res.ok) throw new Error('consent check failed')
        return res.json()
      })
      .then((data) => {
        if (cancelled) return
        // API returns null when no consent, or the consent record when granted
        if (data === null || data === undefined) {
          setState('required')
        } else if (typeof data === 'object' && data.id) {
          // Consent record exists — check it hasn't been revoked
          setState(data.revoked_at ? 'required' : 'granted')
        } else if (data.has_active_consent === true) {
          // Alternative response format
          setState('granted')
        } else {
          setState('required')
        }
      })
      .catch(() => {
        // On error, redirect to consent to be safe
        if (!cancelled) setState('required')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (state === 'loading') {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <p className="text-muted-foreground">Checking consent status...</p>
      </div>
    )
  }

  if (state === 'required') {
    return <Navigate to="/consent" replace />
  }

  return <Outlet />
}
