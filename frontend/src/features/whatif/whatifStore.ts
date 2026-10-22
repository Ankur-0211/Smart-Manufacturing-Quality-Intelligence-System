/**
 * What-if drafts (roadmap R2-P7 task 1, Plan §13.7): overrides forked from a base run, kept per base
 * run in memory. Nothing is persisted until the operator evaluates with "Save as scenario".
 * Only values that differ from the parent are kept, so Reset restores the parent exactly.
 */
import { create } from 'zustand'

export type Overrides = Record<string, number>

interface WhatIfDraftState {
  drafts: Record<string, Overrides>
  setOverride: (baseRunId: string, name: string, value: number, parentValue: number) => void
  setOverrides: (baseRunId: string, overrides: Overrides) => void
  reset: (baseRunId: string) => void
}

export const useWhatIfDrafts = create<WhatIfDraftState>((set) => ({
  drafts: {},
  setOverride: (baseRunId, name, value, parentValue) =>
    set((s) => {
      const current = { ...(s.drafts[baseRunId] ?? {}) }
      if (value === parentValue) delete current[name]
      else current[name] = value
      return { drafts: { ...s.drafts, [baseRunId]: current } }
    }),
  setOverrides: (baseRunId, overrides) =>
    set((s) => ({ drafts: { ...s.drafts, [baseRunId]: { ...overrides } } })),
  reset: (baseRunId) =>
    set((s) => {
      const drafts = { ...s.drafts }
      delete drafts[baseRunId]
      return { drafts }
    }),
}))
