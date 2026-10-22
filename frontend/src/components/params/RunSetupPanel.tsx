import { useState } from 'react'

import { useConstraints, nominalRecipe, setpoints, type ParameterSpec } from '@/api/constraints'
import { useMachines, useMaterials, useProducts } from '@/api/reference'
import { STAGE_META, STAGE_ORDER, type StageName } from '@/features/process-control/model'
import { cn } from '@/lib/utils'
import { useRunSetup } from '@/stores/runSetup'

import { CreateLotDialog } from './CreateLotDialog'
import { clientErrors, rangeText, unitLabel, type ServerErrors } from './recipeValidation'
import { useEffectiveRecipe } from './useEffectiveRecipe'

function Picker({
  label,
  value,
  onChange,
  options,
  loading,
  error,
}: {
  label: string
  value: string | null
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  loading: boolean
  error?: string
}) {
  return (
    <label className="flex min-w-48 flex-1 flex-col gap-1 text-xs text-text-muted">
      {label}
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        className={cn(
          'rounded border bg-panel px-2 py-1 text-sm text-text',
          error ? 'border-risk-critical' : 'border-border',
        )}
      >
        <option value="" disabled>
          {loading ? 'Loading…' : `Select ${label.toLowerCase()}`}
        </option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && <span className="text-risk-critical">{error}</span>}
    </label>
  )
}

function ParameterControl({
  spec,
  value,
  error,
  onChange,
}: {
  spec: ParameterSpec
  value: number
  error?: string
  onChange: (value: number) => void
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
      {error && (
        <p id={`${id}-error`} className="text-xs text-risk-critical">
          {error}
        </p>
      )}
    </div>
  )
}

/**
 * Run setup (roadmap R2-P6 tasks 3-4): machine / product / lot pickers and one control per registry
 * setpoint, grouped by stage. Every bound, step, unit and default comes from GET /constraints.
 */
export function RunSetupPanel({
  server,
  onUseRun,
}: {
  /** Field errors from the last rejected run creation (422 details). */
  server: ServerErrors
  /** Copies the open run's context and recipe into the draft, when a run is open. */
  onUseRun?: () => void
}) {
  const constraintsQuery = useConstraints()
  const machines = useMachines()
  const products = useProducts()
  const materials = useMaterials()
  const { machineId, productId, lotId, setContext, setParam, setRecipe } = useRunSetup()
  const [creatingLot, setCreatingLot] = useState(false)
  const recipe = useEffectiveRecipe()
  const constraints = constraintsQuery.data

  if (constraintsQuery.isError) {
    return (
      <p role="alert" className="text-sm text-risk-critical">
        Cannot load the constraint registry: {constraintsQuery.error.message}
      </p>
    )
  }
  if (!constraints || !recipe)
    return <p className="text-sm text-text-muted">Loading the constraint registry…</p>

  const local = clientErrors(constraints, recipe)
  const byStage = new Map<StageName, ParameterSpec[]>()
  for (const spec of setpoints(constraints)) {
    const stage = spec.stage as StageName
    byStage.set(stage, [...(byStage.get(stage) ?? []), spec])
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold tracking-widest text-text-muted uppercase">Run setup</h3>
        <div className="flex gap-2">
          {onUseRun && (
            <button
              type="button"
              onClick={onUseRun}
              className="rounded border border-border px-2 py-0.5 text-xs text-text hover:bg-panel-raised"
            >
              Use this run&apos;s setup
            </button>
          )}
          <button
            type="button"
            onClick={() => setRecipe(nominalRecipe(constraints))}
            className="rounded border border-border px-2 py-0.5 text-xs text-text hover:bg-panel-raised"
          >
            Load nominal recipe
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3" role="group" aria-label="Run context selection">
        <Picker
          label="Machine"
          value={machineId}
          onChange={(v) => setContext({ machineId: v })}
          loading={machines.isLoading}
          error={server.fields.machine_id}
          options={(machines.data ?? []).map((m) => ({
            value: m.machine_id,
            label: `${m.machine_id} · ${m.machine_type} · max clamp ${m.max_clamp_force_ton} t`,
          }))}
        />
        <Picker
          label="Product"
          value={productId}
          onChange={(v) => setContext({ productId: v })}
          loading={products.isLoading}
          error={server.fields.product_id}
          options={(products.data ?? []).map((p) => ({
            value: p.product_id,
            label: `${p.product_id} · ${p.cavity_count} cavity`,
          }))}
        />
        <Picker
          label="Material lot"
          value={lotId}
          onChange={(v) => setContext({ lotId: v })}
          loading={materials.isLoading}
          error={server.fields.material_lot_id}
          options={(materials.data ?? []).map((l) => ({
            value: l.material_lot_id,
            label: `${l.material_lot_id} · ${l.resin_grade} · moisture ${l.moisture_pct} %`,
          }))}
        />
        <button
          type="button"
          onClick={() => setCreatingLot(true)}
          className="self-end rounded border border-border px-2 py-1 text-xs text-text hover:bg-panel-raised"
        >
          New lot…
        </button>
      </div>
      {creatingLot && (
        <CreateLotDialog
          constraints={constraints}
          onClose={() => setCreatingLot(false)}
          onCreated={(id) => {
            setContext({ lotId: id })
            setCreatingLot(false)
          }}
        />
      )}

      {server.general.length > 0 && (
        <ul role="alert" aria-label="Run setup errors" className="text-xs text-risk-critical">
          {server.general.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}

      <p className="text-xs text-text-muted">
        Applies to the next run. Windows come from the constraint registry ({constraints.version}); coupling
        rules are checked by the server when the run is created.
      </p>

      {STAGE_ORDER.filter((s) => byStage.has(s)).map((stage) => (
        <fieldset key={stage} className="rounded border border-border px-3 pt-1 pb-3">
          <legend className="px-1 text-xs font-semibold text-text-muted">{STAGE_META[stage].long}</legend>
          <div className="grid gap-3 md:grid-cols-2">
            {byStage.get(stage)!.map((spec) => (
              <ParameterControl
                key={spec.name}
                spec={spec}
                value={recipe[spec.name] ?? Number.NaN}
                error={local[spec.name] ?? server.fields[spec.name]}
                onChange={(v) => setParam(spec.name, v, recipe)}
              />
            ))}
          </div>
        </fieldset>
      ))}
    </div>
  )
}
