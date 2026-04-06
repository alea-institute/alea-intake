/**
 * NarrativeView -- annotated text container with margin annotations and legend (D-09).
 *
 * Renders the consumer's original text with claim-colored highlights.
 * Desktop: margin chips positioned to the right of highlight spans.
 * Mobile (< md): no margin chips, inline expansion on highlight click.
 * Popover detail on click shows supporting claims, confidence, and source link.
 */

import { useState, useCallback, useMemo, useRef, useLayoutEffect } from 'react'
import type { VisualizationData } from '../../types'
import { useNarrativeData } from '../../hooks/useNarrativeData'
import type { MessageAnnotation } from '../../hooks/useNarrativeData'
import { useVisualizationStore } from '../../store'
import { HighlightSpan } from './HighlightSpan'
import { AnnotationChip } from './AnnotationChip'
import { NarrativeLegend } from './NarrativeLegend'

interface NarrativeViewProps {
  data: VisualizationData
}

interface ChipPosition {
  claimId: number
  claimName: string
  color: string
  top: number
}

const SENDER_LABELS: Record<string, string> = {
  consumer: 'Consumer',
  professional: 'Professional',
  system: 'System',
}

export function NarrativeView({ data }: NarrativeViewProps) {
  const { messageTexts, legend, claimColorMap } = useNarrativeData(data)
  const { setNarrativeState, narrativeState } = useVisualizationStore()
  const [expandedSpan, setExpandedSpan] = useState<string | null>(null)
  const messageRefs = useRef<Map<number, HTMLDivElement>>(new Map())
  const [chipPositions, setChipPositions] = useState<Map<number, ChipPosition[]>>(
    new Map()
  )

  // Memoize claim name lookup to avoid infinite effect loops
  const claimNameMap = useMemo(
    () => new Map(data.claims.map((c) => [c.id, c.claim_name])),
    [data.claims]
  )

  // Calculate chip positions after render using layout effect
  // Depends only on stable references (messageTexts is memoized in hook)
  useLayoutEffect(() => {
    const newPositions = new Map<number, ChipPosition[]>()

    for (const msg of messageTexts) {
      const container = messageRefs.current.get(msg.messageId)
      if (!container) continue

      const chips: ChipPosition[] = []
      const marks = container.querySelectorAll<HTMLElement>('[role="mark"]')

      marks.forEach((mark) => {
        const rect = mark.getBoundingClientRect()
        const containerRect = container.getBoundingClientRect()
        const top = rect.top - containerRect.top

        const claimIdsStr = mark.getAttribute('data-claim-ids')
        if (!claimIdsStr) return

        const claimIds = claimIdsStr.split(',').map(Number)
        for (const claimId of claimIds) {
          const existing = chips.find(
            (c) => c.claimId === claimId && Math.abs(c.top - top) < 10
          )
          if (existing) continue

          chips.push({
            claimId,
            claimName: claimNameMap.get(claimId) ?? `Claim ${claimId}`,
            color: claimColorMap.get(claimId) ?? '#888888',
            top,
          })
        }
      })

      newPositions.set(msg.messageId, chips)
    }

    setChipPositions(newPositions)
  }, [messageTexts, claimColorMap, claimNameMap])

  const handleSpanClick = useCallback(
    (segKey: string) => {
      setNarrativeState({ selectedSpanId: segKey })
      setExpandedSpan((prev) => (prev === segKey ? null : segKey))
    },
    [setNarrativeState]
  )

  const handleChipClick = useCallback(
    (claimId: number) => {
      setNarrativeState({
        selectedSpanId: `chip-${claimId}`,
      })
    },
    [setNarrativeState]
  )

  return (
    <div className="mx-auto max-w-3xl" aria-live="polite">
      {/* Legend at top */}
      <NarrativeLegend legend={legend} />

      {/* Messages */}
      <div className="space-y-6">
        {messageTexts.map((msg) => (
          <MessageBlock
            key={msg.messageId}
            msg={msg}
            claimNameMap={claimNameMap}
            claimColorMap={claimColorMap}
            selectedSpanId={narrativeState.selectedSpanId}
            expandedSpan={expandedSpan}
            chipPositions={chipPositions.get(msg.messageId) ?? []}
            onSpanClick={handleSpanClick}
            onChipClick={handleChipClick}
            onRefSet={(id, el) => messageRefs.current.set(id, el)}
            data={data}
          />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MessageBlock sub-component
// ---------------------------------------------------------------------------

interface MessageBlockProps {
  msg: MessageAnnotation
  claimNameMap: Map<number, string>
  claimColorMap: Map<number, string>
  selectedSpanId: string | null
  expandedSpan: string | null
  chipPositions: ChipPosition[]
  onSpanClick: (segKey: string) => void
  onChipClick: (claimId: number) => void
  onRefSet: (messageId: number, el: HTMLDivElement) => void
  data: VisualizationData
}

function MessageBlock({
  msg,
  claimNameMap,
  claimColorMap,
  selectedSpanId,
  expandedSpan,
  chipPositions,
  onSpanClick,
  onChipClick,
  onRefSet,
  data,
}: MessageBlockProps) {
  const senderLabel = SENDER_LABELS[msg.senderType] ?? msg.senderType

  return (
    <div
      data-message-id={msg.messageId}
      className="relative"
    >
      {/* Sender label */}
      <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {senderLabel}
      </div>

      {/* Text with annotations + margin */}
      <div className="flex">
        {/* Text column */}
        <div
          ref={(el) => { if (el) onRefSet(msg.messageId, el) }}
          className="flex-1 text-sm leading-relaxed text-foreground md:mr-36"
        >
          {msg.segments.map((seg) => {
            const segKey = `${msg.messageId}-${seg.start}-${seg.end}`

            if (!seg.isAnnotated) {
              return <span key={segKey}>{seg.text}</span>
            }

            const claimNames = seg.claimIds.map(
              (id) => claimNameMap.get(id) ?? `Claim ${id}`
            )

            return (
              <span key={segKey}>
                <HighlightSpan
                  segment={seg}
                  isSelected={selectedSpanId === segKey}
                  onClick={() => onSpanClick(segKey)}
                  claimNames={claimNames}
                />
                {/* Inline expansion for mobile (and selected state) */}
                {expandedSpan === segKey && (
                  <span className="block rounded-md border border-border bg-card p-2 text-xs shadow-sm md:hidden">
                    <span className="font-semibold">Supporting claims:</span>
                    <ul className="mt-1 space-y-0.5">
                      {seg.claimIds.map((cid) => {
                        const claim = data.claims.find((c) => c.id === cid)
                        return (
                          <li key={cid} className="flex items-center gap-1">
                            <span
                              className="inline-block h-2 w-2 rounded-full"
                              style={{
                                backgroundColor:
                                  claimColorMap.get(cid) ?? '#888',
                              }}
                            />
                            {claimNameMap.get(cid)}
                            {claim && (
                              <span className="text-muted-foreground">
                                {' '}
                                ({Math.round(claim.confidence * 100)}%)
                              </span>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  </span>
                )}
              </span>
            )
          })}
        </div>

        {/* Margin chips (desktop only) */}
        <div
          data-testid="margin-chips"
          className="relative hidden w-32 md:block"
        >
          {chipPositions.map((chip, idx) => (
            <div
              key={`${chip.claimId}-${idx}`}
              className="absolute left-2"
              style={{ top: chip.top }}
            >
              <AnnotationChip
                claimName={chip.claimName}
                color={chip.color}
                onClick={() => onChipClick(chip.claimId)}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
