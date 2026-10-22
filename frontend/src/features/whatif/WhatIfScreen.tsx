import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiClientError } from '@/api/client'
import { setpoints, useConstraints, type ParameterSpec } from '@/api/constraints'
import { useRunState } from '@/api/runs'
import { useWhatIf } from '@/api/whatif'
import { ParameterControl } from '@/components/params/ParameterControl'
import { clientErrors, serverErrors } from '@/components/params/recipeValidation'
import { RISK_TEXT } from '@/components/pipeline/stateStyle'
import { STAGE_META, STAGE_ORDER, type RiskLevel, type StageName } from '@/features/process-control/model'

import { DiffView } from './DiffView'
import { FinishedRunPicker } from './FinishedRunPicker'
import { useWhatIfDrafts, type Overrides } from './whatifStore'

const EMPTY: Overrides = {}

/**
 * What-If workbench (roadmap R2-P7 tasks 1-2; Plan §13.4-13.6). Fork a finished run, change one or
 * more parameters (windows from GET /constraints), then Evaluate (nothing saved) or Save as scenario
 * (a child run). The diff, stage reuse and every number come from POST /whatif.
 */
export function WhatIfScreen() {
  const [params, setParams] = useSearchParams()
  const baseRunId = params.get('base')
  const base = useRunState(baseRunId)
  const constraints = useConstraints().data
  const overrides = useWhatIfDrafts((s) => (baseRunId ? (s.drafts[baseRunId] ?? EMPTY) : EMPTY))
  const { setOverride, reset } = useWhatIfDrafts()
  const whatif = useWhatIf()
  const [label, setLabel] = useState('')

  const parent = base.data?.parameters ?? null
  const finished = base.data?.status === 'FINAL_RESULT'
  const recipe = parent ? { ...parent, ...overrides } : null
  const local = constraints && recipe ? clientErrors(constraints, recipe) : {}
  const server = serverErrors(whatif.isError ? whatif.error : null)
  const changed = Object.keys(overrides).length
  const canEvaluate = Boolean(baseRunId && finished && changed > 0 && Object.keys(local).length === 0)
  const result = whatif.data && whatif.data.parent_run_id === baseRunId ? whatif.data : null

  const evaluate = (persist: boolean) => {
    if (!baseRunId) return
    whatif.mutate({
      base_run_id: baseRunId,
      overrides,
      persist,
      label: persist && label.trim() ? label.trim() : null,
    })
  }

  const byStage = new Map<StageName, ParameterSpec[]>()
  for (const spec of constraints ? setpoints(constraints) : []) {
    const stage = spec.stage as StageName
    byStage.set(stage, [...(byStage.get(stage) ?? []), spec])
  }
  const ctx = (base.data?.context ?? {}) as {
    machine?: { machine_id?: string }
    product?: { product_id?: string }
    material_lot?: { material_lot_id?: string }
  }
  const prediction = base.data?.prediction as { p_fail?: number; label?: string; risk_level?: string } | null

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-sm font-semibold tracking-widest text-text-muted uppercase">What-If workbench</h2>

      <section
        aria-label="Base run"
        className="flex flex-wrap items-end justify-between gap-3 rounded border border-border bg-panel px-4 py-3"
      >
        <FinishedRunPicker
          value={baseRunId}
          onChange={(id) => {
            whatif.reset()
            setParams({ base: id })
          }}
        />
        {base.data && (
          <div className="numeric flex flex-wrap gap-4 text-sm">
            <span>
              <span className="text-text-muted">Machine</span> {ctx.machine?.machine_id ?? '—'}
            </span>
            <span>
              <span className="text-text-muted">Product</span> {ctx.product?.product_id ?? '—'}
            </span>
            <span>
              <span className="text-text-muted">Lot</span> {ctx.material_lot?.material_lot_id ?? '—'}
            </span>
            {prediction?.p_fail != null && (
              <span>
                <span className="text-text-muted">Predicted P(fail)</span> {prediction.p_fail.toFixed(2)}{' '}
                {prediction.label}
              </span>
            )}
            {prediction?.risk_level && (
              <span>
                <span className="text-text-muted">Operational risk</span>{' '}
                <span className={RISK_TEXT[prediction.risk_level as RiskLevel]}>{prediction.risk_level}</span>
              </span>
            )}
            <Link to={`/?run=${baseRunId}`} className="text-state-active">
              Open base run
            </Link>
          </div>
        )}
      </section>

      {!baseRunId && <p className="text-sm text-text-muted">Choose a finished run to branch from.</p>}
      {baseRunId && base.data && !finished && (
        <p role="alert" className="text-sm text-risk-high">
          This run is {base.data.status}. What-if needs a run with a final result.
        </p>
      )}

      {baseRunId && parent && constraints && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section
            aria-label="What-if parameters"
            className="flex flex-col gap-3 rounded border border-border bg-panel p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-text-muted">
                {changed === 0 ? 'No changes yet.' : `${changed} parameter${changed > 1 ? 's' : ''} changed.`}{' '}
                Windows come from the constraint registry ({constraints.version}).
              </p>
              <button
                type="button"
                onClick={() => {
                  reset(baseRunId)
                  whatif.reset()
                }}
                disabled={changed === 0}
                className="rounded border border-border px-2 py-0.5 text-xs text-text hover:bg-panel-raised disabled:opacity-40"
              >
                Reset to base
              </button>
            </div>
            {STAGE_ORDER.filter((s) => byStage.has(s)).map((stage) => (
              <fieldset key={stage} className="rounded border border-border px-3 pt-1 pb-3">
                <legend className="px-1 text-xs font-semibold text-text-muted">
                  {STAGE_META[stage].long}
                </legend>
                <div className="grid gap-3 md:grid-cols-2">
                  {byStage.get(stage)!.map((spec) => (
                    <ParameterControl
                      key={spec.name}
                      spec={spec}
                      value={recipe![spec.name] ?? Number.NaN}
                      changedFrom={parent[spec.name]}
                      error={local[spec.name] ?? server.fields[spec.name]}
                      onChange={(v) => setOverride(baseRunId, spec.name, v, parent[spec.name]!)}
                    />
                  ))}
                </div>
              </fieldset>
            ))}
          </section>

          <section
            aria-label="What-if result"
            className="flex flex-col gap-3 rounded border border-border bg-panel p-4"
          >
            <div className="flex flex-wrap items-end gap-2">
              <button
                type="button"
                disabled={!canEvaluate || whatif.isPending}
                onClick={() => evaluate(false)}
                className="rounded border border-state-active px-3 py-1 text-xs font-semibold text-state-active uppercase disabled:opacity-40"
              >
                Evaluate
              </button>
              <label className="flex flex-1 flex-col gap-1 text-xs text-text-muted">
                Scenario label (optional)
                <input
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  maxLength={200}
                  className="rounded border border-border bg-panel px-2 py-1 text-sm text-text"
                />
              </label>
              <button
                type="button"
                disabled={!canEvaluate || whatif.isPending}
                onClick={() => evaluate(true)}
                className="rounded border border-border px-3 py-1 text-xs font-semibold text-text uppercase hover:bg-panel-raised disabled:opacity-40"
              >
                Save as scenario
              </button>
            </div>
            {whatif.isPending && <p className="text-xs text-text-muted">Evaluating…</p>}
            {server.general.length > 0 && (
              <ul role="alert" aria-label="What-if errors" className="text-xs text-risk-critical">
                {server.general.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            )}
            {whatif.isError && server.general.length === 0 && Object.keys(server.fields).length === 0 && (
              <p role="alert" className="text-xs text-risk-critical">
                {whatif.error instanceof ApiClientError ? `${whatif.error.code}: ` : ''}
                {whatif.error.message}
              </p>
            )}
            {result ? (
              <>
                {result.run_id ? (
                  <p className="text-xs">
                    Saved as scenario{' '}
                    <Link to={`/history/${result.run_id}`} className="text-state-active">
                      {result.run_id.slice(0, 8)}
                    </Link>{' '}
                    (child of the base run; the base run is unchanged).
                  </p>
                ) : (
                  <p className="text-xs text-text-muted">Evaluated only; nothing was saved.</p>
                )}
                <DiffView
                  diff={result.diff}
                  constraints={constraints}
                  recomputed={result.recomputed_stages}
                  reused={result.reused_stages}
                />
              </>
            ) : (
              !whatif.isPending && (
                <p className="text-sm text-text-muted">Change parameters, then Evaluate to see the diff.</p>
              )
            )}
          </section>
        </div>
      )}
    </div>
  )
}
