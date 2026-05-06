import { create } from 'zustand'
import type { ConnectionStatus, ReviewStatusState } from './types'

interface PracticeAreaState {
  practiceAreaId: string | null
  setPracticeArea: (id: string | null) => void
  reset: () => void
}

/**
 * Selected practice area for a forthcoming intake. Null means "Generic"
 * (no practice binding). State is intentionally page-lifetime only — no
 * persistence — so refreshing the page returns to the generic default.
 *
 * Kept separate from the WebSocket store because the lifecycle is different:
 * this is a pre-conversation choice, not a connection concern.
 */
export const usePracticeAreaStore = create<PracticeAreaState>((set) => ({
  practiceAreaId: null,
  setPracticeArea: (practiceAreaId) => set({ practiceAreaId }),
  reset: () => set({ practiceAreaId: null }),
}))

interface WSState {
  status: ConnectionStatus
  ws: WebSocket | null
  reconnectAttempt: number
  reviewStatus: ReviewStatusState
  setStatus: (s: ConnectionStatus) => void
  setWs: (ws: WebSocket | null) => void
  setReconnectAttempt: (n: number) => void
  setReviewStatus: (rs: ReviewStatusState) => void
}

export const useWSStore = create<WSState>((set) => ({
  status: 'connecting',
  ws: null,
  reconnectAttempt: 0,
  reviewStatus: { status: 'idle', label: '' },
  setStatus: (status) => set({ status }),
  setWs: (ws) => set({ ws }),
  setReconnectAttempt: (n) => set({ reconnectAttempt: n }),
  setReviewStatus: (reviewStatus) => set({ reviewStatus }),
}))
