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
      .then((data: { has_active_consent?: boolean }) => {
        if (!cancelled) {
          setState(data.has_active_consent ? 'granted' : 'required')
        }
      })
      .catch(() => {
        // On error, allow through to avoid blocking — the backend will
        // still enforce consent with 403 on intake endpoints.
        if (!cancelled) setState('granted')
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
