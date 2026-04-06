/**
 * Detail slide-out panel using shadcn Sheet (D-03).
 *
 * Opens from the right side, showing full details of the selected
 * visualization item (fact, claim, element, or gap). Includes type badge,
 * confidence score, connected edges, and source spans via SourceSpanViewer.
 */

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { NODE_TYPE_COLORS } from '../palette'
import { getConfidenceLevel } from '../palette'
import { SourceSpanViewer } from './SourceSpanViewer'
import type {
  NodeType,
  VisualizationData,
  VisualizationFact,
  VisualizationClaim,
  VisualizationElement,
  VisualizationGap,
} from '../types'

type SelectedItem =
  | { type: 'fact'; data: VisualizationFact }
  | { type: 'claim'; data: VisualizationClaim }
  | { type: 'element'; data: VisualizationElement; claimName?: string }
  | { type: 'gap'; data: VisualizationGap }

interface DetailPanelProps {
  selectedItem: SelectedItem | null
  onClose: () => void
  vizData?: VisualizationData
}

export function DetailPanel({ selectedItem, onClose, vizData }: DetailPanelProps) {
  const isOpen = selectedItem !== null

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-[400px] overflow-y-auto sm:max-w-[400px]">
        {selectedItem && (
          <>
            <SheetHeader>
              <div className="flex items-center gap-2">
                <TypeBadge type={selectedItem.type} />
                <SheetTitle className="text-base">
                  {getTitle(selectedItem)}
                </SheetTitle>
              </div>
              <SheetDescription>
                {getDescription(selectedItem)}
              </SheetDescription>
            </SheetHeader>

            <div className="mt-4 space-y-4">
              {/* Confidence score */}
              {'confidence' in selectedItem.data && selectedItem.data.confidence != null && (
                <ConfidenceBadge confidence={selectedItem.data.confidence as number} />
              )}
              {'satisfaction_confidence' in selectedItem.data && selectedItem.data.satisfaction_confidence != null && (
                <ConfidenceBadge confidence={selectedItem.data.satisfaction_confidence as number} />
              )}

              {/* Type-specific content */}
              {selectedItem.type === 'fact' && (
                <FactDetail fact={selectedItem.data} vizData={vizData} />
              )}
              {selectedItem.type === 'claim' && (
                <ClaimDetail claim={selectedItem.data} />
              )}
              {selectedItem.type === 'element' && (
                <ElementDetail element={selectedItem.data} claimName={selectedItem.claimName} />
              )}
              {selectedItem.type === 'gap' && (
                <GapDetail gap={selectedItem.data} />
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TypeBadge({ type }: { type: NodeType }) {
  const color = NODE_TYPE_COLORS[type]
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold text-white"
      style={{ backgroundColor: color }}
    >
      {type}
    </span>
  )
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const level = getConfidenceLevel(confidence)
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground">Confidence:</span>
      <span
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white"
        style={{ backgroundColor: level.color }}
      >
        {level.label} ({Math.round(confidence * 100)}%)
      </span>
    </div>
  )
}

function FactDetail({
  fact,
  vizData,
}: {
  fact: VisualizationFact
  vizData?: VisualizationData
}) {
  return (
    <div className="space-y-3">
      <div>
        <span className="text-xs font-medium text-muted-foreground">Assertion</span>
        <p className="text-sm">{fact.assertion_text}</p>
      </div>
      <div>
        <span className="text-xs font-medium text-muted-foreground">Type</span>
        <p className="text-sm">{fact.fact_type}</p>
      </div>
      {vizData && (
        <SourceSpanViewer
          sourceSpans={fact.source_spans}
          messages={vizData.messages}
        />
      )}
    </div>
  )
}

function ClaimDetail({ claim }: { claim: VisualizationClaim }) {
  return (
    <div className="space-y-3">
      {claim.jurisdiction && (
        <div>
          <span className="text-xs font-medium text-muted-foreground">Jurisdiction</span>
          <p className="text-sm">{claim.jurisdiction}</p>
        </div>
      )}
      {claim.rationale && (
        <div>
          <span className="text-xs font-medium text-muted-foreground">Rationale</span>
          <p className="text-sm">{claim.rationale}</p>
        </div>
      )}
      {claim.elements.length > 0 && (
        <div>
          <span className="text-xs font-medium text-muted-foreground">
            Elements ({claim.elements.length})
          </span>
          <ul className="mt-1 space-y-1">
            {claim.elements.map((elem) => (
              <li key={elem.id} className="flex items-center gap-2 text-sm">
                <span
                  className={`h-2 w-2 rounded-full ${
                    elem.is_satisfied ? 'bg-green-500' : 'bg-red-400'
                  }`}
                />
                {elem.element_name}
                {elem.satisfaction_confidence != null && (
                  <span className="text-xs text-muted-foreground">
                    ({Math.round(elem.satisfaction_confidence * 100)}%)
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function ElementDetail({
  element,
  claimName,
}: {
  element: VisualizationElement
  claimName?: string
}) {
  return (
    <div className="space-y-3">
      {claimName && (
        <div>
          <span className="text-xs font-medium text-muted-foreground">Claim</span>
          <p className="text-sm">{claimName}</p>
        </div>
      )}
      <div>
        <span className="text-xs font-medium text-muted-foreground">Satisfied</span>
        <p className="text-sm">{element.is_satisfied ? 'Yes' : 'No'}</p>
      </div>
      {element.element_description && (
        <div>
          <span className="text-xs font-medium text-muted-foreground">Description</span>
          <p className="text-sm">{element.element_description}</p>
        </div>
      )}
    </div>
  )
}

function GapDetail({ gap }: { gap: VisualizationGap }) {
  return (
    <div className="space-y-3">
      <div>
        <span className="text-xs font-medium text-muted-foreground">Gap Type</span>
        <p className="text-sm">{gap.gap_type}</p>
      </div>
      <div>
        <span className="text-xs font-medium text-muted-foreground">Description</span>
        <p className="text-sm">{gap.description}</p>
      </div>
      <div className="flex items-center gap-4">
        <div>
          <span className="text-xs font-medium text-muted-foreground">Priority</span>
          <p className="text-sm">{gap.priority}</p>
        </div>
        <div>
          <span className="text-xs font-medium text-muted-foreground">Status</span>
          <p className="text-sm">{gap.status}</p>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getTitle(item: SelectedItem): string {
  switch (item.type) {
    case 'fact':
      return item.data.assertion_text.slice(0, 60) + (item.data.assertion_text.length > 60 ? '...' : '')
    case 'claim':
      return item.data.claim_name
    case 'element':
      return item.data.element_name
    case 'gap':
      return `Gap: ${item.data.gap_type}`
  }
}

function getDescription(item: SelectedItem): string {
  switch (item.type) {
    case 'fact':
      return `${item.data.fact_type} fact`
    case 'claim':
      return `${item.data.claim_type} claim`
    case 'element':
      return item.data.is_satisfied ? 'Satisfied' : 'Not satisfied'
    case 'gap':
      return item.data.description.slice(0, 80) + (item.data.description.length > 80 ? '...' : '')
  }
}

export type { SelectedItem }
