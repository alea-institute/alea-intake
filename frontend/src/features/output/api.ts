import { apiFetch } from '@/features/auth/api'

export interface OutputProfileData {
  id?: string
  profile_key: string
  content: string
  rendered_at: string
}

export async function fetchOutput(
  intakeId: string
): Promise<{ profiles: OutputProfileData[] }> {
  const res = await apiFetch(`/api/v1/output/intake/${intakeId}`)
  if (!res.ok) throw new Error('Failed to load output')
  const docs: {id:number;profile_type:string;created_at:string}[] = await res.json()
  const profiles = await Promise.all(docs.map(async doc => {
    const detail = await apiFetch(`/api/v1/output/${doc.id}`)
    if (!detail.ok) throw new Error('Failed to load output')
    const body = await detail.json()
    return { profile_key: doc.profile_type, content: body.markdown_content, rendered_at: doc.created_at, id: String(doc.id) }
  }))
  return { profiles }
}

export async function exportOutput(
  outputId: string,
  format: 'pdf' | 'docx' | 'json'
): Promise<void> {
  const res = await apiFetch(
    `/api/v1/output/${outputId}/export/${format}`
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
