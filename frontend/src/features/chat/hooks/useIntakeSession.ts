import { useQuery } from '@tanstack/react-query'
import { fetchMessages } from '../api'
import type { Message } from '../types'

export function useIntakeMessages(sessionId: string | null) {
  return useQuery<Message[]>({
    queryKey: ['intake', sessionId, 'messages'],
    queryFn: () => fetchMessages(sessionId!),
    enabled: !!sessionId,
    staleTime: 60_000,
  })
}
