import { create } from 'zustand'
import type { ConnectionStatus, ReviewStatusState } from './types'

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
