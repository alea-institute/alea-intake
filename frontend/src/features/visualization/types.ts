/**
 * Shared TypeScript types for the visualization feature.
 *
 * Covers the API response shape, D3 graph nodes/links, matrix cells,
 * narrative annotation ranges, and view type discriminants.
 */

// ---------------------------------------------------------------------------
// API response types (mirrors backend VisualizationResponse schema)
// ---------------------------------------------------------------------------

export interface VisualizationSourceSpan {
  message_id: number
  start_char: number
  end_char: number
  page_number: number | null
  paragraph_index: number | null
  timestamp_start_sec: number | null
  timestamp_end_sec: number | null
}

export interface VisualizationFact {
  id: number
  assertion_text: string
  fact_type: string
  confidence: number
  source_spans: VisualizationSourceSpan[]
}

export interface VisualizationElement {
  id: number
  element_name: string
  element_description: string | null
  is_satisfied: boolean
  satisfaction_confidence: number | null
}

export interface VisualizationClaim {
  id: number
  claim_name: string
  claim_type: string
  jurisdiction: string | null
  confidence: number
  rationale: string | null
  elements: VisualizationElement[]
}

export interface VisualizationMapping {
  id: number
  fact_id: number
  claim_id: number
  element_id: number | null
  confidence: number
  mapping_rationale: string | null
}

export interface VisualizationGap {
  id: number
  gap_type: string
  claim_id: number | null
  element_id: number | null
  description: string
  priority: number
  status: string
}

export interface VisualizationMessage {
  id: number
  content: string
  sender_type: string
}

export interface VisualizationData {
  run_id: number
  status: string
  facts: VisualizationFact[]
  claims: VisualizationClaim[]
  mappings: VisualizationMapping[]
  gaps: VisualizationGap[]
  messages: VisualizationMessage[]
}

// ---------------------------------------------------------------------------
// Graph view types (D3-force compatible)
// ---------------------------------------------------------------------------

export type NodeType = 'fact' | 'claim' | 'element' | 'gap'

export interface GraphNode {
  id: string
  type: NodeType
  label: string
  confidence: number
  /** Original DB ID for back-reference */
  factId?: number
  claimId?: number
  elementId?: number
  gapId?: number
  // d3-force simulation fields
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
  vx?: number
  vy?: number
  index?: number
}

export interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
  confidence: number
  index?: number
}

// ---------------------------------------------------------------------------
// Matrix view types
// ---------------------------------------------------------------------------

export interface MatrixCell {
  factId: number
  elementId: number
  claimId: number
  confidence: number
  rationale: string | null
}

// ---------------------------------------------------------------------------
// Narrative-anchored view types
// ---------------------------------------------------------------------------

export interface AnnotationRange {
  start: number
  end: number
  claimIds: number[]
  factIds: number[]
  colors: string[]
}

// ---------------------------------------------------------------------------
// View discriminant
// ---------------------------------------------------------------------------

export type ViewType = 'graph' | 'matrix' | 'narrative'
