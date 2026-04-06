/**
 * MatrixView -- bidirectional virtual grid for fact-by-element matrix.
 *
 * Per D-06: facts as rows, elements as columns grouped by claim.
 * Per D-07: color-coded cells with confidence values, gap stripes.
 * Per D-08: @tanstack/react-virtual for row/column virtualization,
 *           sticky headers outside virtual container.
 * Per D-16: mobile responsive with rotated layout.
 */

import { useRef, useState, useCallback } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useMatrixData } from '../../hooks/useMatrixData'
import { useVisualizationStore } from '../../store'
import { MatrixCell } from './MatrixCell'
import { MatrixHeader } from './MatrixHeader'
import type { VisualizationData, MatrixCell as MatrixCellType } from '../../types'
import type { ClaimGroup } from '../../hooks/useMatrixData'

interface MatrixViewProps {
  data: VisualizationData | undefined
  onCellSelect?: (cell: MatrixCellType) => void
}

const FACT_LABEL_WIDTH = 200
const ROW_HEIGHT = 40
const COL_WIDTH = 80
const ROW_OVERSCAN = 10
const COL_OVERSCAN = 5

export function MatrixView({ data, onCellSelect }: MatrixViewProps) {
  const { rows, columnGroups, getCellData } = useMatrixData(data)
  const setMatrixState = useVisualizationStore((s) => s.setMatrixState)

  // Collapse state managed locally (not in Zustand for simplicity)
  const [collapsedClaims, setCollapsedClaims] = useState<Set<number>>(new Set())

  const toggleCollapse = useCallback((claimId: number) => {
    setCollapsedClaims((prev) => {
      const next = new Set(prev)
      if (next.has(claimId)) {
        next.delete(claimId)
      } else {
        next.add(claimId)
      }
      return next
    })
  }, [])

  // Apply collapse state to column groups
  const visibleGroups: ClaimGroup[] = columnGroups.map((g) => ({
    ...g,
    collapsed: collapsedClaims.has(g.claimId),
  }))

  // Flatten visible columns (non-collapsed)
  const flatColumns = visibleGroups.flatMap((g) =>
    g.collapsed ? [] : g.columns
  )

  // Scroll container ref
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const headerScrollRef = useRef<HTMLDivElement>(null)

  // Row virtualizer
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: ROW_OVERSCAN,
  })

  // Column virtualizer (horizontal)
  const colVirtualizer = useVirtualizer({
    count: flatColumns.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => COL_WIDTH,
    horizontal: true,
    overscan: COL_OVERSCAN,
  })

  // Sync horizontal scroll between header and body
  const handleScroll = useCallback(() => {
    if (scrollContainerRef.current && headerScrollRef.current) {
      headerScrollRef.current.scrollLeft = scrollContainerRef.current.scrollLeft
    }
  }, [])

  // Handle cell click
  const handleCellClick = useCallback(
    (cell: MatrixCellType) => {
      setMatrixState({
        selectedCell: { factId: cell.factId, elementId: cell.elementId },
      })
      onCellSelect?.(cell)
    },
    [setMatrixState, onCellSelect]
  )

  if (!data || rows.length === 0) {
    return (
      <div
        role="grid"
        className="flex h-64 items-center justify-center text-muted-foreground"
      >
        No matrix data available
      </div>
    )
  }

  return (
    <div className="flex flex-col" role="grid" aria-label="Fact-element completeness matrix">
      {/* Sticky header -- scrolls horizontally in sync */}
      <div
        ref={headerScrollRef}
        className="overflow-hidden"
        style={{ marginLeft: 0 }}
      >
        <MatrixHeader
          columnGroups={visibleGroups}
          onToggleCollapse={toggleCollapse}
          factLabelWidth={FACT_LABEL_WIDTH}
        />
      </div>

      {/* Scrollable body with virtual rows and columns */}
      <div
        ref={scrollContainerRef}
        className="overflow-auto"
        style={{ height: 'calc(100vh - 280px)', maxHeight: 600 }}
        onScroll={handleScroll}
      >
        <div
          style={{
            height: rowVirtualizer.getTotalSize(),
            width: FACT_LABEL_WIDTH + colVirtualizer.getTotalSize(),
            position: 'relative',
          }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const row = rows[virtualRow.index]
            return (
              <div
                key={row.factId}
                role="row"
                className="absolute left-0 flex"
                style={{
                  top: virtualRow.start,
                  height: ROW_HEIGHT,
                  width: FACT_LABEL_WIDTH + colVirtualizer.getTotalSize(),
                }}
              >
                {/* Sticky fact label */}
                <div
                  className="sticky left-0 z-10 flex shrink-0 items-center border-b border-r border-border bg-background px-2"
                  style={{
                    width: FACT_LABEL_WIDTH,
                    minWidth: FACT_LABEL_WIDTH,
                    height: ROW_HEIGHT,
                  }}
                  role="rowheader"
                  title={row.label}
                >
                  <span className="truncate text-xs">{row.label}</span>
                </div>

                {/* Virtual columns */}
                {colVirtualizer.getVirtualItems().map((virtualCol) => {
                  const col = flatColumns[virtualCol.index]
                  const cellData = getCellData(row.factId, col.elementId)

                  return (
                    <div
                      key={`${row.factId}-${col.elementId}`}
                      className="absolute"
                      style={{
                        left: FACT_LABEL_WIDTH + virtualCol.start,
                        width: COL_WIDTH,
                        height: ROW_HEIGHT,
                      }}
                    >
                      <MatrixCell
                        mapping={cellData}
                        onClick={handleCellClick}
                      />
                    </div>
                  )
                })}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
