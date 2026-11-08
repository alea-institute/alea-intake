import { apiFetch } from '@/features/auth/api'
import type { Message, PracticeArea } from './types'

export async function fetchMessages(sessionId: string): Promise<Message[]> {
  const res = await apiFetch(`/api/v1/intake/${sessionId}/messages?session_id=${encodeURIComponent(sessionId)}`)
  if (!res.ok) throw new Error('Failed to load messages')
  const body = await res.json()
  return (Array.isArray(body) ? body : []).map((m: {id:number;content:string;sender_type:Message['sender'];modality:Message['modality'];created_at:string}) => ({ id: String(m.id), sessionId, content: m.content, sender: m.sender_type, modality: m.modality, timestamp: m.created_at, status: 'done' as const }))
}

/**
 * Public taxonomy — no auth required, but we still go through apiFetch so
 * tenant headers etc. ride along consistently.
 */
export async function fetchPracticeAreas(): Promise<PracticeArea[]> {
  const res = await fetch('/api/practice-areas', { credentials: 'include' })
  if (!res.ok) throw new Error('Failed to load practice areas')
  const body = (await res.json()) as { practice_areas?: PracticeArea[] }
  return body.practice_areas ?? []
}

export interface CreateIntakeResponse {
  id?: number
  session_id?: number
  practice_area_id?: string | null
}

/**
 * POST /api/v1/intake/ — kicks off a fresh intake. When `practiceAreaId` is
 * non-null, the resulting session is bound to that practice area; the LLM
 * conversation will use the practice's system prompt + welcome message.
 */
export async function createIntake(
  practiceAreaId: string | null = null,
): Promise<CreateIntakeResponse> {
  const init: RequestInit = { method: 'POST' }
  if (practiceAreaId !== null) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify({ practice_area_id: practiceAreaId })
  }
  const res = await apiFetch('/api/v1/intake/', init)
  if (!res.ok) throw new Error(`Intake creation failed: ${res.status}`)
  return (await res.json()) as CreateIntakeResponse
}
