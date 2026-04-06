/**
 * Pure transformation hook: VisualizationData -> GraphNode[] + GraphLink[].
 *
 * Reads filter state from Zustand store and applies ghosting (D-04):
 * filtered-out nodes are marked ghosted rather than removed, preserving
 * spatial context in the graph layout.
 */

import { useMemo } from 'react'
import { useVisualizationStore } from '../store'
import type {
  VisualizationData,
  GraphNode,
  GraphLink,
} from '../types'

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
  ghostedNodeIds: Set<string>
}

/**
 * Transforms raw API VisualizationData into graph-ready nodes and links.
 *
 * Node ID scheme:
 *   - fact-{id}
 *   - claim-{id}
 *   - element-{id}
 *   - gap-{id}
 */
export function useGraphData(data: VisualizationData | undefined): GraphData {
  const jurisdictionFilter = useVisualizationStore((s) => s.jurisdictionFilter)
  const claimFilter = useVisualizationStore((s) => s.claimFilter)
  const confidenceThreshold = useVisualizationStore((s) => s.confidenceThreshold)
  const showGapsOnly = useVisualizationStore((s) => s.showGapsOnly)

  return useMemo(() => {
    if (!data) {
      return { nodes: [], links: [], ghostedNodeIds: new Set<string>() }
    }

    const nodes: GraphNode[] = []
    const links: GraphLink[] = []
    const ghostedNodeIds = new Set<string>()

    // Track claim IDs that pass jurisdiction filter (for cascading element ghost)
    const claimPassesJurisdiction = new Set<number>()
    // Track claim IDs that pass claim filter
    const claimPassesClaimFilter = new Set<number>()

    // -----------------------------------------------------------------------
    // Create claim nodes
    // -----------------------------------------------------------------------
    for (const claim of data.claims) {
      const id = `claim-${claim.id}`
      nodes.push({
        id,
        type: 'claim',
        label: claim.claim_name,
        confidence: claim.confidence,
        claimId: claim.id,
      })

      // Jurisdiction filter
      const passesJurisdiction =
        !jurisdictionFilter || claim.jurisdiction === jurisdictionFilter
      if (passesJurisdiction) claimPassesJurisdiction.add(claim.id)

      // Claim filter (empty = all pass)
      const passesClaimFilter =
        claimFilter.length === 0 || claimFilter.includes(claim.id)
      if (passesClaimFilter) claimPassesClaimFilter.add(claim.id)

      // Ghost if fails any filter
      if (
        !passesJurisdiction ||
        !passesClaimFilter ||
        claim.confidence < confidenceThreshold ||
        showGapsOnly
      ) {
        ghostedNodeIds.add(id)
      }
    }

    // -----------------------------------------------------------------------
    // Create element nodes + claim->element structural links
    // -----------------------------------------------------------------------
    for (const claim of data.claims) {
      for (const elem of claim.elements) {
        const elemId = `element-${elem.id}`
        nodes.push({
          id: elemId,
          type: 'element',
          label: elem.element_name,
          confidence: elem.satisfaction_confidence ?? 0,
          elementId: elem.id,
        })

        // Structural link: claim -> element
        links.push({
          source: `claim-${claim.id}`,
          target: elemId,
          confidence: elem.satisfaction_confidence ?? 0,
        })

        // Ghost if parent claim is ghosted or element confidence below threshold
        const parentGhosted = ghostedNodeIds.has(`claim-${claim.id}`)
        const elemConfidence = elem.satisfaction_confidence ?? 0
        if (
          parentGhosted ||
          elemConfidence < confidenceThreshold ||
          showGapsOnly
        ) {
          ghostedNodeIds.add(elemId)
        }
      }
    }

    // -----------------------------------------------------------------------
    // Create fact nodes
    // -----------------------------------------------------------------------
    for (const fact of data.facts) {
      const id = `fact-${fact.id}`
      const label =
        fact.assertion_text.length > 40
          ? fact.assertion_text.slice(0, 40) + '...'
          : fact.assertion_text
      nodes.push({
        id,
        type: 'fact',
        label,
        confidence: fact.confidence,
        factId: fact.id,
      })

      if (fact.confidence < confidenceThreshold || showGapsOnly) {
        ghostedNodeIds.add(id)
      }
    }

    // -----------------------------------------------------------------------
    // Create gap nodes
    // -----------------------------------------------------------------------
    for (const gap of data.gaps) {
      const id = `gap-${gap.id}`
      const label =
        gap.description.length > 40
          ? gap.description.slice(0, 40) + '...'
          : gap.description
      nodes.push({
        id,
        type: 'gap',
        label,
        confidence: gap.priority / 5, // Normalize priority to 0-1 range
        gapId: gap.id,
      })

      // Gaps are only ghosted if showGapsOnly is false and they fail confidence
      // When showGapsOnly is true, everything EXCEPT gaps gets ghosted
      if (!showGapsOnly && gap.priority / 5 < confidenceThreshold) {
        ghostedNodeIds.add(id)
      }
    }

    // -----------------------------------------------------------------------
    // Create mapping links: fact -> claim, fact -> element
    // -----------------------------------------------------------------------
    for (const mapping of data.mappings) {
      // fact -> claim link
      links.push({
        source: `fact-${mapping.fact_id}`,
        target: `claim-${mapping.claim_id}`,
        confidence: mapping.confidence,
      })

      // fact -> element link (if element_id exists)
      if (mapping.element_id != null) {
        links.push({
          source: `fact-${mapping.fact_id}`,
          target: `element-${mapping.element_id}`,
          confidence: mapping.confidence,
        })
      }
    }

    return { nodes, links, ghostedNodeIds }
  }, [data, jurisdictionFilter, claimFilter, confidenceThreshold, showGapsOnly])
}
