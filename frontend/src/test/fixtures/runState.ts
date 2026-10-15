/** TEST-ONLY builders for API payloads of the simulation endpoints (shapes from docs/openapi.json). */
import type { ScenarioSummary, SimulationState } from '@/api/runs'

import { fullRun, prediction, RUN_ID, stageResult } from './runEvents'

export function runState(over: Partial<SimulationState> = {}): SimulationState {
  return {
    run_id: RUN_ID,
    status: 'INITIALIZED',
    mode: 'auto',
    speed_factor: '1x',
    halt_on_critical: true,
    blocked_stage: null,
    current_stage: null,
    override_count: 0,
    abort_reason: null,
    created_at: '2026-10-15T12:00:00Z',
    updated_at: '2026-10-15T12:00:00Z',
    started_at: null,
    completed_at: null,
    context: {
      machine: { machine_id: 'MC-03' },
      product: { product_id: 'PP-JBOX-42' },
      material_lot: { material_lot_id: 'A-771' },
    },
    parameters: { melt_temp_c: 230 },
    stage_results: [],
    prediction: null,
    timeline: [],
    parent_run_id: null,
    is_whatif: false,
    scenario_label: null,
    inference_backend: 'mock',
    constraints_version: 'constraints-0.1.0',
    last_seq: 0,
    ...over,
  }
}

/** A finished run as GET /simulation/runs/{id} returns it. */
export function finishedRunState(over: Partial<SimulationState> = {}): SimulationState {
  const events = fullRun()
  return runState({
    status: 'FINAL_RESULT',
    stage_results: (
      ['MATERIAL_CONDITIONING', 'PLASTICIZING', 'INJECTION', 'PACKING', 'COOLING'] as const
    ).map(
      (s) =>
        stageResult(
          s,
          s === 'COOLING' ? { health_score: 0.41, risk_level: 'HIGH', risk_ordinal: 3 } : {},
        ) as never,
    ),
    prediction: prediction() as never,
    timeline: events as never,
    last_seq: events.length,
    ...over,
  })
}

export function summary(i: number, over: Partial<ScenarioSummary> = {}): ScenarioSummary {
  return {
    run_id: `${String(i).padStart(8, '0')}-0000-4000-8000-000000000000`,
    parent_run_id: null,
    is_whatif: false,
    scenario_label: null,
    status: 'FINAL_RESULT',
    created_at: '2026-10-15T12:00:00Z',
    machine_id: 'MC-03',
    product_id: 'PP-JBOX-42',
    material_lot_id: 'A-771',
    label: 'FAIL',
    p_fail: 0.71,
    risk_level: 'HIGH',
    model_version: 'mock-0.0.0',
    inference_backend: 'mock',
    ...over,
  }
}
