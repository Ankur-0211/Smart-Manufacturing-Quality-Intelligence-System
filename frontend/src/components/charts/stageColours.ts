import type { StageName } from '@/features/process-control/model'

/** One colour per stage (S1-S5), stable across screens. Presentation only. */
export const STAGE_COLOURS: Record<StageName, string> = {
  MATERIAL_CONDITIONING: '#22d3ee',
  PLASTICIZING: '#f97316',
  INJECTION: '#a855f7',
  PACKING: '#f59e0b',
  COOLING: '#3b82f6',
  QUALITY_INSPECTION: '#8b98a7',
}
