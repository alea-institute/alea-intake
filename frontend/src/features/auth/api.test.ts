import { describe, it, expect, beforeEach, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/msw/server'
import { useAuth } from './store'
import { apiFetch, login } from './api'

// jsdom origin is http://localhost:3000 — relative /api/... paths resolve here
const ORIGIN = 'http://localhost:3000'

describe('apiFetch', () => {
  beforeEach(() => useAuth.getState().clear())

  it('attaches Authorization header from auth store', async () => {
    useAuth.getState().setAuth('tok-xyz', {
      id: 'u1',
      email: 'a@b.c',
      role: 'consumer',
      org_id: 'o1',
    })
    let captured = ''
    server.use(
      http.get(`${ORIGIN}/api/v1/ping`, ({ request }) => {
        captured = request.headers.get('authorization') ?? ''
        return HttpResponse.json({ ok: true })
      })
    )
    await apiFetch('/api/v1/ping')
    expect(captured).toBe('Bearer tok-xyz')
  })

  it('retries with refreshed token on 401', async () => {
    useAuth.getState().setAuth('stale-tok', {
      id: 'u1',
      email: 'a@b.c',
      role: 'consumer',
      org_id: 'o1',
    })
    let callCount = 0
    server.use(
      http.get(`${ORIGIN}/api/v1/protected`, ({ request }) => {
        callCount += 1
        const auth = request.headers.get('authorization')
        if (auth === 'Bearer stale-tok') return new HttpResponse(null, { status: 401 })
        return HttpResponse.json({ ok: true })
      }),
      http.post(`${ORIGIN}/api/v1/auth/refresh`, () =>
        HttpResponse.json({
          access_token: 'fresh-tok',
          user: { id: 'u1', email: 'a@b.c', role: 'consumer', org_id: 'o1' },
        })
      )
    )
    const res = await apiFetch('/api/v1/protected')
    expect(res.ok).toBe(true)
    expect(callCount).toBe(2)
    expect(useAuth.getState().accessToken).toBe('fresh-tok')
  })

  it('clears auth on refresh failure', async () => {
    useAuth.getState().setAuth('stale', {
      id: 'u1',
      email: 'a@b.c',
      role: 'consumer',
      org_id: 'o1',
    })
    server.use(
      http.get(`${ORIGIN}/api/v1/protected`, () => new HttpResponse(null, { status: 401 })),
      http.post(`${ORIGIN}/api/v1/auth/refresh`, () => new HttpResponse(null, { status: 401 }))
    )
    // Override window.location with a proxy that captures href assignments.
    // jsdom's href setter actually navigates and throws, so we intercept here.
    const originalLocation = window.location
    const hrefSetter = vi.fn()
    const mockLocation = new Proxy(originalLocation, {
      set(target, prop, value) {
        if (prop === 'href') {
          hrefSetter(value)
          return true
        }
        return Reflect.set(target, prop, value)
      },
    })
    // @ts-expect-error - jsdom allows deleting window.location in tests
    delete window.location
    window.location = mockLocation

    try {
      await expect(apiFetch('/api/v1/protected')).rejects.toThrow('Session expired')
      expect(useAuth.getState().accessToken).toBeNull()
      expect(hrefSetter).toHaveBeenCalledWith('/login')
    } finally {
      window.location = originalLocation
    }
  })

  it('login stores token + user', async () => {
    server.use(
      http.post(`${ORIGIN}/api/v1/auth/login`, () =>
        HttpResponse.json({
          access_token: 'logged-in',
          user: { id: 'u1', email: 'a@b.c', role: 'consumer', org_id: 'o1' },
        })
      )
    )
    await login('a@b.c', 'pw')
    expect(useAuth.getState().accessToken).toBe('logged-in')
  })
})
