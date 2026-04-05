import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ThemeProvider, useTheme } from './ThemeProvider'

function Probe() {
  const { theme } = useTheme()
  return <span>{theme}</span>
}

describe('ThemeProvider', () => {
  afterEach(() => document.documentElement.removeAttribute('data-theme'))

  it('sets data-theme on html root', () => {
    render(
      <ThemeProvider defaultTheme="legal-professional">
        <Probe />
      </ThemeProvider>
    )
    expect(document.documentElement.getAttribute('data-theme')).toBe('legal-professional')
    expect(screen.getByText('legal-professional')).toBeInTheDocument()
  })

  it('supports all three themes', () => {
    const { rerender } = render(
      <ThemeProvider defaultTheme="courthouse-classic">
        <Probe />
      </ThemeProvider>
    )
    expect(document.documentElement.getAttribute('data-theme')).toBe('courthouse-classic')
    rerender(
      <ThemeProvider defaultTheme="modern-conversational">
        <Probe />
      </ThemeProvider>
    )
    expect(document.documentElement.getAttribute('data-theme')).toBe('modern-conversational')
  })

  it('applies orgAccent override as inline CSS variable', () => {
    const { container } = render(
      <ThemeProvider defaultTheme="legal-professional" orgAccent="#FF6600">
        <Probe />
      </ThemeProvider>
    )
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.style.getPropertyValue('--primary')).toBeTruthy()
  })

  it('throws if useTheme used outside provider', () => {
    const originalError = console.error
    console.error = () => {}
    try {
      expect(() => render(<Probe />)).toThrow('useTheme must be used within ThemeProvider')
    } finally {
      console.error = originalError
    }
  })
})
