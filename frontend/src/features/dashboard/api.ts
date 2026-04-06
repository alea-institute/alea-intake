import { apiFetch } from '@/features/auth/api'

export interface IntakeSummary {
  id: string
  matterId: string
  consumerName: string
  areaOfLaw?: string
  jurisdiction?: string
  status: 'new' | 'in_progress' | 'complete' | 'referred' | 'abandoned'
  lastActivity: string
  completeness: number
  assignedProfessional?: string
}

export interface IntakeFilters {
  status?: string[]
  area?: string[]
  jurisdiction?: string[]
  from?: string
  to?: string
  assigned?: string
  q?: string
}

export async function fetchIntakes(
  filters: IntakeFilters,
  limit = 50,
  offset = 0
): Promise<{ items: IntakeSummary[]; total: number }> {
  const params = new URLSearchParams()
  if (filters.status?.length) params.set('status', filters.status.join(','))
  if (filters.area?.length) params.set('area', filters.area.join(','))
  if (filters.jurisdiction?.length) params.set('jurisdiction', filters.jurisdiction.join(','))
  if (filters.from) params.set('from', filters.from)
  if (filters.to) params.set('to', filters.to)
  if (filters.assigned) params.set('assigned', filters.assigned)
  if (filters.q) params.set('q', filters.q)
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const res = await apiFetch(`/api/v1/intakes?${params.toString()}`)
  if (!res.ok) throw new Error('Failed to load intakes')
  return res.json()
}
