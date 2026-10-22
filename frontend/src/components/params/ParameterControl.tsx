import type { ParameterSpec } from '@/api/constraints'
import { cn } from '@/lib/utils'

import { rangeText, unitLabel } from './recipeValidation'

/** One registry setpoint: slider + numeric input with window, step and unit from GET /constraints. */
export function ParameterControl({
  spec,
  value,
  error,
  onChange,
  changedFrom,
}: {
  spec: ParameterSpec
  value: number
  error?: string
  onChange: (value: number) => void
  /** Shown when the value differs from a reference (e.g. the what-if parent). */
  changedFrom?: number
}) {
  const id = `param-${spec.name}`
  const unit = unitLabel(spec.unit)
  const min = spec.min ?? undefined
  const max = spec.max ?? undefined
  const sliderValue = Number.isNaN(value) ? (spec.nominal as number) : value
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <label htmlFor={id} className="text-text">
          {spec.display_name}
          {!spec.actionable && <span className="ml-1 text-text-muted">(not a recommendation knob)</span>}
        </label>
        <span className="numeric text-text-muted">{rangeText(spec)}</span>
      </div>
      <div className="flex items-center gap-2">
        <input
          type="range"
          aria-label={`${spec.display_name} slider`}
          min={min}
          max={max}
          step={spec.step ?? undefined}
          value={sliderValue}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 accent-state-active"
        />
        <input
          id={id}
          type="number"
          min={min}
          max={max}
          step={spec.step ?? undefined}
          value={Number.isNaN(value) ? '' : value}
          onChange={(e) => onChange(e.target.value === '' ? Number.NaN : Number(e.target.value))}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          className={cn(
            'numeric w-24 rounded border bg-panel px-2 py-0.5 text-right text-sm text-text',
            error ? 'border-risk-critical' : 'border-border',
          )}
        />
        <span className="w-10 text-xs text-text-muted">{unit}</span>
      </div>
      {changedFrom !== undefined && changedFrom !== value && !error && (
        <p className="numeric text-xs text-state-active">
          changed from {changedFrom}
          {unit ? ` ${unit}` : ''}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-xs text-risk-critical">
          {error}
        </p>
      )}
    </div>
  )
}
