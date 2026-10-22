import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiClientError } from '@/api/client'
import { setpoints, type Constraints } from '@/api/constraints'
import { fetchSensitivity, type SensitivityResult } from '@/api/whatif'
import { SensitivityCurve } from '@/components/charts/lazy'
import { unitLabel } from '@/components/params/recipeValidation'

/** Points per curve: a detailed single sweep, and a coarser one per parameter when ranking. */
const SWEEP_STEPS = 40
const RANK_STEPS = 12

function errorText(error: Error): string {
  return error instanceof ApiClientError
    ? `${error.code}: ${error.message}${error.hint ? ` — ${error.hint}` : ''}`
    : error.message
}

/**
 * Sensitivity strip (roadmap R2-P7 task 4, Plan §13.5): the base run's P(fail) as one actionable
 * parameter sweeps its registry window, all others held. "Rank parameters" sweeps each actionable
 * parameter and orders them by the server's range_swing ("which knob matters most here").
 * Every number comes from POST /whatif/sensitivity.
 */
export function SensitivityPanel({
  baseRunId,
  constraints,
  threshold,
}: {
  baseRunId: string
  constraints: Constraints
  threshold: number | null
}) {
  const actionable = setpoints(constraints).filter((p) => p.actionable)
  const [parameter, setParameter] = useState(actionable[0]?.name ?? '')
  const [curves, setCurves] = useState<Record<string, SensitivityResult>>({})
  const [ranked, setRanked] = useState<Record<string, SensitivityResult>>({})
  const [progress, setProgress] = useState<number | null>(null)
  // Results belong to one base run; switching runs starts over.
  const [forRun, setForRun] = useState(baseRunId)
  if (forRun !== baseRunId) {
    setForRun(baseRunId)
    setCurves({})
    setRanked({})
  }

  const sweep = useMutation({
    mutationFn: (name: string) =>
      fetchSensitivity({ base_run_id: baseRunId, parameter: name, steps: SWEEP_STEPS }),
    onSuccess: (result) => setCurves((c) => ({ ...c, [result.parameter]: result })),
  })
  const rank = useMutation({
    // One request at a time: the endpoint is rate limited, and the order of results is stable.
    mutationFn: async () => {
      setRanked({})
      for (const [i, spec] of actionable.entries()) {
        setProgress(i)
        const result = await fetchSensitivity({
          base_run_id: baseRunId,
          parameter: spec.name,
          steps: RANK_STEPS,
        })
        setRanked((r) => ({ ...r, [spec.name]: result }))
      }
    },
    onSettled: () => setProgress(null),
  })

  const spec = (name: string) => actionable.find((p) => p.name === name)
  const shown = curves[parameter] ?? ranked[parameter] ?? null
  const unit = unitLabel(shown?.unit ?? spec(parameter)?.unit)
  const order = Object.values(ranked).sort((a, b) => (b.range_swing ?? 0) - (a.range_swing ?? 0))
  const busy = sweep.isPending || rank.isPending
  const error = sweep.error ?? rank.error

  return (
    <section
      aria-label="Sensitivity"
      className="flex flex-col gap-3 rounded border border-border bg-panel p-4"
    >
      <h3 className="text-xs font-semibold tracking-widest text-text-muted uppercase">Sensitivity</h3>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs text-text-muted">
          Parameter
          <select
            value={parameter}
            onChange={(e) => setParameter(e.target.value)}
            className="rounded border border-border bg-panel px-2 py-1 text-sm text-text"
          >
            {actionable.map((p) => (
              <option key={p.name} value={p.name}>
                {p.display_name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={!parameter || busy}
          onClick={() => sweep.mutate(parameter)}
          className="rounded border border-state-active px-3 py-1 text-xs font-semibold text-state-active uppercase disabled:opacity-40"
        >
          Sweep
        </button>
        <button
          type="button"
          disabled={actionable.length === 0 || busy}
          onClick={() => rank.mutate()}
          className="rounded border border-border px-3 py-1 text-xs font-semibold text-text uppercase hover:bg-panel-raised disabled:opacity-40"
        >
          Rank parameters
        </button>
        {progress != null && (
          <span role="status" className="text-xs text-text-muted">
            Sweeping {progress + 1} of {actionable.length}…
          </span>
        )}
      </div>

      {error && (
        <p role="alert" aria-label="Sensitivity error" className="text-xs text-risk-critical">
          {errorText(error)}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          {shown ? (
            <>
              <SensitivityCurve result={shown} threshold={threshold} unit={unit} />
              <p className="numeric text-xs" aria-label="Sweep summary">
                {spec(shown.parameter)?.display_name ?? shown.parameter}: current {shown.current_value}
                {unit ? ` ${unit}` : ''} · range swing {(shown.range_swing ?? 0).toFixed(3)} · local gradient{' '}
                {(shown.local_gradient ?? 0).toFixed(4)} per {unit || 'unit'} ·{' '}
                {shown.flip_point != null
                  ? `label flips at ${shown.flip_point}${unit ? ` ${unit}` : ''}`
                  : 'no label flip in the window'}{' '}
                ({(shown.points ?? []).length} points)
              </p>
            </>
          ) : (
            <p className="text-sm text-text-muted">
              Sweep a parameter to see the predicted P(fail) across its registry window.
            </p>
          )}
        </div>

        {order.length > 0 && (
          <table className="numeric w-full self-start text-xs" aria-label="Parameter ranking">
            <thead className="text-left text-text-muted">
              <tr>
                <th className="font-normal">#</th>
                <th className="font-normal">Parameter</th>
                <th className="text-right font-normal">Range swing</th>
                <th className="text-right font-normal">Local gradient</th>
                <th className="text-right font-normal">Flip at</th>
              </tr>
            </thead>
            <tbody>
              {order.map((r, i) => (
                <tr key={r.parameter} className={r.parameter === parameter ? 'bg-panel-raised' : undefined}>
                  <td>{i + 1}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => setParameter(r.parameter)}
                      className="text-left text-state-active"
                    >
                      {spec(r.parameter)?.display_name ?? r.parameter}
                    </button>
                  </td>
                  <td className="text-right">{(r.range_swing ?? 0).toFixed(3)}</td>
                  <td className="text-right">{(r.local_gradient ?? 0).toFixed(4)}</td>
                  <td className="text-right">{r.flip_point ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-text-muted">
        Sensitivity is not SHAP. A sweep moves one parameter across its window with every other parameter held
        at the base run, and reports how the model-predicted P(fail) responds. SHAP splits the model&apos;s
        margin among all features at this one point. The two answer different questions and need not agree.
      </p>
    </section>
  )
}
