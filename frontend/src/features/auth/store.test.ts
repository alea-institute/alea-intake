import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuth } from './store'

describe('useAuth store', () => {
  beforeEach(() => useAuth.getState().clear())

  it('starts with null token and user', () => {
    expect(useAuth.getState().accessToken).toBeNull()
    expect(useAuth.getState().user).toBeNull()
  })

  it('stores token and user on setAuth', () => {
    useAuth.getState().setAuth('tok123', {
      id: 'u1',
      email: 'a@b.c',
      role: 'consumer',
      org_id: 'o1',
    })
    expect(useAuth.getState().accessToken).toBe('tok123')
    expect(useAuth.getState().user?.email).toBe('a@b.c')
  })

  it('clears on logout', () => {
    useAuth.getState().setAuth('tok', {
      id: 'u1',
      email: 'a@b.c',
      role: 'consumer',
      org_id: 'o1',
    })
    useAuth.getState().clear()
    expect(useAuth.getState().accessToken).toBeNull()
  })

  it('never writes auth data to localStorage per D-22', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem')
    useAuth.getState().setAuth('tok', {
      id: 'u1',
      email: 'a@b.c',
      role: 'consumer',
      org_id: 'o1',
    })
    // Zustand's default store has no persist middleware wired → should not write auth keys
    const authWrites = spy.mock.calls.filter(
      ([k, v]) =>
        (typeof k === 'string' && (k.toLowerCase().includes('auth') || k.toLowerCase().includes('token'))) ||
        (typeof v === 'string' && v.includes('tok'))
    )
    expect(authWrites).toHaveLength(0)
    spy.mockRestore()
  })
})
