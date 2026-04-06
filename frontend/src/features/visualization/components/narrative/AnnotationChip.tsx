/**
 * AnnotationChip -- margin annotation chip with claim abbreviation (D-09).
 *
 * Small pill positioned in the right margin showing the first 3 characters
 * of the claim name plus a colored dot. Click opens detail panel for that claim.
 * Hidden on mobile (< md breakpoint) per D-16.
 */

interface AnnotationChipProps {
  claimName: string
  color: string
  onClick: () => void
}

export function AnnotationChip({ claimName, color, onClick }: AnnotationChipProps) {
  const abbrev = claimName.slice(0, 3)

  return (
    <button
      type="button"
      data-testid="annotation-chip"
      onClick={onClick}
      className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-2 py-0.5 text-xs font-medium text-foreground shadow-sm transition-colors hover:bg-accent"
    >
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: color }}
        aria-hidden="true"
      />
      {abbrev}
    </button>
  )
}
