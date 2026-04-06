import { apiFetch } from '@/features/auth/api'
import type { SafetyAlert } from '@/features/chat/types'

export async function fetchSafetyAlerts(sessionId: string): Promise<SafetyAlert[]> {
  const res = await apiFetch(`/api/v1/intakes/${sessionId}/safety`)
  if (!res.ok) return [] // graceful degrade — safety should never break chat
  const body = await res.json()
  return body.items ?? []
}
