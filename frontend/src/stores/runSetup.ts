/**
 * Draft of the next run: context codes and recipe (roadmap R2-P6 task 5, `draftRecipe` + `context`).
 * In-memory only, so the draft survives navigation between screens but never outlives the tab.
 * `recipe` stays null until the operator edits a value; until then the registry nominal applies.
 */
import { create } from 'zustand'

export type Recipe = Record<string, number>

interface RunSetupState {
  machineId: string | null
  productId: string | null
  lotId: string | null
  recipe: Recipe | null
  setContext: (part: Partial<Pick<RunSetupState, 'machineId' | 'productId' | 'lotId'>>) => void
  /** `base` is the recipe currently shown (the nominal one while nothing was edited). */
  setParam: (name: string, value: number, base: Recipe) => void
  setRecipe: (recipe: Recipe | null) => void
}

export const useRunSetup = create<RunSetupState>((set) => ({
  machineId: null,
  productId: null,
  lotId: null,
  recipe: null,
  setContext: (part) => set(part),
  setParam: (name, value, base) => set((s) => ({ recipe: { ...(s.recipe ?? base), [name]: value } })),
  setRecipe: (recipe) => set({ recipe }),
}))
