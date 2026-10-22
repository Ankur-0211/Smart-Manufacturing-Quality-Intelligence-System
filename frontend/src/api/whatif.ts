/** What-if and recommendation hooks (roadmap 9.3.2; R2-P5 endpoints, R2-P7 screens). */
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiPost, type Schemas } from './client'

export type WhatIfRequest = Schemas['WhatIfRequest']
export type WhatIfResult = Schemas['WhatIfResult']
export type RunDiff = Schemas['RunDiff']
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

/** POST /recommend for a finished run (Role 1's guarded search; rate limited). */
export function useRecommend() {
  return useMutation({
    mutationFn: async (body: RecommendRequest) =>
      normalize((await apiPost<Schemas['RecommendOut']>('/recommend', body)).data),
  })
}
