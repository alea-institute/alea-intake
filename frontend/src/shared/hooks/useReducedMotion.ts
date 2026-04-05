import { useEffect, useState } from 'react'

/**
 * Returns true when the user has requested reduced motion via OS/browser preferences.
 * Subscribes to prefers-reduced-motion media query changes.
 * Consumers (streaming message renderer, fade transitions) MUST respect this per D-20 item 3.
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () =>
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return reduced
}
