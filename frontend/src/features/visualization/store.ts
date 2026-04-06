/**
 * Zustand store for visualization shared filters and per-view state.
 *
 * - Shared filters (jurisdiction, claim, confidence threshold) apply across all views (D-13)
 * - Per-view state (graph selection, matrix sort, narrative layers) persists across tab switches (D-12)
 * - activeView reflected in ?view= URL param via window.history.replaceState
 */

import { create } from 'zustand'
import type { ViewType } from './types'

// ---------------------------------------------------------------------------
// Per-view state slices
// ---------------------------------------------------------------------------

export interface GraphState {
  selectedNodeId: string | null
  zoom: number
  panX: number
  panY: number
}

export interface MatrixState {
  sortBy: 'confidence' | 'source_order' | 'alphabetical'
  selectedCell: { factId: number; elementId: number } | null
}

export interface NarrativeState {
  activeLayers: number[] // claim IDs whose annotations are visible
  selectedSpanId: string | null
}

// ---------------------------------------------------------------------------
// Full store interface
// ---------------------------------------------------------------------------

export interface VisualizationState {
  // Shared filters
  activeView: ViewType
  jurisdictionFilter: string | null
  claimFilter: number[]
  confidenceThreshold: number
  showGapsOnly: boolean

  // Per-view state
  graphState: GraphState
  matrixState: MatrixState
  narrativeState: NarrativeState

  // Actions -- shared
  setActiveView: (view: ViewType) => void
  setJurisdiction: (jurisdiction: string | null) => void
  setClaims: (claimIds: number[]) => void
  setConfidenceThreshold: (threshold: number) => void
  toggleGapsOnly: () => void

  // Actions -- per-view
  setGraphState: (patch: Partial<GraphState>) => void
  setMatrixState: (patch: Partial<MatrixState>) => void
  setNarrativeState: (patch: Partial<NarrativeState>) => void
}

// ---------------------------------------------------------------------------
// Default state values
// ---------------------------------------------------------------------------

const defaultGraphState: GraphState = {
  selectedNodeId: null,
  zoom: 1,
  panX: 0,
  panY: 0,
}

const defaultMatrixState: MatrixState = {
  sortBy: 'confidence',
  selectedCell: null,
}

const defaultNarrativeState: NarrativeState = {
  activeLayers: [],
  selectedSpanId: null,
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

function syncViewToUrl(view: ViewType): void {
  if (typeof window === 'undefined') return
  const url = new URL(window.location.href)
  url.searchParams.set('view', view)
  window.history.replaceState(null, '', url.toString())
}

export const useVisualizationStore = create<VisualizationState>((set) => ({
  // Shared filters -- defaults
  activeView: 'graph',
  jurisdictionFilter: null,
  claimFilter: [],
  confidenceThreshold: 0,
  showGapsOnly: false,

  // Per-view state -- defaults
  graphState: { ...defaultGraphState },
  matrixState: { ...defaultMatrixState },
  narrativeState: { ...defaultNarrativeState },

  // Shared actions
  setActiveView: (view) => {
    syncViewToUrl(view)
    set({ activeView: view })
  },

  setJurisdiction: (jurisdiction) => set({ jurisdictionFilter: jurisdiction }),

  setClaims: (claimIds) => set({ claimFilter: claimIds }),

  setConfidenceThreshold: (threshold) => set({ confidenceThreshold: threshold }),

  toggleGapsOnly: () => set((s) => ({ showGapsOnly: !s.showGapsOnly })),

  // Per-view actions -- merge patch into existing state
  setGraphState: (patch) =>
    set((s) => ({ graphState: { ...s.graphState, ...patch } })),

  setMatrixState: (patch) =>
    set((s) => ({ matrixState: { ...s.matrixState, ...patch } })),

  setNarrativeState: (patch) =>
    set((s) => ({ narrativeState: { ...s.narrativeState, ...patch } })),
}))
