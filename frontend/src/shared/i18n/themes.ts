import type { Theme } from '@/shared/components/ThemeProvider'

/**
 * Lazy-load fonts for a given theme. Called when ThemeProvider mounts with a specific theme.
 * Keeps font payload out of main bundle — each theme only loads the weights it needs.
 * Addresses Pitfall 6 (eager @fontsource imports blow bundle budget).
 */
export async function loadThemeFonts(theme: Theme): Promise<void> {
  switch (theme) {
    case 'legal-professional':
      await Promise.all([
        import('@fontsource/source-serif-4/600.css'),
        import('@fontsource/inter/400.css'),
        import('@fontsource/inter/600.css'),
      ])
      break
    case 'modern-conversational':
      await Promise.all([import('@fontsource/inter/400.css'), import('@fontsource/inter/600.css')])
      break
    case 'courthouse-classic':
      await Promise.all([
        import('@fontsource/libre-caslon-text/600.css'),
        import('@fontsource/libre-franklin/400.css'),
        import('@fontsource/libre-franklin/600.css'),
      ])
      break
  }
}
