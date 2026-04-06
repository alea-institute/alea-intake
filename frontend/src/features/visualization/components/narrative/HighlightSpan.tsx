/**
 * HighlightSpan -- annotated text span with claim-colored highlight (D-09/D-10).
 *
 * Single-claim: semi-transparent background color at 30% opacity.
 * Multi-claim: CSS linear-gradient with each claim's color at reduced opacity,
 * each taking an equal fraction of the gradient.
 * Selected state: thicker underline to indicate selection.
 * Accessible: role="mark" with aria-label describing supporting claims.
 */

import type { TextSegment } from '../../hooks/useNarrativeData'

interface HighlightSpanProps {
  segment: TextSegment
  isSelected: boolean
  onClick: () => void
  claimNames?: string[]
}

/**
 * Convert hex color to rgba with given alpha.
 */
function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/**
 * Build background CSS for the highlight.
 * Single color: solid rgba background.
 * Multiple colors: stacked linear-gradient bands per D-10.
 */
function buildBackground(colors: string[]): string {
  if (colors.length === 0) return 'transparent'
  if (colors.length === 1) return hexToRgba(colors[0], 0.3)

  const bandSize = 100 / colors.length
  const stops = colors
    .map((c, i) => {
      const start = i * bandSize
      const end = (i + 1) * bandSize
      return `${hexToRgba(c, 0.25)} ${start}% ${end}%`
    })
    .join(', ')

  return `linear-gradient(180deg, ${stops})`
}

export function HighlightSpan({
  segment,
  isSelected,
  onClick,
  claimNames,
}: HighlightSpanProps) {
  const background = buildBackground(segment.colors)
  const ariaLabel = claimNames?.length
    ? `Text supporting: ${claimNames.join(', ')}`
    : `Annotated text with ${segment.claimIds.length} claim(s)`

  return (
    <span
      role="mark"
      aria-label={ariaLabel}
      data-claim-ids={segment.claimIds.join(',')}
      onClick={onClick}
      style={{
        background,
        cursor: 'pointer',
        borderBottom: isSelected ? '2px solid currentColor' : undefined,
        borderRadius: '2px',
        padding: '0 1px',
      }}
      className="transition-colors hover:opacity-80"
    >
      {segment.text}
    </span>
  )
}
