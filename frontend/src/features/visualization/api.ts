/**
 * React Query hook for fetching visualization data from the API.
 *
 * Uses apiFetch for auth-aware requests with automatic token refresh.
 * Query key: ['visualization', intakeId]
 * Stale time: 30s (analysis data doesn't change frequently during viewing).
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiFetch } from '@/features/auth/api'
import type { VisualizationData } from './types'

async function fetchVisualizationData(intakeId: string): Promise<VisualizationData> {
  const res = await apiFetch(`/api/v1/analysis/${intakeId}/visualization`)
  if (!res.ok) {
    throw new Error(`Visualization fetch failed: ${res.status}`)
  }
  return res.json()
}

/**
 * Hook to fetch the complete visualization payload for an intake.
 *
 * Returns facts (with source_spans), claims (with elements), mappings,
 * gaps, and messages for rendering in graph, matrix, and narrative views.
 */
export function useVisualizationData(
  intakeId: string
): UseQueryResult<VisualizationData> {
  return useQuery({
    queryKey: ['visualization', intakeId],
    queryFn: () => fetchVisualizationData(intakeId),
    staleTime: 30_000,
    enabled: !!intakeId,
  })
}
