/**
 * Okabe-Ito colorblind-safe categorical palette and confidence scale.
 *
 * Tested against protanopia/deuteranopia simulations per D-15.
 * Shapes + patterns supplement color in matrix cells and graph nodes.
 */

import type { NodeType } from './types'

/** 8-color Okabe-Ito categorical palette */
export const CATEGORICAL_PALETTE = [
  '#E69F00', // orange
  '#56B4E9', // sky blue
  '#009E73', // bluish green
  '#D55E00', // vermillion
  '#0072B2', // blue
  '#CC79A7', // reddish purple
  '#F0E442', // yellow
  '#000000', // black
] as const

/** Semantic colors by node type */
export const NODE_TYPE_COLORS: Record<NodeType, string> = {
  fact: '#E69F00',
  claim: '#56B4E9',
  element: '#009E73',
  gap: '#D55E00',
}

/** 5-level confidence scale for matrix cells and badges */
export interface ConfidenceLevel {
  label: string
  min: number
  color: string
}

export const CONFIDENCE_SCALE: ConfidenceLevel[] = [
  { label: 'strong', min: 0.8, color: '#009E73' },
  { label: 'good', min: 0.6, color: '#56B4E9' },
  { label: 'partial', min: 0.4, color: '#E69F00' },
  { label: 'weak', min: 0.2, color: '#D55E00' },
  { label: 'none', min: 0, color: '#cccccc' },
]

/**
 * Get the confidence level for a given score (0-1).
 * Returns the first matching level where score >= min.
 */
export function getConfidenceLevel(score: number): ConfidenceLevel {
  for (const level of CONFIDENCE_SCALE) {
    if (score >= level.min) return level
  }
  // Fallback (should never reach here with min=0)
  return CONFIDENCE_SCALE[CONFIDENCE_SCALE.length - 1]
}
