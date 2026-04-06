import { create } from 'zustand'
import type { ConnectionStatus } from './types'

interface WSState {
  status: ConnectionStatus
  ws: WebSocket | null
  reconnectAttempt: number
  setStatus: (s: ConnectionStatus) => void
  setWs: (ws: WebSocket | null) => void
  setReconnectAttempt: (n: number) => void
}

export const useWSStore = create<WSState>((set) => ({
  status: 'connecting',
  ws: null,
  reconnectAttempt: 0,
  setStatus: (status) => set({ status }),
  setWs: (ws) => set({ ws }),
  setReconnectAttempt: (n) => set({ reconnectAttempt: n }),
}))
