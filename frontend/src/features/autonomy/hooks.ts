import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchAutonomyConfig,
  updateAutonomyConfig,
  fetchStages,
  fetchPresets,
  fetchPendingApprovals,
} from './api'
import type { AutonomyConfig } from './types'

export function useAutonomyConfig() {
  return useQuery({
    queryKey: ['autonomy', 'config'],
    queryFn: fetchAutonomyConfig,
  })
}

export function useUpdateAutonomyConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (config: AutonomyConfig) => updateAutonomyConfig(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['autonomy', 'config'] })
    },
  })
}

export function useStages() {
  return useQuery({
    queryKey: ['autonomy', 'stages'],
    queryFn: fetchStages,
  })
}

export function usePresets() {
  return useQuery({
    queryKey: ['autonomy', 'presets'],
    queryFn: fetchPresets,
  })
}

export function usePendingApprovals() {
  return useQuery({
    queryKey: ['autonomy', 'pending'],
    queryFn: fetchPendingApprovals,
    refetchInterval: 5000,
  })
}
