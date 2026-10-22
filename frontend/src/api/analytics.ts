/** Analytics hooks (roadmap 9.3.2, R2-P8). Every number is an aggregation over stored runs. */
import { useQuery } from '@tanstack/react-query'

import { apiGet, type Schemas } from './client'

export type AnalyticsSummary = Schemas['AnalyticsSummary']
export type GroupedAnalytics = Schemas['GroupedAnalytics']
export type MaterialAnalytics = Schemas['MaterialAnalytics']
export type ParameterAnalytics = Schemas['ParameterAnalytics']
export type SpcOut = Schemas['SpcOut']
// The base Outcome model is only emitted through its subclasses.
export type Outcome = Omit<Schemas['GroupOutcome'], 'key'>

/** Default exclusions (Plan §13.7): what-if children, MOCK-scored runs, runs without a final result. */
export interface AnalyticsFilters {
  includeWhatif: boolean
  includeMock: boolean
  includeUnfinished: boolean
  from: string // yyyy-mm-dd or ''
  to: string
}

export const DEFAULT_ANALYTICS_FILTERS: AnalyticsFilters = {
  includeWhatif: false,
  includeMock: false,
  includeUnfinished: false,
  from: '',
  to: '',
}

export function analyticsQuery(f: AnalyticsFilters, extra: Record<string, string | number> = {}): string {
  const q = new URLSearchParams()
  if (f.includeWhatif) q.set('include_whatif', 'true')
  if (f.includeMock) q.set('include_mock', 'true')
  if (f.includeUnfinished) q.set('include_unfinished', 'true')
  if (f.from) q.set('from', `${f.from}T00:00:00Z`)
  if (f.to) q.set('to', `${f.to}T23:59:59Z`)
  for (const [k, v] of Object.entries(extra)) q.set(k, String(v))
  const text = q.toString()
  return text ? `?${text}` : ''
}

function useAnalytics<T>(
  path: string,
  f: AnalyticsFilters,
  extra: Record<string, string | number>,
  enabled = true,
) {
  return useQuery({
    queryKey: ['analytics', path, f, extra],
    queryFn: async () => (await apiGet<T>(`/analytics/${path}${analyticsQuery(f, extra)}`)).data,
    enabled,
    placeholderData: (previous) => previous,
  })
}

export const useAnalyticsSummary = (f: AnalyticsFilters) => useAnalytics<AnalyticsSummary>('summary', f, {})

export const useByMachine = (f: AnalyticsFilters) => useAnalytics<GroupedAnalytics>('by-machine', f, {})

export const useByMaterial = (f: AnalyticsFilters, group: 'lot' | 'resin_grade') =>
  useAnalytics<MaterialAnalytics>('by-material', f, { group })

export const useByParameter = (f: AnalyticsFilters, parameter: string, buckets: number) =>
  useAnalytics<ParameterAnalytics>('by-parameter', f, { parameter, buckets }, Boolean(parameter))

export const useSpc = (f: AnalyticsFilters, machineId: string, parameter: string) =>
  useAnalytics<SpcOut>('spc', f, { machine_id: machineId, parameter }, Boolean(machineId && parameter))
