import { nominalRecipe, useConstraints } from '@/api/constraints'
import { useRunSetup, type Recipe } from '@/stores/runSetup'

/** The recipe shown: the operator's draft, or the registry nominal until something is edited. */
export function useEffectiveRecipe(): Recipe | null {
  const draft = useRunSetup((s) => s.recipe)
  const constraints = useConstraints().data
  if (draft) return draft
  return constraints ? nominalRecipe(constraints) : null
}
