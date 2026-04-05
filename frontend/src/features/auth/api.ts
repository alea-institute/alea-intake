import { useAuth, type User } from './store'

const API_BASE = '/api/v1'

let refreshPromise: Promise<void> | null = null

/**
 * Refresh the access token using the httpOnly refresh cookie.
 * Coalesces concurrent refreshes to avoid thundering-herd on first 401 after idle.
 */
async function refreshToken(): Promise<void> {
  if (refreshPromise) return refreshPromise
  refreshPromise = (async () => {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
    if (!res.ok) {
      useAuth.getState().clear()
      throw new Error('Session expired')
    }
    const { access_token, user } = await res.json()
    useAuth.getState().setAuth(access_token, user)
  })()
  try {
    await refreshPromise
  } finally {
    refreshPromise = null
  }
}

/**
 * Fetch wrapper that attaches the bearer token from useAuth and auto-retries on 401
 * by refreshing via the httpOnly cookie. On refresh failure, clears auth and redirects
 * to /login (D-22).
 */
export async function apiFetch(input: RequestInfo, init: RequestInit = {}): Promise<Response> {
  const token = useAuth.getState().accessToken
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let res = await fetch(input, { ...init, headers, credentials: 'include' })

  if (res.status === 401) {
    try {
      await refreshToken()
      const newToken = useAuth.getState().accessToken
      if (newToken) headers.set('Authorization', `Bearer ${newToken}`)
      res = await fetch(input, { ...init, headers, credentials: 'include' })
    } catch {
      if (typeof window !== 'undefined') {
        window.location.href = '/login'
      }
      throw new Error('Session expired')
    }
  }
  return res
}

export async function login(email: string, password: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? 'Login failed')
  }
  const { access_token, user } = await res.json()
  useAuth.getState().setAuth(access_token, user)
  return user
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  }).catch(() => {})
  useAuth.getState().clear()
}

export { refreshToken }
