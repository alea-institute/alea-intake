import { useQuery } from '@tanstack/react-query'
import { fetchSafetyAlerts } from '../api'
import type { SafetyAlert } from '@/features/chat/types'

export function useSafetyAlerts(sessionId: string | null) {
  return useQuery<SafetyAlert[]>({
    queryKey: ['intake', sessionId, 'safety'],
    queryFn: () => fetchSafetyAlerts(sessionId!),
    enabled: !!sessionId,
    staleTime: 30_000,
  })
}
