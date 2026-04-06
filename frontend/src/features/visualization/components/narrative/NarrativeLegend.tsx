/**
 * NarrativeLegend -- color-to-claim legend bar (D-10).
 *
 * Horizontal bar at top of narrative view. Each entry shows a
 * 16x16 color swatch + claim name text. Wraps on narrow screens.
 * ARIA: role="list" for legend items.
 */

import type { LegendEntry } from '../../hooks/useNarrativeData'

interface NarrativeLegendProps {
  legend: LegendEntry[]
}

export function NarrativeLegend({ legend }: NarrativeLegendProps) {
  if (legend.length === 0) return null

  return (
    <div
      data-testid="narrative-legend"
      className="mb-4 flex flex-wrap items-center gap-4 rounded-lg border border-border bg-card px-4 py-2"
      role="list"
      aria-label="Claim color legend"
    >
      {legend.map((entry) => (
        <div
          key={entry.claimId}
          className="flex items-center gap-2"
          role="listitem"
        >
          <span
            className="inline-block h-4 w-4 rounded-sm"
            style={{ backgroundColor: entry.color }}
            aria-hidden="true"
          />
          <span className="text-sm text-foreground">{entry.claimName}</span>
        </div>
      ))}
    </div>
  )
}
