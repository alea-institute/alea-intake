/**
 * VisualizationPage -- route entry page composing all visualization components.
 *
 * Connects Graph, Matrix, and Narrative views into a single page with:
 * - ViewTabs for tab switching (D-12)
 * - FilterBar for shared filter controls (D-13)
 * - DetailPanel for slide-out item details (D-03)
 * - Export dropdown with per-view format options (D-17)
 * - Accessible table toggle (D-14)
 * - URL sync for active tab via ?view= param (D-12)
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { EmptyState } from '@/shared/components/EmptyState'
import { useVisualizationData } from './api'
import { useVisualizationStore } from './store'
import { useGraphData } from './hooks/useGraphData'
import { useMatrixData } from './hooks/useMatrixData'
import { useExport } from './hooks/useExport'
import { ViewTabs } from './components/ViewTabs'
import { FilterBar } from './components/FilterBar'
import { DetailPanel } from './components/DetailPanel'
import { AccessibleTable } from './components/AccessibleTable'
import { GraphView } from './components/graph/GraphView'
import { MatrixView } from './components/matrix/MatrixView'
import { NarrativeView } from './components/narrative/NarrativeView'
import type { ViewType } from './types'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const VALID_VIEWS: ViewType[] = ['graph', 'matrix', 'narrative']

function isValidView(v: string | null): v is ViewType {
  return v !== null && VALID_VIEWS.includes(v as ViewType)
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function VisualizationPage() {
  const { id = '' } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()

  // Data fetching
  const { data, isLoading, isError, error, refetch } = useVisualizationData(id)

  // Store state
  const activeView = useVisualizationStore((s) => s.activeView)
  const setActiveView = useVisualizationStore((s) => s.setActiveView)

  // Accessible table toggle state
  const [showAccessibleTable, setShowAccessibleTable] = useState(false)

  // Graph data hook (for passing to GraphView)
  const graphData = useGraphData(data)
  const matrixData = useMatrixData(data)

  // Export hook
  const { exportGraph, exportMatrixCSV, exportMatrixPNG, exportNarrativePDF } =
    useExport(id)

  // Refs for export targets
  const graphRef = useRef<HTMLDivElement>(null)
  const matrixRef = useRef<HTMLDivElement>(null)

  // URL sync: read ?view= param on mount to set initial activeView (D-12)
  useEffect(() => {
    const viewParam = searchParams.get('view')
    if (isValidView(viewParam) && viewParam !== activeView) {
      setActiveView(viewParam)
    }
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ARIA announcement for view changes
  const [announcement, setAnnouncement] = useState('')

  useEffect(() => {
    setAnnouncement(`Switched to ${activeView} view`)
  }, [activeView])

  // Reset accessible table toggle when switching views
  useEffect(() => {
    setShowAccessibleTable(false)
  }, [activeView])

  // ---------------------------------------------------------------------------
  // Export handlers
  // ---------------------------------------------------------------------------

  const handleExport = async (format: string) => {
    switch (format) {
      case 'graph-svg':
        if (graphRef.current) await exportGraph(graphRef.current, 'svg')
        break
      case 'graph-png':
        if (graphRef.current) await exportGraph(graphRef.current, 'png')
        break
      case 'matrix-csv':
        exportMatrixCSV(
          matrixData.rows,
          matrixData.columnGroups,
          matrixData.getCellData
        )
        break
      case 'matrix-png':
        if (matrixRef.current) await exportMatrixPNG(matrixRef.current)
        break
      case 'narrative-pdf':
        if (data) exportNarrativePDF(data)
        break
    }
  }

  // Build export menu items based on active view
  const exportMenuItems = useMemo(() => {
    switch (activeView) {
      case 'graph':
        return [
          { label: 'Export as SVG', key: 'graph-svg' },
          { label: 'Export as PNG', key: 'graph-png' },
        ]
      case 'matrix':
        return [
          { label: 'Export as CSV', key: 'matrix-csv' },
          { label: 'Export as PNG', key: 'matrix-png' },
        ]
      case 'narrative':
        return [{ label: 'Export as PDF', key: 'narrative-pdf' }]
    }
  }, [activeView])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <main className="flex-1 overflow-auto p-[24px]">
      <div className="mx-auto max-w-7xl space-y-[16px]">
        {/* Header: title + export + a11y toggle */}
        <header className="flex flex-wrap items-center justify-between gap-[8px]">
          <h1 className="font-display text-[28px] font-semibold leading-[1.2]">
            Analysis Visualization
          </h1>

          {data && (
            <div className="flex gap-[8px]">
              {/* Export dropdown (D-17) */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" aria-label="Export">
                    Export
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {exportMenuItems.map((item) => (
                    <DropdownMenuItem
                      key={item.key}
                      onSelect={() => handleExport(item.key)}
                    >
                      {item.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Accessible table toggle (D-14) */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAccessibleTable((prev) => !prev)}
                aria-label={
                  showAccessibleTable
                    ? 'Switch to visualization view'
                    : 'Switch to accessible table view'
                }
                aria-pressed={showAccessibleTable}
              >
                {showAccessibleTable ? 'Visualization' : 'Table View'}
              </Button>
            </div>
          )}
        </header>

        {/* ARIA live region for announcements (D-14) */}
        <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
          {announcement}
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="space-y-[8px]" data-testid="loading-skeleton">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        )}

        {/* Error state */}
        {isError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
            <p className="text-sm text-destructive">
              {error?.message ?? 'Failed to load visualization data'}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => refetch()}
            >
              Retry
            </Button>
          </div>
        )}

        {/* Empty state */}
        {data && data.claims.length === 0 && !isLoading && (
          <EmptyState
            heading="No analysis data"
            body="Complete an intake conversation to generate the analysis visualization."
          />
        )}

        {/* Main content */}
        {data && data.claims.length > 0 && (
          <>
            {/* Filter bar (D-13) */}
            <FilterBar data={data} />

            {/* View content */}
            {showAccessibleTable ? (
              <AccessibleTable mode={activeView} data={data} />
            ) : (
              <ViewTabs
                graphView={
                  <div ref={graphRef}>
                    <GraphView
                      nodes={graphData.nodes}
                      links={graphData.links}
                      ghostedNodeIds={graphData.ghostedNodeIds}
                      width={900}
                      height={600}
                      selectedNodeId={
                        useVisualizationStore.getState().graphState.selectedNodeId
                      }
                      onNodeClick={(nodeId) =>
                        useVisualizationStore
                          .getState()
                          .setGraphState({ selectedNodeId: nodeId })
                      }
                    />
                  </div>
                }
                matrixView={
                  <div ref={matrixRef}>
                    <MatrixView data={data} />
                  </div>
                }
                narrativeView={<NarrativeView data={data} />}
              />
            )}

            {/* Detail panel (slide-out) */}
            <DetailPanel
              selectedItem={null}
              onClose={() => {}}
              vizData={data}
            />
          </>
        )}
      </div>
    </main>
  )
}
