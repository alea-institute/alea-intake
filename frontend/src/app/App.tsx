import { Outlet } from 'react-router-dom'
import { SkipToContent } from '@/shared/components/SkipToContent'
import { ThemeProvider } from '@/shared/components/ThemeProvider'

/**
 * Root application shell rendered by every route.
 * Wraps feature outlets in ThemeProvider + SkipToContent + <main> landmark.
 * Theme defaults to modern-conversational until the user's org data arrives.
 */
export function AppShell() {
  return (
    <ThemeProvider defaultTheme="modern-conversational">
      <SkipToContent />
      <main id="main-content">
        <Outlet />
      </main>
    </ThemeProvider>
  )
}
