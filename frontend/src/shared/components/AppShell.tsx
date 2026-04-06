import { Outlet } from 'react-router-dom'
import { Toaster } from 'sonner'
import { SkipToContent } from './SkipToContent'
import { ThemeProvider } from './ThemeProvider'
import { Sidebar } from './Sidebar'
import { MobileBottomNav } from './MobileBottomNav'

/**
 * Root application shell rendered by every authenticated route.
 * Wraps feature outlets in ThemeProvider + Sidebar (desktop) + MobileBottomNav (mobile).
 * Theme defaults to modern-conversational until the user's org data arrives.
 */
export function AppShell() {
  return (
    <ThemeProvider defaultTheme="modern-conversational">
      <SkipToContent />
      <div className="flex flex-col sm:flex-row h-screen bg-background">
        <Sidebar />
        <div className="flex-1 flex flex-col min-h-0 pb-[64px] sm:pb-0">
          <Outlet />
        </div>
      </div>
      <MobileBottomNav />
      <Toaster position="top-right" />
    </ThemeProvider>
  )
}
