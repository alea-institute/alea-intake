import { useQuery } from '@tanstack/react-query'
import { fetchIntakes, type IntakeFilters } from '../api'

export function useIntakes(filters: IntakeFilters) {
  return useQuery({
    queryKey: ['intakes', filters],
    queryFn: () => fetchIntakes(filters),
    staleTime: 30_000,
  })
}
