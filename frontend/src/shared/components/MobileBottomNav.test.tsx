import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { MobileBottomNav } from './MobileBottomNav'
import { useAuth } from '@/features/auth/store'

describe('MobileBottomNav', () => {
  beforeEach(() => useAuth.getState().clear())

  it('renders 3 items for non-admin users', () => {
    useAuth
      .getState()
      .setAuth('t', { id: 'u1', email: 'a@b', role: 'consumer', org_id: 'o1' })
    renderWithProviders(<MobileBottomNav />)
    expect(screen.getAllByRole('link')).toHaveLength(3) // Chat, Dashboard, Profile (admin hidden)
  })

  it('renders 4 items for admin users', () => {
    useAuth
      .getState()
      .setAuth('t', { id: 'u1', email: 'a@b', role: 'admin', org_id: 'o1' })
    renderWithProviders(<MobileBottomNav />)
    expect(screen.getAllByRole('link')).toHaveLength(4)
  })

  it('all nav items have aria-label', () => {
    useAuth
      .getState()
      .setAuth('t', { id: 'u1', email: 'a@b', role: 'admin', org_id: 'o1' })
    renderWithProviders(<MobileBottomNav />)
    screen.getAllByRole('link').forEach((link) => {
      expect(link).toHaveAttribute('aria-label')
    })
  })

  it('nav container has height 64px class', () => {
    useAuth
      .getState()
      .setAuth('t', { id: 'u1', email: 'a@b', role: 'consumer', org_id: 'o1' })
    const { container } = renderWithProviders(<MobileBottomNav />)
    const nav = container.querySelector('nav')
    expect(nav?.className).toContain('h-[64px]')
  })

  it('each nav item has min 44px touch target', () => {
    useAuth
      .getState()
      .setAuth('t', { id: 'u1', email: 'a@b', role: 'consumer', org_id: 'o1' })
    renderWithProviders(<MobileBottomNav />)
    screen.getAllByRole('link').forEach((link) => {
      expect(link.className).toContain('min-h-[44px]')
      expect(link.className).toContain('min-w-[44px]')
    })
  })
})
