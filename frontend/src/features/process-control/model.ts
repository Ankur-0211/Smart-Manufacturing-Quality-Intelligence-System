/**
 * PROVISIONAL view types for the Process Control workspace.
 *
 * Transcribed from roadmap §7.9 (StageResult), §7.12 (PredictionResult), §7.17 (SimulationState) and
 * §9.5 (events), because the backend does not expose these shapes yet (they depend on Role 1's
 * `app.contracts`). Once the simulation endpoints exist (R2-P4), replace every type here with the
 * generated OpenAPI types from `@/api/generated/schema`. Field names are already the canonical ones,
 * so the swap should only remove this file.
 */

export const STAGE_ORDER = [
  'MATERIAL_CONDITIONING',
  'PLASTICIZING',
  'INJECTION',
  'PACKING',
  'COOLING',
  'QUALITY_INSPECTION',
] as const

export type StageName = (typeof STAGE_ORDER)[number]

export interface StageMeta {
  name: StageName
  index: number
  short: string
  long: string
}

/** Display names (roadmap §1.4). Canonical enum values never change; labels may. */
export const STAGE_META: Record<StageName, StageMeta> = {
  MATERIAL_CONDITIONING: {
    name: 'MATERIAL_CONDITIONING',
    index: 1,
    short: 'Material',
    long: 'Material Conditioning',
  },
  PLASTICIZING: { name: 'PLASTICIZING', index: 2, short: 'Thermal', long: 'Plasticizing / Thermal' },
  INJECTION: { name: 'INJECTION', index: 3, short: 'Injection', long: 'Injection / Fill' },
  PACKING: { name: 'PACKING', index: 4, short: 'Packing', long: 'Packing / Holding' },
  COOLING: { name: 'COOLING', index: 5, short: 'Cooling', long: 'Cooling / Ejection' },
  QUALITY_INSPECTION: {
    name: 'QUALITY_INSPECTION',
    index: 6,
    short: 'Quality',
    long: 'Quality Inspection / Fusion',
  },
}

export const RISK_LEVELS = ['NORMAL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
export type RiskLevel = (typeof RISK_LEVELS)[number]

export type RunStatus =
  | 'INITIALIZED'
  | 'MATERIAL_CONDITIONING'
  | 'PLASTICIZING'
  | 'INJECTION'
  | 'PACKING'
  | 'COOLING'
  | 'QUALITY_INSPECTION'
  | 'FINAL_RESULT'
  | 'PAUSED'
  | 'BLOCKED'
  | 'ABORTED'

export const TERMINAL_STATUSES: ReadonlySet<RunStatus> = new Set(['FINAL_RESULT', 'ABORTED'])

export type RunMode = 'auto' | 'stepwise'
export type SpeedFactor = '0.5x' | '1x' | '2x' | 'instant'

export type ConstraintSeverity = 'INFO' | 'WARNING' | 'CRITICAL'

export interface ConstraintBreach {
  rule_id: string
  severity: ConstraintSeverity
  parameters: string[]
  value: number | null
  limit: number | null
  message: string
  hint: string | null
}

export interface StageAnomaly {
  flag: boolean
  score: number
  method: string
  contributors: { feature: string; deviation: number }[]
  note?: string
}

export type IndicatorValue = number | string | boolean | null

export interface StageResultView {
  stage_name: StageName
  sequence_index: number
  substate: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'BLOCKED'
  inputs_used: Record<string, IndicatorValue>
  upstream_in: Record<string, IndicatorValue>
  upstream_out: Record<string, IndicatorValue>
  health_score: number
  risk_level: RiskLevel
  risk_ordinal: number
  anomaly: StageAnomaly
  indicators: Record<string, IndicatorValue>
  indicator_provenance: Record<string, string>
  notes: string[]
  constraint_breaches: ConstraintBreach[]
  blocked: boolean
  block_reason: string | null
  overridden?: boolean
}

export interface Caveat {
  code: string
  message: string
  features: string[]
}

export interface PredictionView {
  label: 'PASS' | 'FAIL'
  p_fail: number
  threshold_used: number
  model_version: string
  risk_level: RiskLevel
  risk_drivers: { source: 'model' | 'anomaly' | 'constraint'; detail: string; weight: number }[]
  stage_risk_mass: { stage: StageName; share: number }[]
  caveats: Caveat[]
  anomaly_global: { is_anomaly: boolean; score: number; note: string } | null
  ood: { is_out_of_distribution: boolean; features_outside: { feature: string }[] } | null
  constraint_override_applied: boolean
  inference_backend: 'real' | 'mock'
  is_mock: boolean
}

export const EVENT_TYPES = [
  'run.started',
  'stage.started',
  'stage.progress',
  'stage.completed',
  'anomaly.flagged',
  'constraint.breached',
  'stage.blocked',
  'stage.override_acknowledged',
  'prediction.ready',
  'run.completed',
  'run.paused',
  'run.resumed',
  'run.reset',
  'run.aborted',
  'run.error',
] as const

export type EventType = (typeof EVENT_TYPES)[number]

/** SSE event envelope (roadmap §9.5.3). */
export interface SimulationEvent {
  run_id: string
  seq: number
  ts: string
  type: EventType
  stage: StageName | null
  payload: Record<string, unknown>
}

/** Subset of SimulationState (roadmap §7.17) needed to re-sync after an SSE gap. */
export interface SimulationSnapshot {
  run_id: string
  status: RunStatus
  mode: RunMode
  blocked_stage: StageName | null
  current_stage: StageName | null
  stage_results: StageResultView[]
  prediction: PredictionView | null
  timeline: SimulationEvent[]
  last_seq: number
}
