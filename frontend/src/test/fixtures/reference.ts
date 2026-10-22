/**
 * TEST-ONLY payloads for GET /constraints and the reference lists (shapes from docs/openapi.json).
 * Windows here are arbitrary test values; production bounds come only from the API (rule B6).
 */
import type { Constraints, ParameterSpec } from '@/api/constraints'
import type { Machine, MaterialLot, Product } from '@/api/reference'

export function paramSpec(over: Partial<ParameterSpec> & Pick<ParameterSpec, 'name'>): ParameterSpec {
  return {
    kind: 'setpoint',
    stage: 'PLASTICIZING',
    unit: 'c',
    dtype: 'float',
    min: 0,
    max: 10,
    nominal: 5,
    step: 1,
    actionable: true,
    display_name: over.name,
    provenance: 'heuristic',
    ...over,
  }
}

export function constraintsPayload(parameters?: ParameterSpec[]): Constraints {
  return {
    version: 'constraints-test',
    registry_version: 'constraints-test',
    content_hash: 'abc',
    parameters: parameters ?? [
      paramSpec({
        name: 'drying_time_h',
        stage: 'MATERIAL_CONDITIONING',
        unit: 'h',
        display_name: 'Drying Time',
        min: 0,
        max: 6,
        nominal: 1.5,
        step: 0.25,
      }),
      paramSpec({
        name: 'melt_temp_c',
        display_name: 'Melt Temperature',
        min: 180,
        max: 295,
        nominal: 230,
        step: 1,
      }),
      paramSpec({
        name: 'cooling_time_s',
        stage: 'COOLING',
        unit: 's',
        display_name: 'Cooling Time',
        min: 3,
        max: 30,
        nominal: 11,
        step: 0.5,
      }),
      paramSpec({
        name: 'cycle_time_s',
        stage: 'COOLING',
        unit: 's',
        display_name: 'Cycle Time',
        min: 8,
        max: 60,
        nominal: 20,
        step: 0.5,
        actionable: false,
      }),
    ],
    coupling_rules: [],
    hard_constraints: [],
    resin_grades: {},
    risk_bands: { stage_health: {}, p_fail: {} },
  } as unknown as Constraints
}

export const machines = [
  { machine_id: 'MC-02', machine_type: 'HYDRAULIC', max_clamp_force_ton: 175 },
  { machine_id: 'MC-03', machine_type: 'ELECTRIC', max_clamp_force_ton: 110 },
] as unknown as Machine[]

export const products = [{ product_id: 'PP-JBOX-42', cavity_count: 1 }] as unknown as Product[]

export const materials = [
  { material_lot_id: 'A-771', resin_grade: 'PP-H', moisture_pct: 0.04 },
  { material_lot_id: 'D-105', resin_grade: 'PP-H', moisture_pct: 0.22 },
] as unknown as MaterialLot[]
