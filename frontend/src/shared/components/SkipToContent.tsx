import { useTranslation } from 'react-i18next'

/**
 * Skip-to-content link (WCAG 2.4.1, D-20 item 6).
 * First focusable element on every page; visually hidden until keyboard focus.
 * On activation, focus jumps to <main id="main-content">.
 */
export function SkipToContent() {
  const { t } = useTranslation('common')
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:bg-primary focus:text-primary-foreground focus:px-4 focus:py-2 focus:rounded"
    >
      {t('a11y.skipToContent')}
    </a>
  )
}
