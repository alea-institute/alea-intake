import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './store'

/**
 * Route guard — redirects to /login if not authenticated.
 * Preserves the intended destination in ?returnTo= so login can redirect back.
 */
export function RequireAuth() {
  const { accessToken } = useAuth()
  const location = useLocation()

  if (!accessToken) {
    const returnTo = location.pathname + location.search
    return <Navigate to={`/login?returnTo=${encodeURIComponent(returnTo)}`} replace />
  }

  return <Outlet />
}
