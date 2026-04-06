/**
 * Tests for useMatrixData transformer hook.
 *
 * TDD RED phase: all tests written before implementation.
 * Tests verify that VisualizationData is correctly transformed into
 * a matrix structure with rows (facts), column groups (claims),
 * cell lookup, filtering, sorting, and gap detection.
 */

import { describe, it, expect, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useMatrixData } from './useMatrixData'
import { useVisualizationStore } from '@/features/visualization/store'
import { mockVisualizationData } from '@/test/fixtures/visualization'

describe('useMatrixData', () => {
  afterEach(() => {
    // Reset store to defaults
    useVisualizationStore.setState({
      jurisdictionFilter: null,
      claimFilter: [],
      confidenceThreshold: 0,
      showGapsOnly: false,
      matrixState: { sortBy: 'confidence', selectedCell: null },
    })
  })

  it('transforms VisualizationData into rows (facts) and columns (elements grouped by claim)', () => {
    const { result } = renderHook(() => useMatrixData(mockVisualizationData))

    // Rows correspond to facts
    expect(result.current.rows.length).toBe(mockVisualizationData.facts.length)
    expect(result.current.rows[0]).toHaveProperty('factId')
    expect(result.current.rows[0]).toHaveProperty('label')
    expect(result.current.rows[0]).toHaveProperty('confidence')

    // Column groups correspond to claims
    expect(result.current.columnGroups.length).toBe(mockVisualizationData.claims.length)

    // totalColumns = sum of all element columns
    const totalElements = mockVisualizationData.claims.reduce(
      (sum, c) => sum + c.elements.length,
      0
    )
    expect(result.current.totalColumns).toBe(totalElements)
  })

  it('column groups correspond to claims, each group contains that claims elements', () => {
    const { result } = renderHook(() => useMatrixData(mockVisualizationData))

    // First claim: "Breach of Warranty of Habitability" with 3 elements
    const group0 = result.current.columnGroups[0]
    expect(group0.claimId).toBe(201)
    expect(group0.claimName).toBe('Breach of Warranty of Habitability')
    expect(group0.columns.length).toBe(3)

    // Second claim: "Wrongful Eviction / Retaliatory Eviction" with 1 element
    const group1 = result.current.columnGroups[1]
    expect(group1.claimId).toBe(202)
    expect(group1.columns.length).toBe(1)

    // Each column has element info
    expect(group0.columns[0]).toHaveProperty('elementId')
    expect(group0.columns[0]).toHaveProperty('elementName')
    expect(group0.columns[0]).toHaveProperty('isGap')
    expect(group0.columns[0]).toHaveProperty('isSatisfied')
  })

  it('cell lookup by (factId, elementId) returns MatrixCell with confidence and rationale', () => {
    const { result } = renderHook(() => useMatrixData(mockVisualizationData))

    // Mapping 501: fact 101 -> element 401, confidence 0.88
    const cell = result.current.getCellData(101, 401)
    expect(cell).not.toBeNull()
    expect(cell!.factId).toBe(101)
    expect(cell!.elementId).toBe(401)
    expect(cell!.confidence).toBe(0.88)
    expect(cell!.rationale).toBe(
      'Broken heater constitutes defective condition affecting habitability'
    )
  })

  it('missing mappings return null (gap cell)', () => {
    const { result } = renderHook(() => useMatrixData(mockVisualizationData))

    // Fact 102 (mold) has no mapping to element 403 (Reasonable Time to Repair)
    const cell = result.current.getCellData(102, 403)
    expect(cell).toBeNull()

    // Fact 103 has no mapping to element 401
    const cell2 = result.current.getCellData(103, 401)
    expect(cell2).toBeNull()
  })

  it('filters reduce visible rows/columns (jurisdiction, claim, confidence)', () => {
    // Filter by claim: only show claim 201
    useVisualizationStore.setState({ claimFilter: [201] })

    const { result: withClaimFilter } = renderHook(() =>
      useMatrixData(mockVisualizationData)
    )
    // Only claim 201's elements should appear
    expect(withClaimFilter.current.columnGroups.length).toBe(1)
    expect(withClaimFilter.current.columnGroups[0].claimId).toBe(201)

    // Reset and filter by confidence threshold
    useVisualizationStore.setState({
      claimFilter: [],
      confidenceThreshold: 0.90,
    })

    const { result: withConfFilter } = renderHook(() =>
      useMatrixData(mockVisualizationData)
    )
    // Only fact 101 (0.92) passes 0.90 threshold; facts 102 (0.88) and 103 (0.85) are excluded
    expect(withConfFilter.current.rows.length).toBe(1)
    expect(withConfFilter.current.rows[0].factId).toBe(101)
  })

  it('sort by confidence orders facts by their max mapping confidence descending', () => {
    useVisualizationStore.setState({
      matrixState: { sortBy: 'confidence', selectedCell: null },
    })

    const { result } = renderHook(() => useMatrixData(mockVisualizationData))

    // Fact 101 has mappings at 0.88, 0.75, 0.65 -> max 0.88
    // Fact 102 has mapping at 0.82 -> max 0.82
    // Fact 103 has mapping at 0.78 -> max 0.78
    // Order: 101 (0.88), 102 (0.82), 103 (0.78)
    expect(result.current.rows[0].factId).toBe(101)
    expect(result.current.rows[1].factId).toBe(102)
    expect(result.current.rows[2].factId).toBe(103)
  })

  it('sort by source_order preserves original fact order', () => {
    useVisualizationStore.setState({
      matrixState: { sortBy: 'source_order', selectedCell: null },
    })

    const { result } = renderHook(() => useMatrixData(mockVisualizationData))

    // Source order: fact 101, 102, 103 (as they appear in the data)
    expect(result.current.rows[0].factId).toBe(101)
    expect(result.current.rows[1].factId).toBe(102)
    expect(result.current.rows[2].factId).toBe(103)
  })

  it('gap columns (elements with no satisfying mappings) are flagged with isGap=true', () => {
    const { result } = renderHook(() => useMatrixData(mockVisualizationData))

    // Element 402 "Notice to Landlord" has no mappings in the test data (gap 601 confirms this)
    const group0 = result.current.columnGroups[0]
    const noticeColumn = group0.columns.find((c) => c.elementId === 402)
    expect(noticeColumn).toBeDefined()
    expect(noticeColumn!.isGap).toBe(true)

    // Element 401 "Defective Condition" HAS mappings (501, 502) -> not a gap
    const defectiveColumn = group0.columns.find((c) => c.elementId === 401)
    expect(defectiveColumn).toBeDefined()
    expect(defectiveColumn!.isGap).toBe(false)
  })
})
