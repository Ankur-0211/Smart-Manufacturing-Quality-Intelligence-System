/**
 * Client-side recipe checks and server 422 mapping (roadmap R2-P6 task 4).
 * Bounds come only from GET /constraints (rule B6); coupling rules are evaluated by the server.
 */
import { ApiClientError } from '@/api/client'
import { outOfRange, setpoints, type Constraints, type ParameterSpec } from '@/api/constraints'
import type { Recipe } from '@/stores/runSetup'

const UNIT_LABEL: Record<string, string> = {
  c: '°C',
  mm_s: 'mm/s',
  ton: 't',
  pct: '%',
  dimensionless: '',
}

export function unitLabel(unit: string | null | undefined): string {
  if (!unit) return ''
  return UNIT_LABEL[unit] ?? unit
}

export function rangeText(spec: ParameterSpec): string {
  const unit = unitLabel(spec.unit)
  return `${spec.min}–${spec.max}${unit ? ` ${unit}` : ''}`
}

/** Field -> message for values missing, non-numeric or outside the registry window. */
export function clientErrors(constraints: Constraints, recipe: Recipe): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const spec of setpoints(constraints)) {
    const value = recipe[spec.name]
    if (value === undefined || Number.isNaN(value)) errors[spec.name] = 'Enter a number'
    else if (outOfRange(spec, value)) errors[spec.name] = `Allowed ${rangeText(spec)}`
  }
  return errors
}

export interface ServerErrors {
  /** Recipe field or context field (machine_id …) -> message. */
  fields: Record<string, string>
  /** Messages not tied to one field, and every coupling rule (they name their rule id). */
  general: string[]
}

/** Map a 422 envelope's per-field `details` onto form fields. */
export function serverErrors(error: unknown): ServerErrors {
  const out: ServerErrors = { fields: {}, general: [] }
  if (!(error instanceof ApiClientError)) return out
  const details = error.details ?? []
  for (const d of details) {
    const field = d.field?.replace(/^(parameters|overrides)\./, '') ?? null
    if (d.code === 'COUPLING_VIOLATION') out.general.push(d.message)
    if (field) out.fields[field] = d.limit != null ? `${d.message} (limit ${d.limit})` : d.message
    else if (d.code !== 'COUPLING_VIOLATION') out.general.push(d.message)
  }
  if (details.length === 0) {
    if (error.field) out.fields[error.field] = error.message
    else out.general.push(`${error.code}: ${error.message}`)
  }
  return out
}
