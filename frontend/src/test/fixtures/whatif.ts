/** TEST-ONLY payloads for /whatif and /recommend (shapes from docs/openapi.json). */
import type { Schemas } from '@/api/client'

import { prediction, RUN_ID } from './runEvents'
import { runState } from './runState'

export const BASE_PARAMETERS = { drying_time_h: 1.5, melt_temp_c: 230, cooling_time_s: 11, cycle_time_s: 20 }

/** A finished base run whose parameters match the default constraints fixture. */
export function finishedBase() {
  return runState({
    status: 'FINAL_RESULT',
    parameters: { ...BASE_PARAMETERS },
    prediction: prediction({ p_fail: 0.62, label: 'FAIL', risk_level: 'HIGH' }) as never,
  })
}

export function whatIfDiff(): Schemas['RunDiff'] {
  return {
    parameters: [
      { name: 'cooling_time_s', from: 11, to: 14, delta: 3 },
      { name: 'cycle_time_s', from: 20, to: 23, delta: 3 },
    ],
    stages: [
      {
        stage: 'MATERIAL_CONDITIONING',
        health_from: 0.9,
        health_to: 0.9,
        risk_from: 'NORMAL',
        risk_to: 'NORMAL',
        change: 'unchanged',
      },
      {
        stage: 'PLASTICIZING',
        health_from: 0.8,
        health_to: 0.8,
        risk_from: 'LOW',
        risk_to: 'LOW',
        change: 'unchanged',
      },
      {
        stage: 'INJECTION',
        health_from: 0.8,
        health_to: 0.8,
        risk_from: 'LOW',
        risk_to: 'LOW',
        change: 'unchanged',
      },
      {
        stage: 'PACKING',
        health_from: 0.7,
        health_to: 0.7,
        risk_from: 'LOW',
        risk_to: 'LOW',
        change: 'unchanged',
      },
      {
        stage: 'COOLING',
        health_from: 0.41,
        health_to: 0.88,
        risk_from: 'HIGH',
        risk_to: 'LOW',
        change: 'improved',
      },
    ],
    prediction: {
      label_from: 'FAIL',
      label_to: 'PASS',
      p_fail_from: 0.62,
      p_fail_to: 0.31,
      p_fail_delta: -0.31,
      flipped: true,
    },
    operational_risk: { from: 'HIGH', to: 'MEDIUM', band_delta: -1 },
    constraint_compliance: { warnings_from: 1, warnings_to: 0, critical_from: 0, critical_to: 0 },
    cycle_time: { from: 20, to: 23, delta_s: 3, delta_pct: 15 },
  }
}

export function whatIfResult(over: Partial<Schemas['WhatIfResult']> = {}): Schemas['WhatIfResult'] {
  return {
    run_id: null,
    parent_run_id: RUN_ID,
    recomputed_stages: ['COOLING'],
    reused_stages: ['MATERIAL_CONDITIONING', 'PLASTICIZING', 'INJECTION', 'PACKING'],
    stage_results: [],
    prediction: prediction({ p_fail: 0.31, label: 'PASS', risk_level: 'MEDIUM' }) as never,
    diff: whatIfDiff(),
    ...over,
  }
}

export function candidate(
  over: Partial<Schemas['RecommendationCandidate']> = {},
): Schemas['RecommendationCandidate'] {
  return {
    option_rank: 1,
    option_label: 'Minimal change',
    changes: [{ parameter: 'cooling_time_s', from_value: 11, to_value: 14, delta: 3, unit: 's' }],
    predicted_p_fail: 0.31,
    predicted_label: 'PASS',
    delta_p_fail: -0.31,
    stage_health_after: [{ stage: 'COOLING', health_score: 0.88, risk_level: 'LOW' }],
    constraint_status: 'ALL_SATISFIED',
    guard_checks: [
      { check: 'box', passed: true, detail: 'within windows' },
      { check: 'couplings', passed: true, detail: 'all coupling rules hold' },
      { check: 'stability', passed: true, detail: '1/20 flips' },
    ],
    stability: { trials: 20, flips: 1, stable: true },
    in_distribution: true,
    flags: [],
    cycle_time_delta_s: 3,
    cycle_time_delta_pct: 15,
    change_cost: 0.1,
    score: 0.2,
    rationale: ['Cooling stage dominates the risk'],
    search_method: 'coordinate',
    ...over,
  }
}

export function recommendOut(over: Partial<Schemas['RecommendOut']> = {}): Schemas['RecommendOut'] {
  return {
    request_id: 'req-rec-1',
    base_p_fail: 0.62,
    base_label: 'FAIL',
    candidates: [
      candidate(),
      candidate({
        option_rank: 2,
        option_label: 'Aggressive',
        changes: [
          { parameter: 'cooling_time_s', from_value: 11, to_value: 16, delta: 5, unit: 's' },
          { parameter: 'melt_temp_c', from_value: 230, to_value: 220, delta: -10, unit: 'c' },
        ],
        predicted_p_fail: 0.18,
        delta_p_fail: -0.44,
        in_distribution: false,
        flags: ['EXTRAPOLATED'],
      }),
    ],
    evaluated_count: 42,
    rejected_counts: { couplings: 3 },
    empty_reason: null,
    model_version: 'fusion-1.0.0',
    constraints_version: 'constraints-1.0.0',
    disclaimer_key: 'DISCLAIMER_RECOMMENDATION',
    compute_ms: 120,
    ...over,
  }
}
