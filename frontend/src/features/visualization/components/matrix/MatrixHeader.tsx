/**
 * MatrixHeader -- sticky claim/element column headers.
 *
 * Per D-06:
 * - Row 1: claim names as group headers spanning element columns
 * - Row 2: individual element column headers
 * - Collapse toggle on each claim group
 * - Gap columns show warning icon
 *
 * Per D-08:
 * - position: sticky, top: 0, z-index for pinning during scroll
 */

import { ChevronDown, ChevronRight, TriangleAlert } from 'lucide-react'
import type { ClaimGroup } from '../../hooks/useMatrixData'

interface MatrixHeaderProps {
  columnGroups: ClaimGroup[]
  onToggleCollapse: (claimId: number) => void
  /** Width of the frozen fact-label column on the left */
  factLabelWidth?: number
}

export function MatrixHeader({
  columnGroups,
  onToggleCollapse,
  factLabelWidth = 200,
}: MatrixHeaderProps) {
  return (
    <div
      className="sticky top-0 z-20 bg-background"
      role="rowgroup"
      aria-label="Column headers"
    >
      {/* Row 1: Claim group headers */}
      <div className="flex" role="row">
        {/* Empty corner cell above fact labels */}
        <div
          className="sticky left-0 z-30 shrink-0 border-b border-r border-border bg-background"
          style={{ width: factLabelWidth, minWidth: factLabelWidth }}
          role="columnheader"
          aria-label="Facts"
        />

        {columnGroups.map((group) => (
          <div
            key={group.claimId}
            className="flex items-center border-b border-r border-border bg-muted/50 px-2"
            style={{ width: group.collapsed ? 40 : group.columns.length * 80 }}
            role="columnheader"
            aria-label={group.claimName}
          >
            <button
              type="button"
              className="mr-1 flex h-6 w-6 shrink-0 items-center justify-center rounded hover:bg-muted"
              onClick={() => onToggleCollapse(group.claimId)}
              aria-label={`${group.collapsed ? 'Expand' : 'Collapse'} ${group.claimName}`}
            >
              {group.collapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>
            {!group.collapsed && (
              <span className="truncate text-xs font-semibold">
                {group.claimName}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Row 2: Element column headers */}
      <div className="flex" role="row">
        {/* Empty cell under the corner */}
        <div
          className="sticky left-0 z-30 shrink-0 border-b border-r border-border bg-background"
          style={{ width: factLabelWidth, minWidth: factLabelWidth }}
          role="columnheader"
        />

        {columnGroups.map((group) =>
          group.collapsed ? (
            <div
              key={`collapsed-${group.claimId}`}
              className="h-8 border-b border-r border-border bg-muted/30"
              style={{ width: 40 }}
              role="columnheader"
            />
          ) : (
            group.columns.map((col) => (
              <div
                key={col.elementId}
                className="flex h-8 w-20 items-center gap-1 border-b border-r border-border px-1"
                role="columnheader"
                aria-label={col.elementName}
              >
                <span className="truncate text-xs">{col.elementName}</span>
                {col.isGap && (
                  <TriangleAlert
                    className="h-3 w-3 shrink-0 text-amber-500"
                    data-testid="gap-warning"
                    aria-label="Gap: no supporting evidence"
                  />
                )}
              </div>
            ))
          )
        )}
      </div>
    </div>
  )
}
