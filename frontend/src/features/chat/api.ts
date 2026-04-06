import { apiFetch } from '@/features/auth/api'
import type { Message } from './types'

export async function fetchMessages(sessionId: string): Promise<Message[]> {
  const res = await apiFetch(`/api/v1/intakes/${sessionId}/messages`)
  if (!res.ok) throw new Error('Failed to load messages')
  const body = await res.json()
  return body.items ?? []
}
