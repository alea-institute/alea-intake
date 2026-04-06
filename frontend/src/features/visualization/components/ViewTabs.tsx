/**
 * Three-tab switcher for visualization views: Graph | Matrix | Narrative.
 *
 * Uses shadcn Tabs with ARIA-correct tablist/tab/tabpanel association (D-12).
 * Reads activeView from store and dispatches setActiveView on tab change.
 * Children are rendered inside the matching TabsContent.
 */

import type { ReactNode } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useVisualizationStore } from '../store'
import type { ViewType } from '../types'

interface ViewTabsProps {
  graphView?: ReactNode
  matrixView?: ReactNode
  narrativeView?: ReactNode
}

const VIEW_LABELS: Record<ViewType, string> = {
  graph: 'Graph',
  matrix: 'Matrix',
  narrative: 'Narrative',
}

export function ViewTabs({ graphView, matrixView, narrativeView }: ViewTabsProps) {
  const activeView = useVisualizationStore((s) => s.activeView)
  const setActiveView = useVisualizationStore((s) => s.setActiveView)

  return (
    <Tabs
      value={activeView}
      onValueChange={(v) => setActiveView(v as ViewType)}
      className="w-full"
    >
      <TabsList aria-label="Visualization views">
        {(Object.keys(VIEW_LABELS) as ViewType[]).map((view) => (
          <TabsTrigger key={view} value={view}>
            {VIEW_LABELS[view]}
          </TabsTrigger>
        ))}
      </TabsList>

      <TabsContent value="graph">{graphView}</TabsContent>
      <TabsContent value="matrix">{matrixView}</TabsContent>
      <TabsContent value="narrative">{narrativeView}</TabsContent>
    </Tabs>
  )
}
