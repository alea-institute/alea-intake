import { apiFetch } from '@/features/auth/api'

export interface Organization {
  id: string
  name: string
  deployment_type: 'law_firm' | 'legal_aid' | 'court_self_help'
  accent_color?: string
  logo_url?: string
  preferred_language?: string
}

export async function fetchOrg(id: string): Promise<Organization> {
  const res = await apiFetch(`/api/v1/orgs/${id}`)
  if (!res.ok) throw new Error('Failed to load organization')
  return res.json()
}

export async function updateOrg(
  id: string,
  patch: Partial<Organization>
): Promise<Organization> {
  const res = await apiFetch(`/api/v1/orgs/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error('Failed to update organization')
  return res.json()
}
