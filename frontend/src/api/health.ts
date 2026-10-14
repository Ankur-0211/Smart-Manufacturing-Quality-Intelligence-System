import { useQuery } from '@tanstack/react-query'

import { apiGet, type Schemas } from './client'

export type HealthData = Schemas['HealthData']

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => (await apiGet<HealthData>('/health')).data,
    refetchInterval: 15_000,
    retry: 1,
  })
}

/** True when any non-real intelligence may be producing outputs (roadmap 9.2). */
export function isMockIntelligence(health: HealthData | undefined): boolean {
  if (!health) return false
  if (health.intelligence_backend !== 'real') return true
  const info = health.intelligence as { is_mock?: boolean } | null | undefined
  return info?.is_mock === true
}
