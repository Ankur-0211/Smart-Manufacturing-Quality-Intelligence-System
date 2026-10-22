/** What-if and recommendation hooks (roadmap 9.3.2; R2-P5 endpoints, R2-P7 screens). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useDebounced } from '@/lib/useDebounced'

import { apiPost, type Schemas } from './client'

export type WhatIfRequest = Schemas['WhatIfRequest']
export type WhatIfResult = Schemas['WhatIfResult']
export type RunDiff = Schemas['RunDiff']
export type SensitivityRequest = Schemas['SensitivityRequest']
export type SensitivityResult = Schemas['SensitivityResult']
export type RecommendRequest = Schemas['RecommendRequest']
type RawCandidate = Schemas['RecommendationCandidate']
type StabilityReport = Schemas['StabilityReport']

/** A candidate with its defaulted list fields filled (the contract gives them server defaults). */
export type RecommendationCandidate = Required<
  Pick<RawCandidate, 'changes' | 'flags' | 'guard_checks' | 'rationale' | 'stage_health_after'>
> &
  Omit<
    RawCandidate,
    'changes' | 'flags' | 'guard_checks' | 'rationale' | 'stage_health_after' | 'stability'
  > & {
    stability: Required<StabilityReport>
  }

export type RecommendOut = Omit<Schemas['RecommendOut'], 'candidates' | 'rejected_counts'> & {
  candidates: RecommendationCandidate[]
  rejected_counts: Record<string, number>
}

function normalize(raw: Schemas['RecommendOut']): RecommendOut {
  return {
    ...raw,
    rejected_counts: raw.rejected_counts ?? {},
    candidates: (raw.candidates ?? []).map((c) => ({
      ...c,
      changes: c.changes ?? [],
      flags: c.flags ?? [],
      guard_checks: c.guard_checks ?? [],
      rationale: c.rationale ?? [],
      stage_health_after: c.stage_health_after ?? [],
      stability: {
        trials: c.stability?.trials ?? 0,
        flips: c.stability?.flips ?? 0,
        stable: c.stability?.stable ?? false,
      },
    })),
  }
}

/** POST /whatif. `persist: true` saves a child run (scenario); `false` only evaluates. */
export function useWhatIf() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (body: WhatIfRequest) => (await apiPost<WhatIfResult>('/whatif', body)).data,
    onSuccess: (result) => {
      if (result.run_id) void client.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}

/** Live mode debounce (roadmap R2-P7 task 1). */
export const LIVE_DEBOUNCE_MS = 150

/**
 * What-if live mode: `persist=false` evaluations, one request per 150 ms pause in editing. A newer
 * draft aborts the in-flight request (AbortController via the query signal), so the latest result
 * is the one shown. The previous result stays visible while the next one loads.
 */
export function useLiveWhatIf(baseRunId: string | null, overrides: Record<string, number>, enabled: boolean) {
  const settled = useDebounced(overrides, LIVE_DEBOUNCE_MS)
  return useQuery({
    queryKey: ['whatif-live', baseRunId, settled],
    queryFn: async ({ signal }) =>
      (
        await apiPost<WhatIfResult>(
          '/whatif',
          { base_run_id: baseRunId!, overrides: settled, persist: false } satisfies WhatIfRequest,
          signal,
        )
      ).data,
    enabled: enabled && Boolean(baseRunId) && Object.keys(settled).length > 0,
    placeholderData: keepPreviousData,
    staleTime: Infinity, // the same draft on the same base gives the same result
    retry: false,
  })
}

/** POST /whatif/compare: the §7.16 diff between two finished runs (A → B). */
export function useCompare(runIdA: string | null, runIdB: string | null) {
  return useQuery({
    queryKey: ['whatif-compare', runIdA, runIdB],
    queryFn: async ({ signal }) =>
      (await apiPost<RunDiff>('/whatif/compare', { run_id_a: runIdA, run_id_b: runIdB }, signal)).data,
    enabled: Boolean(runIdA && runIdB && runIdA !== runIdB),
    staleTime: Infinity, // finished runs are immutable
    retry: false,
  })
}

/** POST /whatif/sensitivity: one 1-D sweep around a finished run (rate limited on the server). */
export async function fetchSensitivity(body: SensitivityRequest): Promise<SensitivityResult> {
  return (await apiPost<SensitivityResult>('/whatif/sensitivity', body)).data
}

/** POST /recommend for a finished run (Role 1's guarded search; rate limited). */
export function useRecommend() {
  return useMutation({
    mutationFn: async (body: RecommendRequest) =>
      normalize((await apiPost<Schemas['RecommendOut']>('/recommend', body)).data),
  })
}
