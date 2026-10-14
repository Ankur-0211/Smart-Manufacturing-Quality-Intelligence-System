/**
 * TEST-ONLY event-stream builders shaped like roadmap §9.5.3 / §7.9 / §7.12.
 * Values are arbitrary test inputs, never shown in the app (ESLint blocks `@/test/*` imports in src).
 */
import {
  STAGE_ORDER,
  type EventType,
  type PredictionView,
  type RiskLevel,
  type SimulationEvent,
  type StageName,
  type StageResultView,
} from '@/features/process-control/model'

export const RUN_ID = '9f2c0000-0000-4000-8000-000000000001'

export function stageResult(
  stage: StageName,
  over: Partial<StageResultView> & { health_score?: number; risk_level?: RiskLevel } = {},
): StageResultView {
  const index = STAGE_ORDER.indexOf(stage) + 1
  return {
    stage_name: stage,
    sequence_index: index,
    substate: 'COMPLETED',
    inputs_used: { test_input: index },
    upstream_in: {},
    upstream_out: {},
    health_score: 0.9,
    risk_level: 'NORMAL',
    risk_ordinal: 0,
    anomaly: { flag: false, score: 0.05, method: 'zscore', contributors: [] },
    indicators: { test_indicator: 1.5 },
    indicator_provenance: { test_indicator: 'heuristic' },
    notes: [],
    constraint_breaches: [],
    blocked: false,
    block_reason: null,
    ...over,
  }
}

export function prediction(over: Partial<PredictionView> = {}): PredictionView {
  return {
    label: 'FAIL',
    p_fail: 0.71,
    threshold_used: 0.42,
    model_version: 'fusion-test',
    risk_level: 'HIGH',
    risk_drivers: [{ source: 'model', detail: 'p_fail band HIGH', weight: 1 }],
    stage_risk_mass: [
      { stage: 'COOLING', share: 0.58 },
      { stage: 'PLASTICIZING', share: 0.24 },
      { stage: 'PACKING', share: 0.11 },
      { stage: 'INJECTION', share: 0.07 },
    ],
    caveats: [],
    anomaly_global: null,
    ood: null,
    constraint_override_applied: false,
    inference_backend: 'real',
    is_mock: false,
    ...over,
  }
}

export class StreamBuilder {
  private seq = 0
  readonly events: SimulationEvent[] = []

  constructor(private readonly runId: string = RUN_ID) {}

  push(type: EventType, stage: StageName | null = null, payload: Record<string, unknown> = {}): this {
    this.seq += 1
    this.events.push({
      run_id: this.runId,
      seq: this.seq,
      ts: `2026-10-15T12:04:${String(this.seq).padStart(2, '0')}.000Z`,
      type,
      stage,
      payload,
    })
    return this
  }

  stage(stage: StageName, result: StageResultView = stageResult(stage)): this {
    this.push('stage.started', stage, { index: result.sequence_index, inputs_in_scope: result.inputs_used })
    if (result.anomaly.flag)
      this.push('anomaly.flagged', stage, { ...result.anomaly, scope: `stage:${stage}` })
    return this.push('stage.completed', stage, result as unknown as Record<string, unknown>)
  }
}

/** A complete happy-path run: started, five stages, prediction, completed. */
export function fullRun(pred: PredictionView = prediction()): SimulationEvent[] {
  const b = new StreamBuilder().push('run.started')
  for (const s of STAGE_ORDER.slice(0, 5)) {
    b.stage(
      s,
      s === 'COOLING'
        ? stageResult(s, { health_score: 0.41, risk_level: 'HIGH', risk_ordinal: 3 })
        : s === 'PLASTICIZING'
          ? stageResult(s, {
              health_score: 0.61,
              risk_level: 'MEDIUM',
              risk_ordinal: 2,
              anomaly: {
                flag: true,
                score: 0.8,
                method: 'percentile_band',
                contributors: [],
                note: 'residence',
              },
            })
          : stageResult(s),
    )
  }
  b.push('prediction.ready', 'QUALITY_INSPECTION', pred as unknown as Record<string, unknown>)
  b.push('run.completed')
  return b.events
}
