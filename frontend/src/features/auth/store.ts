import { create } from 'zustand'

export interface User {
  id: string
  email: string
  role: 'admin' | 'professional' | 'consumer'
  org_id: string
  full_name?: string
  theme?: 'legal-professional' | 'modern-conversational' | 'courthouse-classic'
  preferred_language?: string
}

interface AuthState {
  accessToken: string | null
  user: User | null
  setAuth: (accessToken: string, user: User) => void
  clear: () => void
}

/**
 * Auth store holds the access token in RAM only (Zustand state, no persist middleware).
 * Refresh token lives in an httpOnly cookie set by the backend.
 * Rationale: prevents XSS exfiltration of bearer tokens per D-22.
 */
export const useAuth = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setAuth: (accessToken, user) => set({ accessToken, user }),
  clear: () => set({ accessToken: null, user: null }),
}))
