import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { LoginPage } from './LoginPage'

describe('LoginPage', () => {
  it('renders email, password, and SSO buttons', () => {
    renderWithProviders(<LoginPage />)
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /continue with google/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /continue with microsoft/i })
    ).toBeInTheDocument()
  })

  it('navigates to google OAuth on click', async () => {
    const user = userEvent.setup()
    const originalHref = window.location.href
    // Spy on location.href assignment via Object.defineProperty
    let capturedHref = ''
    Object.defineProperty(window, 'location', {
      value: {
        ...window.location,
        get href() {
          return capturedHref || originalHref
        },
        set href(val: string) {
          capturedHref = val
        },
      },
      writable: true,
      configurable: true,
    })

    renderWithProviders(<LoginPage />)
    await user.click(
      screen.getByRole('button', { name: /continue with google/i })
    )
    expect(capturedHref).toBe('/api/v1/auth/oauth/login/google')

    // Restore
    Object.defineProperty(window, 'location', {
      value: { href: originalHref },
      writable: true,
      configurable: true,
    })
  })

  it('navigates to microsoft OAuth on click', async () => {
    const user = userEvent.setup()
    let capturedHref = ''
    const originalHref = window.location.href
    Object.defineProperty(window, 'location', {
      value: {
        ...window.location,
        get href() {
          return capturedHref || originalHref
        },
        set href(val: string) {
          capturedHref = val
        },
      },
      writable: true,
      configurable: true,
    })

    renderWithProviders(<LoginPage />)
    await user.click(
      screen.getByRole('button', { name: /continue with microsoft/i })
    )
    expect(capturedHref).toBe('/api/v1/auth/oauth/login/microsoft')

    Object.defineProperty(window, 'location', {
      value: { href: originalHref },
      writable: true,
      configurable: true,
    })
  })
})
