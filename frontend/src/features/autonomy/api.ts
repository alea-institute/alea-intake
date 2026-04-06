import { apiFetch } from '@/features/auth/api'
import type { AutonomyConfig, AutonomyPresets, ApprovalRequest } from './types'

export async function fetchAutonomyConfig(): Promise<AutonomyConfig> {
  const res = await apiFetch('/api/v1/autonomy/admin/config')
  if (!res.ok) throw new Error('Failed to load autonomy config')
  return res.json()
}

export async function updateAutonomyConfig(config: AutonomyConfig): Promise<AutonomyConfig> {
  const res = await apiFetch('/api/v1/autonomy/admin/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error('Failed to update autonomy config')
  return res.json()
}

export async function fetchStages(): Promise<string[]> {
  const res = await apiFetch('/api/v1/autonomy/admin/stages')
  if (!res.ok) throw new Error('Failed to load stages')
  return res.json()
}

export async function fetchPresets(): Promise<AutonomyPresets> {
  const res = await apiFetch('/api/v1/autonomy/admin/presets')
  if (!res.ok) throw new Error('Failed to load presets')
  return res.json()
}

export async function fetchPendingApprovals(): Promise<ApprovalRequest[]> {
  const res = await apiFetch('/api/v1/autonomy/pending')
  if (!res.ok) throw new Error('Failed to load pending approvals')
  return res.json()
}

export async function approveStage(requestId: number): Promise<{ status: string }> {
  const res = await apiFetch(`/api/v1/autonomy/requests/${requestId}/approve`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Failed to approve stage')
  return res.json()
}

export async function rejectStage(requestId: number, guidanceText: string): Promise<{ status: string }> {
  const res = await apiFetch(`/api/v1/autonomy/requests/${requestId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ guidance_text: guidanceText }),
  })
  if (!res.ok) throw new Error('Failed to reject stage')
  return res.json()
}

export async function editStage(requestId: number, edits: Record<string, unknown>): Promise<{ status: string }> {
  const res = await apiFetch(`/api/v1/autonomy/requests/${requestId}/edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ edits }),
  })
  if (!res.ok) throw new Error('Failed to edit stage')
  return res.json()
}

export async function switchMode(
  runId: number,
  config: AutonomyConfig,
  reason: string,
): Promise<{ status: string }> {
  const res = await apiFetch(`/api/v1/autonomy/runs/${runId}/switch-mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config, reason }),
  })
  if (!res.ok) throw new Error('Failed to switch mode')
  return res.json()
}
