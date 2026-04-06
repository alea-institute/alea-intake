/**
 * useMatrixData -- transforms VisualizationData into matrix grid structure.
 *
 * Rows = facts, columns = elements grouped by claim.
 * Cell lookup via Map<`${factId}-${elementId}`, MatrixCell>.
 * Reads filter/sort state from Zustand store.
 *
 * Per D-06: facts as rows, elements grouped by claim as columns.
 * Per D-07: cell confidence + rationale, gaps as empty cells.
 * Per D-08: data layer for virtual scrolling.
 */

import { useMemo } from 'react'
import { useVisualizationStore } from '../store'
import type { MatrixCell, VisualizationData } from '../types'

// ---------------------------------------------------------------------------
// Output interfaces
// ---------------------------------------------------------------------------

export interface MatrixRow {
  factId: number
  label: string
  confidence: number
}

export interface ElementColumn {
  elementId: number
  elementName: string
  isGap: boolean
  isSatisfied: boolean
}

export interface ClaimGroup {
  claimId: number
  claimName: string
  jurisdiction: string | null
  collapsed: boolean
  columns: ElementColumn[]
}

export interface MatrixData {
  rows: MatrixRow[]
  columnGroups: ClaimGroup[]
  getCellData: (factId: number, elementId: number) => MatrixCell | null
  totalColumns: number
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useMatrixData(data: VisualizationData | undefined): MatrixData {
  const jurisdictionFilter = useVisualizationStore((s) => s.jurisdictionFilter)
  const claimFilter = useVisualizationStore((s) => s.claimFilter)
  const confidenceThreshold = useVisualizationStore((s) => s.confidenceThreshold)
  const sortBy = useVisualizationStore((s) => s.matrixState.sortBy)

  return useMemo(() => {
    const empty: MatrixData = {
      rows: [],
      columnGroups: [],
      getCellData: () => null,
      totalColumns: 0,
    }

    if (!data) return empty

    // -------------------------------------------------------------------
    // 1. Build cell lookup Map from mappings
    // -------------------------------------------------------------------
    const cellMap = new Map<string, MatrixCell>()
    for (const m of data.mappings) {
      if (m.element_id == null) continue
      const key = `${m.fact_id}-${m.element_id}`
      // If multiple mappings for same fact-element, keep the highest confidence
      const existing = cellMap.get(key)
      if (!existing || m.confidence > existing.confidence) {
        cellMap.set(key, {
          factId: m.fact_id,
          elementId: m.element_id,
          claimId: m.claim_id,
          confidence: m.confidence,
          rationale: m.mapping_rationale,
        })
      }
    }

    // Set of element IDs that have at least one mapping
    const mappedElementIds = new Set<number>()
    for (const m of data.mappings) {
      if (m.element_id != null) {
        mappedElementIds.add(m.element_id)
      }
    }

    // -------------------------------------------------------------------
    // 2. Build column groups from claims and elements (apply filters)
    // -------------------------------------------------------------------
    const columnGroups: ClaimGroup[] = []

    for (const claim of data.claims) {
      // Jurisdiction filter: skip claims that don't match
      if (jurisdictionFilter && claim.jurisdiction !== jurisdictionFilter) {
        continue
      }

      // Claim filter: skip unselected claims (empty = all pass)
      if (claimFilter.length > 0 && !claimFilter.includes(claim.id)) {
        continue
      }

      const columns: ElementColumn[] = claim.elements.map((elem) => ({
        elementId: elem.id,
        elementName: elem.element_name,
        isGap: !mappedElementIds.has(elem.id),
        isSatisfied: elem.is_satisfied,
      }))

      columnGroups.push({
        claimId: claim.id,
        claimName: claim.claim_name,
        jurisdiction: claim.jurisdiction,
        collapsed: false,
        columns,
      })
    }

    // -------------------------------------------------------------------
    // 3. Build rows from facts (apply confidence threshold)
    // -------------------------------------------------------------------

    // First compute max mapping confidence per fact for sorting
    const maxConfidenceByFact = new Map<number, number>()
    for (const m of data.mappings) {
      const existing = maxConfidenceByFact.get(m.fact_id) ?? 0
      if (m.confidence > existing) {
        maxConfidenceByFact.set(m.fact_id, m.confidence)
      }
    }

    let rows: MatrixRow[] = data.facts
      .filter((f) => f.confidence >= confidenceThreshold)
      .map((f) => ({
        factId: f.id,
        label: f.assertion_text,
        confidence: f.confidence,
      }))

    // -------------------------------------------------------------------
    // 4. Apply sort
    // -------------------------------------------------------------------
    if (sortBy === 'confidence') {
      rows = rows.slice().sort((a, b) => {
        const aMax = maxConfidenceByFact.get(a.factId) ?? 0
        const bMax = maxConfidenceByFact.get(b.factId) ?? 0
        return bMax - aMax
      })
    }
    // 'source_order' and 'alphabetical' keep original order or sort alphabetically
    if (sortBy === 'alphabetical') {
      rows = rows.slice().sort((a, b) => a.label.localeCompare(b.label))
    }

    // -------------------------------------------------------------------
    // 5. Calculate totalColumns
    // -------------------------------------------------------------------
    const totalColumns = columnGroups.reduce(
      (sum, g) => sum + g.columns.length,
      0
    )

    // -------------------------------------------------------------------
    // 6. getCellData lookup
    // -------------------------------------------------------------------
    const getCellData = (factId: number, elementId: number): MatrixCell | null => {
      return cellMap.get(`${factId}-${elementId}`) ?? null
    }

    return { rows, columnGroups, getCellData, totalColumns }
  }, [data, jurisdictionFilter, claimFilter, confidenceThreshold, sortBy])
}
