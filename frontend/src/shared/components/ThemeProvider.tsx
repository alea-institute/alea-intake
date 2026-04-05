import { createContext, useContext, useEffect, useState, type ReactNode, type CSSProperties } from 'react'

export type Theme = 'legal-professional' | 'modern-conversational' | 'courthouse-classic'

interface ThemeCtx {
  theme: Theme
  setTheme: (t: Theme) => void
}

const ThemeContext = createContext<ThemeCtx | null>(null)

interface Props {
  children: ReactNode
  defaultTheme?: Theme
  orgAccent?: string // hex override for --primary per D-26
  logoUrl?: string // org logo URL (unused here, consumed by top-bar)
}

export function ThemeProvider({
  children,
  defaultTheme = 'modern-conversational',
  orgAccent,
  logoUrl: _logoUrl,
}: Props) {
  const [theme, setTheme] = useState<Theme>(defaultTheme)

  // Sync theme when defaultTheme prop changes (e.g. org data loads async)
  useEffect(() => {
    setTheme(defaultTheme)
  }, [defaultTheme])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const orgOverride: CSSProperties | undefined = orgAccent
    ? ({ ['--primary' as string]: hexToHsl(orgAccent) } as CSSProperties)
    : undefined

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      <div style={orgOverride} className="min-h-screen">
        {children}
      </div>
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}

/**
 * Convert #RRGGBB hex to HSL "H S% L%" format matching globals.css CSS variable values.
 * Used by ThemeProvider to apply org-branding accent overrides at runtime (D-26).
 */
function hexToHsl(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  let h = 0
  let s = 0
  const l = (max + min) / 2
  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) * 60
    else if (max === g) h = ((b - r) / d + 2) * 60
    else h = ((r - g) / d + 4) * 60
  }
  return `${Math.round(h)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`
}
