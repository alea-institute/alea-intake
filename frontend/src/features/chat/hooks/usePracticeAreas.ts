import { useQuery } from '@tanstack/react-query'
import { fetchPracticeAreas } from '../api'
import type { PracticeArea } from '../types'

/**
 * Fetch the public practice-area taxonomy. The list is small, public, and
 * stable for the lifetime of a page load — `staleTime: Infinity` is the
 * right move (no revalidation, no refetch on focus).
 *
 * Result is sorted by `display_name` to match the backend contract; we
 * sort client-side too as a safety net in case the deployment is older.
 */
export function usePracticeAreas() {
  return useQuery<PracticeArea[]>({
    queryKey: ['practice-areas'],
    queryFn: fetchPracticeAreas,
    staleTime: Infinity,
    gcTime: Infinity,
    select: (areas) =>
      [...areas].sort((a, b) => a.display_name.localeCompare(b.display_name)),
    retry: 0,
  })
}
