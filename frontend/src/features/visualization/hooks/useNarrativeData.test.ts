/**
 * Tests for useNarrativeData transformer hook.
 *
 * TDD RED phase: all tests written before implementation.
 * Tests verify that VisualizationData is correctly transformed into
 * non-overlapping annotation segments using a sweep-line algorithm,
 * with stable color assignment and filter support.
 */

import { describe, it, expect, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useNarrativeData } from './useNarrativeData'
import { useVisualizationStore } from '@/features/visualization/store'
import { mockVisualizationData } from '@/test/fixtures/visualization'
import { CATEGORICAL_PALETTE } from '@/features/visualization/palette'
import type { VisualizationData } from '@/features/visualization/types'

describe('useNarrativeData', () => {
  afterEach(() => {
    useVisualizationStore.setState({
      jurisdictionFilter: null,
      claimFilter: [],
      confidenceThreshold: 0,
      narrativeState: { activeLayers: [], selectedSpanId: null },
    })
  })

  it('builds per-message text with annotation segments from source spans', () => {
    const { result } = renderHook(() => useNarrativeData(mockVisualizationData))

    // Should produce one entry per message
    expect(result.current.messageTexts.length).toBe(
      mockVisualizationData.messages.length
    )

    // Each message entry has expected shape
    const first = result.current.messageTexts[0]
    expect(first).toHaveProperty('messageId')
    expect(first).toHaveProperty('text')
    expect(first).toHaveProperty('senderType')
    expect(first).toHaveProperty('segments')
    expect(first.messageId).toBe(301)
    expect(first.senderType).toBe('consumer')
    expect(first.text).toBe(mockVisualizationData.messages[0].content)

    // Segments should cover the full text (no gaps in coverage)
    const totalLength = first.segments.reduce(
      (sum, seg) => sum + (seg.end - seg.start),
      0
    )
    expect(totalLength).toBe(first.text.length)
  })

  it('non-overlapping spans produce simple segments (one claimId per segment)', () => {
    // Create data with a single non-overlapping source span
    const simpleData: VisualizationData = {
      ...mockVisualizationData,
      facts: [
        {
          id: 101,
          assertion_text: 'Test fact',
          fact_type: 'assertion',
          confidence: 0.9,
          source_spans: [
            {
              message_id: 301,
              start_char: 0,
              end_char: 20,
              page_number: null,
              paragraph_index: null,
              timestamp_start_sec: null,
              timestamp_end_sec: null,
            },
          ],
        },
      ],
      mappings: [
        {
          id: 501,
          fact_id: 101,
          claim_id: 201,
          element_id: 401,
          confidence: 0.88,
          mapping_rationale: 'Test',
        },
      ],
    }

    const { result } = renderHook(() => useNarrativeData(simpleData))

    const msg = result.current.messageTexts.find((m) => m.messageId === 301)!
    // Should have at least 2 segments: the annotated part (0-20) and the plain part (20+)
    expect(msg.segments.length).toBeGreaterThanOrEqual(2)

    const annotatedSeg = msg.segments.find((s) => s.isAnnotated)
    expect(annotatedSeg).toBeDefined()
    expect(annotatedSeg!.claimIds).toEqual([201])
    expect(annotatedSeg!.colors.length).toBe(1)
  })

  it('overlapping spans at same character range produce a single segment with multiple claimIds (D-10 Pitfall 4)', () => {
    // Two facts both span characters 0-64 of message 301, mapped to different claims
    const overlappingData: VisualizationData = {
      ...mockVisualizationData,
      facts: [
        {
          id: 101,
          assertion_text: 'Fact A',
          fact_type: 'assertion',
          confidence: 0.9,
          source_spans: [
            {
              message_id: 301,
              start_char: 0,
              end_char: 64,
              page_number: null,
              paragraph_index: null,
              timestamp_start_sec: null,
              timestamp_end_sec: null,
            },
          ],
        },
        {
          id: 102,
          assertion_text: 'Fact B',
          fact_type: 'condition',
          confidence: 0.8,
          source_spans: [
            {
              message_id: 301,
              start_char: 0,
              end_char: 64,
              page_number: null,
              paragraph_index: null,
              timestamp_start_sec: null,
              timestamp_end_sec: null,
            },
          ],
        },
      ],
      mappings: [
        {
          id: 501,
          fact_id: 101,
          claim_id: 201,
          element_id: 401,
          confidence: 0.88,
          mapping_rationale: 'Test A',
        },
        {
          id: 502,
          fact_id: 102,
          claim_id: 202,
          element_id: 404,
          confidence: 0.82,
          mapping_rationale: 'Test B',
        },
      ],
    }

    const { result } = renderHook(() => useNarrativeData(overlappingData))

    const msg = result.current.messageTexts.find((m) => m.messageId === 301)!
    // The segment covering 0-64 should have BOTH claim IDs
    const overlapSeg = msg.segments.find(
      (s) => s.start === 0 && s.end === 64 && s.isAnnotated
    )
    expect(overlapSeg).toBeDefined()
    expect(overlapSeg!.claimIds.sort()).toEqual([201, 202])
    expect(overlapSeg!.colors.length).toBe(2)
  })

  it('partially overlapping spans produce correctly split segments at each boundary change point', () => {
    // Fact A spans 0-40, Fact B spans 20-64 => segments: [0-20 claim1], [20-40 claim1+claim2], [40-64 claim2], [64+ plain]
    const partialOverlapData: VisualizationData = {
      ...mockVisualizationData,
      facts: [
        {
          id: 101,
          assertion_text: 'Fact A',
          fact_type: 'assertion',
          confidence: 0.9,
          source_spans: [
            {
              message_id: 301,
              start_char: 0,
              end_char: 40,
              page_number: null,
              paragraph_index: null,
              timestamp_start_sec: null,
              timestamp_end_sec: null,
            },
          ],
        },
        {
          id: 102,
          assertion_text: 'Fact B',
          fact_type: 'condition',
          confidence: 0.8,
          source_spans: [
            {
              message_id: 301,
              start_char: 20,
              end_char: 64,
              page_number: null,
              paragraph_index: null,
              timestamp_start_sec: null,
              timestamp_end_sec: null,
            },
          ],
        },
      ],
      mappings: [
        {
          id: 501,
          fact_id: 101,
          claim_id: 201,
          element_id: 401,
          confidence: 0.88,
          mapping_rationale: 'Test A',
        },
        {
          id: 502,
          fact_id: 102,
          claim_id: 202,
          element_id: 404,
          confidence: 0.82,
          mapping_rationale: 'Test B',
        },
      ],
    }

    const { result } = renderHook(() => useNarrativeData(partialOverlapData))

    const msg = result.current.messageTexts.find((m) => m.messageId === 301)!

    // Find the segments by range
    const seg0_20 = msg.segments.find((s) => s.start === 0 && s.end === 20)
    const seg20_40 = msg.segments.find((s) => s.start === 20 && s.end === 40)
    const seg40_64 = msg.segments.find((s) => s.start === 40 && s.end === 64)

    // Segment 0-20: only claim 201
    expect(seg0_20).toBeDefined()
    expect(seg0_20!.claimIds).toEqual([201])

    // Segment 20-40: both claims
    expect(seg20_40).toBeDefined()
    expect(seg20_40!.claimIds.sort()).toEqual([201, 202])

    // Segment 40-64: only claim 202
    expect(seg40_64).toBeDefined()
    expect(seg40_64!.claimIds).toEqual([202])
  })

  it('gaps in text (no annotation) produce plain-text segments', () => {
    const { result } = renderHook(() => useNarrativeData(mockVisualizationData))

    // Message 302 is from professional, has no source_spans referencing it
    const msg302 = result.current.messageTexts.find((m) => m.messageId === 302)!
    // All segments should be plain text (no annotations)
    expect(msg302.segments.length).toBeGreaterThanOrEqual(1)
    expect(msg302.segments.every((s) => !s.isAnnotated)).toBe(true)
    expect(msg302.segments.every((s) => s.claimIds.length === 0)).toBe(true)
  })

  it('filters (active layers/claim filter) hide annotations from filtered-out claims', () => {
    // Set activeLayers to only include claim 201 (hide 202)
    useVisualizationStore.setState({
      narrativeState: { activeLayers: [201], selectedSpanId: null },
    })

    const { result } = renderHook(() => useNarrativeData(mockVisualizationData))

    // No segment should reference claim 202
    for (const msg of result.current.messageTexts) {
      for (const seg of msg.segments) {
        expect(seg.claimIds).not.toContain(202)
      }
    }

    // Reset layers, set claimFilter instead
    useVisualizationStore.setState({
      narrativeState: { activeLayers: [], selectedSpanId: null },
      claimFilter: [202],
    })

    const { result: filtered } = renderHook(() =>
      useNarrativeData(mockVisualizationData)
    )

    // Only claim 202 should appear in annotations
    for (const msg of filtered.current.messageTexts) {
      for (const seg of msg.segments) {
        if (seg.isAnnotated) {
          expect(seg.claimIds.every((id) => id === 202)).toBe(true)
        }
      }
    }
  })

  it('color assignment is stable per claim (same claim always gets same palette index)', () => {
    const { result: first } = renderHook(() =>
      useNarrativeData(mockVisualizationData)
    )
    const { result: second } = renderHook(() =>
      useNarrativeData(mockVisualizationData)
    )

    // Both renders should produce the same color map
    const map1 = first.current.claimColorMap
    const map2 = second.current.claimColorMap

    for (const [key, value] of map1) {
      expect(map2.get(key)).toBe(value)
    }

    // Color should be from the palette based on claim index
    const claim201Color = map1.get(201)
    const claim202Color = map1.get(202)
    expect(claim201Color).toBeDefined()
    expect(claim202Color).toBeDefined()
    // Different claims should get different colors
    expect(claim201Color).not.toBe(claim202Color)
    // Colors should come from CATEGORICAL_PALETTE
    expect(CATEGORICAL_PALETTE).toContain(claim201Color)
    expect(CATEGORICAL_PALETTE).toContain(claim202Color)
  })

  it('returns legend entries mapping each claim to its color', () => {
    const { result } = renderHook(() => useNarrativeData(mockVisualizationData))

    // Legend should have one entry per claim
    expect(result.current.legend.length).toBe(
      mockVisualizationData.claims.length
    )

    const entry0 = result.current.legend.find((l) => l.claimId === 201)
    expect(entry0).toBeDefined()
    expect(entry0!.claimName).toBe('Breach of Warranty of Habitability')
    expect(entry0!.color).toBe(result.current.claimColorMap.get(201))

    const entry1 = result.current.legend.find((l) => l.claimId === 202)
    expect(entry1).toBeDefined()
    expect(entry1!.claimName).toBe('Wrongful Eviction / Retaliatory Eviction')
    expect(entry1!.color).toBe(result.current.claimColorMap.get(202))
  })
})
