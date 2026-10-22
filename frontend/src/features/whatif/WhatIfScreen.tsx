import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiClientError } from '@/api/client'
import { setpoints, useConstraints, type ParameterSpec } from '@/api/constraints'
import { useRunState } from '@/api/runs'
import { LIVE_DEBOUNCE_MS, useLiveWhatIf, useWhatIf } from '@/api/whatif'
import { ParameterControl } from '@/components/params/ParameterControl'
import { clientErrors, serverErrors } from '@/components/params/recipeValidation'
import { RISK_TEXT } from '@/components/pipeline/stateStyle'
import { STAGE_META, STAGE_ORDER, type RiskLevel, type StageName } from '@/features/process-control/model'

import { DiffView } from './DiffView'
import { FinishedRunPicker } from './FinishedRunPicker'
import { SensitivityPanel } from './SensitivityPanel'
import { useWhatIfDrafts, type Overrides } from './whatifStore'

const EMPTY: Overrides = {}

/**
 * What-If workbench (roadmap R2-P7 tasks 1-2; Plan §13.4-13.6). Fork a finished run, change one or
 * more parameters (windows from GET /constraints), then Evaluate (nothing saved) or Save as scenario
 * (a child run). Live mode (P1) re-evaluates with persist=false after each 150 ms pause in editing.
 * The diff, stage reuse and every number come from POST /whatif.
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
  const [live, setLive] = useState(false)

  const parent = base.data?.parameters ?? null
  const finished = base.data?.status === 'FINAL_RESULT'
  const recipe = parent ? { ...parent, ...overrides } : null
  const local = constraints && recipe ? clientErrors(constraints, recipe) : {}
  const changed = Object.keys(overrides).length
  const canEvaluate = Boolean(baseRunId && finished && changed > 0 && Object.keys(local).length === 0)
  const liveQuery = useLiveWhatIf(baseRunId, overrides, live && canEvaluate)
  const error = live ? liveQuery.error : whatif.isError ? whatif.error : null
  const server = serverErrors(error)
  const shown = live ? (changed > 0 ? liveQuery.data : undefined) : whatif.data
  const result = shown && shown.parent_run_id === baseRunId ? shown : null
  const busy = live ? liveQuery.isFetching : whatif.isPending
  // In live mode the diff is the live preview; a scenario saved meanwhile is reported separately.
  const saved = whatif.data?.parent_run_id === baseRunId ? (whatif.data?.run_id ?? null) : null
  const savedId = live ? saved : (result?.run_id ?? null)

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
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold tracking-widest text-text-muted uppercase">What-If workbench</h2>
        <Link
          to={baseRunId ? `/what-if/compare?a=${baseRunId}` : '/what-if/compare'}
          className="text-xs text-state-active"
        >
          A/B compare saved runs
        </Link>
      </div>

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
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} />
              Live: re-evaluate {LIVE_DEBOUNCE_MS} ms after each change (nothing saved)
            </label>
            <div className="flex flex-wrap items-end gap-2">
              <button
                type="button"
                disabled={!canEvaluate || whatif.isPending || live}
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
            {busy && <p className="text-xs text-text-muted">Evaluating…</p>}
            {server.general.length > 0 && (
              <ul role="alert" aria-label="What-if errors" className="text-xs text-risk-critical">
                {server.general.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            )}
            {error && server.general.length === 0 && Object.keys(server.fields).length === 0 && (
              <p role="alert" className="text-xs text-risk-critical">
                {error instanceof ApiClientError ? `${error.code}: ` : ''}
                {error.message}
              </p>
            )}
            {result ? (
              <>
                {savedId ? (
                  <p className="text-xs">
                    Saved as scenario{' '}
                    <Link to={`/history/${savedId}`} className="text-state-active">
                      {savedId.slice(0, 8)}
                    </Link>{' '}
                    (child of the base run; the base run is unchanged).{' '}
                    <Link to={`/what-if/compare?a=${baseRunId}&b=${savedId}`} className="text-state-active">
                      Compare A/B
                    </Link>
                  </p>
                ) : (
                  <p className="text-xs text-text-muted">
                    {live ? 'Live preview' : 'Evaluated only'}; nothing was saved.
                  </p>
                )}
                <DiffView
                  diff={result.diff}
                  constraints={constraints}
                  recomputed={result.recomputed_stages}
                  reused={result.reused_stages}
                />
              </>
            ) : (
              !busy && (
                <p className="text-sm text-text-muted">
                  {live
                    ? 'Change a parameter to see the diff.'
                    : 'Change parameters, then Evaluate to see the diff.'}
                </p>
              )
            )}
          </section>
        </div>
      )}

      {baseRunId && parent && constraints && finished && (
        <SensitivityPanel
          baseRunId={baseRunId}
          constraints={constraints}
          threshold={(base.data?.prediction as { threshold_used?: number } | null)?.threshold_used ?? null}
        />
      )}
    </div>
  )
}
