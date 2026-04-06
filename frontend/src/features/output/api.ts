import { apiFetch } from '@/features/auth/api'

export interface OutputProfileData {
  profile_key: string
  content: string
  rendered_at: string
}

export async function fetchOutput(
  intakeId: string
): Promise<{ profiles: OutputProfileData[] }> {
  const res = await apiFetch(`/api/v1/outputs/${intakeId}`)
  if (!res.ok) throw new Error('Failed to load output')
  return res.json()
}

export async function exportOutput(
  outputId: string,
  format: 'pdf' | 'docx' | 'json'
): Promise<void> {
  const res = await apiFetch(
    `/api/v1/outputs/${outputId}/export?format=${format}`
  )
  if (!res.ok) throw new Error('Export failed')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const ext = format === 'json' ? 'json' : format === 'docx' ? 'docx' : 'pdf'
  a.download = `intake-${outputId}.${ext}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
