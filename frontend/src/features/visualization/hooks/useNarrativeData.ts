/**
 * useNarrativeData hook -- transforms VisualizationData into non-overlapping
 * annotation segments using a sweep-line algorithm (Pitfall 4 avoidance).
 *
 * Algorithm:
 * 1. For each message, collect all source_spans referencing that message_id
 * 2. For each span, look up fact_id -> find mappings -> get claim_ids
 * 3. Build boundary "events" at each character position
 * 4. Sweep through events tracking an "active claims" set
 * 5. At each position change, emit a TextSegment with current active claims
 * 6. Assign colors stably using claim index into CATEGORICAL_PALETTE
 * 7. Apply filters: activeLayers and claimFilter
 */

import { useMemo } from 'react'
import type { VisualizationData } from '../types'
import { CATEGORICAL_PALETTE } from '../palette'
import { useVisualizationStore } from '../store'

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface TextSegment {
  start: number
  end: number
  text: string
  claimIds: number[]
  factIds: number[]
  colors: string[]
  isAnnotated: boolean
}

export interface MessageAnnotation {
  messageId: number
  text: string
  senderType: string
  segments: TextSegment[]
}

export interface LegendEntry {
  claimId: number
  claimName: string
  color: string
}

export interface NarrativeData {
  messageTexts: MessageAnnotation[]
  legend: LegendEntry[]
  claimColorMap: Map<number, string>
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

interface SweepEvent {
  position: number
  type: 'start' | 'end'
  claimId: number
  factId: number
}

/**
 * Build a stable claim -> color mapping using index into the palette.
 * The index is based on the order claims appear in the data (stable across renders).
 */
function buildClaimColorMap(
  claims: VisualizationData['claims']
): Map<number, string> {
  const map = new Map<number, string>()
  claims.forEach((claim, idx) => {
    map.set(claim.id, CATEGORICAL_PALETTE[idx % CATEGORICAL_PALETTE.length])
  })
  return map
}

/**
 * For a given message, collect all source spans from facts,
 * resolve their claim associations via mappings, and produce
 * non-overlapping TextSegments using a sweep-line algorithm.
 */
function buildSegmentsForMessage(
  messageId: number,
  messageText: string,
  data: VisualizationData,
  claimColorMap: Map<number, string>,
  allowedClaimIds: Set<number> | null
): TextSegment[] {
  // 1. Collect source spans for this message and map them to (factId, claimIds)
  const events: SweepEvent[] = []

  // Build fact -> claimIds lookup from mappings
  const factToClaimIds = new Map<number, Set<number>>()
  for (const mapping of data.mappings) {
    if (!factToClaimIds.has(mapping.fact_id)) {
      factToClaimIds.set(mapping.fact_id, new Set())
    }
    factToClaimIds.get(mapping.fact_id)!.add(mapping.claim_id)
  }

  for (const fact of data.facts) {
    for (const span of fact.source_spans) {
      if (span.message_id !== messageId) continue

      const claimIds = factToClaimIds.get(fact.id) ?? new Set<number>()
      for (const claimId of claimIds) {
        // Apply filter: skip claims not in allowedClaimIds
        if (allowedClaimIds !== null && !allowedClaimIds.has(claimId)) continue

        events.push({
          position: span.start_char,
          type: 'start',
          claimId,
          factId: fact.id,
        })
        events.push({
          position: span.end_char,
          type: 'end',
          claimId,
          factId: fact.id,
        })
      }
    }
  }

  // No events => entire message is plain text
  if (events.length === 0) {
    return [
      {
        start: 0,
        end: messageText.length,
        text: messageText,
        claimIds: [],
        factIds: [],
        colors: [],
        isAnnotated: false,
      },
    ]
  }

  // 2. Sort events: by position, then 'start' before 'end'
  events.sort((a, b) => {
    if (a.position !== b.position) return a.position - b.position
    // 'start' before 'end' so we add before removing at the same position
    if (a.type === 'start' && b.type === 'end') return -1
    if (a.type === 'end' && b.type === 'start') return 1
    return 0
  })

  // 3. Sweep through events, tracking active claims/facts
  const activeClaims = new Map<number, number>() // claimId -> count
  const activeFacts = new Map<number, number>() // factId -> count
  const segments: TextSegment[] = []

  // Collect all unique boundary positions
  const boundaries = new Set<number>()
  boundaries.add(0)
  boundaries.add(messageText.length)
  for (const event of events) {
    boundaries.add(event.position)
  }
  const sortedBoundaries = Array.from(boundaries).sort((a, b) => a - b)

  // Process events at each boundary
  let eventIdx = 0

  for (let i = 0; i < sortedBoundaries.length - 1; i++) {
    const segStart = sortedBoundaries[i]
    const segEnd = sortedBoundaries[i + 1]

    // Process all events at segStart position
    while (eventIdx < events.length && events[eventIdx].position === segStart) {
      const evt = events[eventIdx]
      if (evt.type === 'start') {
        activeClaims.set(evt.claimId, (activeClaims.get(evt.claimId) ?? 0) + 1)
        activeFacts.set(evt.factId, (activeFacts.get(evt.factId) ?? 0) + 1)
      } else {
        const claimCount = (activeClaims.get(evt.claimId) ?? 1) - 1
        if (claimCount <= 0) activeClaims.delete(evt.claimId)
        else activeClaims.set(evt.claimId, claimCount)

        const factCount = (activeFacts.get(evt.factId) ?? 1) - 1
        if (factCount <= 0) activeFacts.delete(evt.factId)
        else activeFacts.set(evt.factId, factCount)
      }
      eventIdx++
    }

    // Skip empty segments
    if (segStart === segEnd) continue

    const currentClaims = Array.from(activeClaims.keys()).sort((a, b) => a - b)
    const currentFacts = Array.from(activeFacts.keys()).sort((a, b) => a - b)
    const colors = currentClaims.map((cid) => claimColorMap.get(cid) ?? '#888888')

    segments.push({
      start: segStart,
      end: segEnd,
      text: messageText.slice(segStart, segEnd),
      claimIds: currentClaims,
      factIds: currentFacts,
      colors,
      isAnnotated: currentClaims.length > 0,
    })
  }

  return segments
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useNarrativeData(data: VisualizationData): NarrativeData {
  const { narrativeState, claimFilter, confidenceThreshold } =
    useVisualizationStore()

  return useMemo(() => {
    // Build stable claim color map
    const claimColorMap = buildClaimColorMap(data.claims)

    // Determine allowed claims based on filters
    let allowedClaimIds: Set<number> | null = null

    if (narrativeState.activeLayers.length > 0) {
      // activeLayers restricts which claims are visible
      allowedClaimIds = new Set(narrativeState.activeLayers)
    } else if (claimFilter.length > 0) {
      // claimFilter from shared filters
      allowedClaimIds = new Set(claimFilter)
    }

    // Filter by confidence threshold on claims
    if (confidenceThreshold > 0) {
      const confAllowed = new Set(
        data.claims
          .filter((c) => c.confidence >= confidenceThreshold)
          .map((c) => c.id)
      )
      if (allowedClaimIds !== null) {
        // Intersect with existing filter
        allowedClaimIds = new Set(
          Array.from(allowedClaimIds).filter((id) => confAllowed.has(id))
        )
      } else {
        allowedClaimIds = confAllowed
      }
    }

    // Build message annotations
    const messageTexts: MessageAnnotation[] = data.messages.map((msg) => ({
      messageId: msg.id,
      text: msg.content,
      senderType: msg.sender_type,
      segments: buildSegmentsForMessage(
        msg.id,
        msg.content,
        data,
        claimColorMap,
        allowedClaimIds
      ),
    }))

    // Build legend entries (one per claim, regardless of filters)
    const legend: LegendEntry[] = data.claims.map((claim) => ({
      claimId: claim.id,
      claimName: claim.claim_name,
      color: claimColorMap.get(claim.id) ?? '#888888',
    }))

    return { messageTexts, legend, claimColorMap }
  }, [data, narrativeState.activeLayers, claimFilter, confidenceThreshold])
}
