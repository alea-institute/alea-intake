/**
 * MatrixCell -- individual cell in the fact-by-element matrix.
 *
 * Per D-07:
 * - Color from 5-level CONFIDENCE_SCALE at 20% opacity background
 * - Numeric confidence value (e.g., "85") as small monospace text
 * - Null mapping renders diagonal stripe gap pattern
 * - Click triggers detail panel
 * - Hover shows confidence, rationale, source span
 */

import { getConfidenceLevel } from '../../palette'
import type { MatrixCell as MatrixCellType } from '../../types'

interface MatrixCellProps {
  mapping: MatrixCellType | null
  onClick: (mapping: MatrixCellType) => void
}

export function MatrixCell({ mapping, onClick }: MatrixCellProps) {
  if (mapping === null) {
    return (
      <div
        role="gridcell"
        aria-label="No mapping (gap)"
        className="flex h-10 w-20 items-center justify-center border border-border/40"
        style={{
          background:
            'repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(0,0,0,0.08) 4px, rgba(0,0,0,0.08) 8px)',
          minWidth: 80,
          minHeight: 40,
        }}
      />
    )
  }

  const level = getConfidenceLevel(mapping.confidence)
  const pct = Math.round(mapping.confidence * 100)

  return (
    <div
      role="gridcell"
      aria-label={`${level.label}: ${pct}% confidence`}
      title={`${level.label} (${pct}%)${mapping.rationale ? ` - ${mapping.rationale}` : ''}`}
      className="flex h-10 w-20 cursor-pointer items-center justify-center border border-border/40 transition-shadow hover:shadow-md"
      style={{
        backgroundColor: `${level.color}33`,
        minWidth: 80,
        minHeight: 40,
      }}
      onClick={() => onClick(mapping)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick(mapping)
        }
      }}
      tabIndex={0}
    >
      <span className="font-mono text-xs font-semibold text-foreground">
        {pct}
      </span>
    </div>
  )
}
