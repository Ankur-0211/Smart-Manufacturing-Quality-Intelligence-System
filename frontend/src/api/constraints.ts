/**
 * Constraint registry (GET /constraints, roadmap 8.4). Rule B6: every slider bound, step, unit and
 * default in the UI comes from here; frontend/src holds no limit literals.
 */
import { useQuery } from '@tanstack/react-query'

import { apiGet, type Schemas } from './client'

export type Constraints = Schemas['ConstraintsOut']
export type ParameterSpec = Schemas['ParameterSpecOut']

export function useConstraints() {
  return useQuery({
    queryKey: ['constraints'],
    queryFn: async () => (await apiGet<Constraints>('/constraints')).data,
    // The registry only changes with a deploy; the server also answers ETag revalidation.
    staleTime: 5 * 60_000,
  })
}

/** Operator setpoints (ProcessRecipe fields), in registry order. */
export function setpoints(constraints: Constraints): ParameterSpec[] {
  return constraints.parameters.filter((p) => p.kind === 'setpoint')
}

/** Default recipe for new runs: every setpoint at its registry nominal. */
export function nominalRecipe(constraints: Constraints): Record<string, number> {
  const recipe: Record<string, number> = {}
  for (const p of setpoints(constraints)) {
    if (typeof p.nominal === 'number') recipe[p.name] = p.nominal
  }
  return recipe
}

/** Client-side box check mirroring the server's tier 1, driven only by the registry. */
export function outOfRange(spec: ParameterSpec, value: number): boolean {
  if (spec.min != null && value < spec.min) return true
  if (spec.max != null && value > spec.max) return true
  return false
}
