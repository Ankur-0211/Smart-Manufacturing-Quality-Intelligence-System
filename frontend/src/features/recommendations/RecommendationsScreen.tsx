import { useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ApiClientError } from '@/api/client'
import { setpoints, useConstraints, type Constraints } from '@/api/constraints'
import { useRunState } from '@/api/runs'
import { useRecommend, type RecommendationCandidate } from '@/api/whatif'
import { unitLabel } from '@/components/params/recipeValidation'
import { RISK_TEXT } from '@/components/pipeline/stateStyle'
import { FinishedRunPicker } from '@/features/whatif/FinishedRunPicker'
import { useWhatIfDrafts } from '@/features/whatif/whatifStore'
import { STAGE_META, type RiskLevel, type StageName } from '@/features/process-control/model'
import { DISCLAIMER_RECOMMENDATION } from '@/lib/disclaimers'
import { cn } from '@/lib/utils'

const MAX_CHANGES = [1, 2, 3, 4, 5, 6]

function CandidateCard({
  candidate,
  baseP,
  constraints,
  onSendToWhatIf,
}: {
  candidate: RecommendationCandidate
  baseP: number
  constraints?: Constraints
  onSendToWhatIf: () => void
}) {
  const c = candidate
  const extrapolated = c.flags.includes('EXTRAPOLATED')
  const unstable = c.flags.includes('UNSTABLE')
  const name = (p: string) => constraints?.parameters.find((s) => s.name === p)?.display_name ?? p
  // Cross-check against the registry's step limits: the guard stamp above is Role 1's report; a
  // step larger than max_step_change is shown instead of being hidden behind a tick (CCR-004 #7b).
  const oversized = c.changes.filter((ch) => {
    const limit = constraints?.parameters.find((s) => s.name === ch.parameter)?.max_step_change
    return limit != null && Math.abs(ch.delta) > limit + 1e-9
  })
  return (
    <article
      aria-label={`Option ${c.option_rank}: ${c.option_label}`}
      className="flex flex-col gap-3 rounded border border-border bg-panel p-4"
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">
          #{c.option_rank} {c.option_label}
        </h3>
        <div className="flex flex-wrap gap-1 text-[11px] font-semibold uppercase">
          <span
            className="rounded border border-risk-normal px-1 text-risk-normal"
            title="Every guard check passed"
          >
            {c.constraint_status === 'ALL_SATISFIED' ? 'Constraints satisfied' : c.constraint_status}
          </span>
          {extrapolated ? (
            <span className="rounded border border-risk-high px-1 text-risk-high">Extrapolated</span>
          ) : (
            <span className="rounded border border-border px-1 text-text-muted">
              {c.in_distribution ? 'In distribution' : 'Outside distribution'}
            </span>
          )}
          {unstable && <span className="rounded border border-risk-high px-1 text-risk-high">Unstable</span>}
        </div>
      </header>

      {oversized.length > 0 && (
        <p
          role="alert"
          aria-label="Step limit warning"
          className="rounded border border-risk-high px-2 py-1 text-xs text-risk-high"
        >
          Exceeds the registry step limit (max_step_change):{' '}
          {oversized
            .map((ch) => {
              const limit = constraints?.parameters.find((s) => s.name === ch.parameter)?.max_step_change
              return `${name(ch.parameter)} Δ ${ch.delta} > ${limit} ${unitLabel(ch.unit)}`.trim()
            })
            .join('; ')}
          . Treat this option with extra caution.
        </p>
      )}

      {extrapolated && (
        <p className="text-xs text-risk-high">
          Hypothesis for trial: outside the data the model was fitted on.
        </p>
      )}

      <section aria-label="Predicted failure probability" className="numeric text-sm">
        <span className="text-text-muted">Predicted P(fail)</span> {baseP.toFixed(2)} →{' '}
        <span className="font-semibold">{c.predicted_p_fail.toFixed(2)}</span>{' '}
        <span className={c.delta_p_fail < 0 ? 'text-risk-normal' : 'text-text-muted'}>
          (Δ {c.delta_p_fail > 0 ? '+' : ''}
          {c.delta_p_fail.toFixed(3)})
        </span>{' '}
        · {c.predicted_label}
      </section>

      <table className="numeric w-full text-xs" aria-label="Changes">
        <thead className="text-left text-text-muted">
          <tr>
            <th className="font-normal">Change</th>
            <th className="text-right font-normal">From</th>
            <th className="text-right font-normal">To</th>
          </tr>
        </thead>
        <tbody>
          {c.changes.map((ch) => (
            <tr key={ch.parameter}>
              <td>{name(ch.parameter)}</td>
              <td className="text-right">{ch.from_value}</td>
              <td className="text-right">
                {ch.to_value} {unitLabel(ch.unit)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="grid gap-2 text-xs md:grid-cols-2">
        <section aria-label="Guard checks">
          <h4 className="mb-1 text-[11px] font-semibold tracking-widest text-text-muted uppercase">
            Guard checks
          </h4>
          <ul>
            {c.guard_checks.map((g) => (
              <li key={g.check} className={g.passed ? 'text-text' : 'text-risk-high'} title={g.detail}>
                {g.passed ? '✓' : '✗'} {g.check.replace('_', ' ')}
                {g.detail ? <span className="text-text-muted"> — {g.detail}</span> : null}
              </li>
            ))}
          </ul>
        </section>
        <section aria-label="Stability and cost">
          <h4 className="mb-1 text-[11px] font-semibold tracking-widest text-text-muted uppercase">
            Stability and cost
          </h4>
          <p>
            Stability: {c.stability.flips}/{c.stability.trials} label flips{' '}
            {c.stability.stable ? '(stable)' : '(unstable)'}
          </p>
          <p>
            Cycle time: {c.cycle_time_delta_s > 0 ? '+' : ''}
            {c.cycle_time_delta_s.toFixed(1)} s ({c.cycle_time_delta_pct > 0 ? '+' : ''}
            {c.cycle_time_delta_pct.toFixed(1)} %)
          </p>
          <p>Change cost: {c.change_cost.toFixed(2)}</p>
        </section>
      </div>

      {c.stage_health_after.length > 0 && (
        <p className="text-xs text-text-muted">
          Stage risk after:{' '}
          {c.stage_health_after.map((s, i) => (
            <span key={s.stage}>
              {i > 0 && ' · '}
              {STAGE_META[s.stage as StageName]?.short ?? s.stage}{' '}
              <span className={RISK_TEXT[s.risk_level as RiskLevel]}>{s.risk_level}</span>
            </span>
          ))}
        </p>
      )}

      {c.rationale.length > 0 && (
        <ul className="list-disc pl-4 text-xs text-text-muted" aria-label="Rationale">
          {c.rationale.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={onSendToWhatIf}
        className="self-start rounded border border-state-active px-3 py-1 text-xs font-semibold text-state-active uppercase"
      >
        Send to What-If
      </button>
    </article>
  )
}

/**
 * Recommendations (roadmap R2-P7 task 5; Plan §14.6). Calls POST /recommend for a finished run and
 * shows Role 1's guarded, model-relative options with every guard result and the permanent
 * disclaimer. "Send to What-If" pre-fills the what-if draft with an option's changes.
 */
export function RecommendationsScreen() {
  const [params, setParams] = useSearchParams()
  const runId = params.get('run')
  const run = useRunState(runId)
  const constraints = useConstraints().data
  const recommend = useRecommend()
  const setOverrides = useWhatIfDrafts((s) => s.setOverrides)
  const navigate = useNavigate()
  const [locked, setLocked] = useState<string[]>([])
  const [maxChanges, setMaxChanges] = useState(3)
  const [slow, setSlow] = useState(false)
  const slowTimer = useRef<number | null>(null)

  const finished = run.data?.status === 'FINAL_RESULT'
  const response = recommend.data
  const actionable = constraints ? setpoints(constraints).filter((p) => p.actionable) : []
  const prediction = run.data?.prediction as { p_fail?: number; label?: string } | null

  const submit = () => {
    if (!runId) return
    setSlow(false)
    if (slowTimer.current) window.clearTimeout(slowTimer.current)
    slowTimer.current = window.setTimeout(() => setSlow(true), 1000)
    recommend.mutate(
      {
        run_id: runId,
        locked,
        max_changes: maxChanges,
        n_options: 3,
        objective: 'min_p_fail',
        enable_refinement: false,
      },
      {
        onSettled: () => {
          if (slowTimer.current) window.clearTimeout(slowTimer.current)
          setSlow(false)
        },
      },
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-sm font-semibold tracking-widest text-text-muted uppercase">Recommendations</h2>

      <p
        role="note"
        aria-label="Recommendation disclaimer"
        className="rounded border border-risk-high px-3 py-2 text-xs text-text"
      >
        {DISCLAIMER_RECOMMENDATION}
      </p>

      <section
        aria-label="Recommendation request"
        className="flex flex-col gap-3 rounded border border-border bg-panel p-4"
      >
        <div className="flex flex-wrap items-end gap-3">
          <FinishedRunPicker
            label="Run to improve"
            value={runId}
            onChange={(id) => {
              recommend.reset()
              setParams({ run: id })
            }}
          />
          <label className="flex flex-col gap-1 text-xs text-text-muted">
            Max changes per option
            <select
              value={maxChanges}
              onChange={(e) => setMaxChanges(Number(e.target.value))}
              className="rounded border border-border bg-panel px-2 py-1 text-sm text-text"
            >
              {MAX_CHANGES.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={!runId || !finished || recommend.isPending}
            onClick={submit}
            className="rounded border border-state-active px-3 py-1 text-xs font-semibold text-state-active uppercase disabled:opacity-40"
          >
            Find options
          </button>
        </div>
        {prediction?.p_fail != null && (
          <p className="numeric text-sm">
            <span className="text-text-muted">Current predicted P(fail)</span> {prediction.p_fail.toFixed(2)}{' '}
            {prediction.label}
          </p>
        )}
        {run.data && !finished && (
          <p role="alert" className="text-xs text-risk-high">
            This run is {run.data.status}. Recommendations need a run with a final result.
          </p>
        )}
        {actionable.length > 0 && (
          <fieldset className="rounded border border-border px-3 pt-1 pb-2">
            <legend className="px-1 text-xs text-text-muted">
              Lock parameters (never changed). Non-actionable parameters are always locked by the registry.
            </legend>
            <div className="grid gap-1 text-xs sm:grid-cols-2 md:grid-cols-3">
              {actionable.map((p) => (
                <label key={p.name} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={locked.includes(p.name)}
                    onChange={(e) =>
                      setLocked((cur) =>
                        e.target.checked ? [...cur, p.name] : cur.filter((n) => n !== p.name),
                      )
                    }
                  />
                  {p.display_name}
                </label>
              ))}
            </div>
          </fieldset>
        )}
      </section>

      {recommend.isPending && slow && (
        <p role="status" className="text-sm text-text-muted">
          Searching the constrained parameter space… (up to the server&apos;s time budget)
        </p>
      )}
      {recommend.isError && (
        <p role="alert" className="text-xs text-risk-critical">
          {recommend.error instanceof ApiClientError ? `${recommend.error.code}: ` : ''}
          {recommend.error.message}
          {recommend.error instanceof ApiClientError && recommend.error.hint
            ? ` — ${recommend.error.hint}`
            : ''}
        </p>
      )}

      {response && (
        <section aria-label="Recommendation options" className="flex flex-col gap-3">
          <p className="text-xs text-text-muted">
            {response.evaluated_count} candidates evaluated · model {response.model_version} ·{' '}
            {response.constraints_version}
            {Object.keys(response.rejected_counts).length > 0 &&
              ` · rejected: ${Object.entries(response.rejected_counts)
                .map(([k, v]) => `${k} ${v}`)
                .join(', ')}`}
          </p>
          {response.candidates.length === 0 ? (
            <p className="text-sm">
              No option found{response.empty_reason ? `: ${response.empty_reason}` : '.'}
            </p>
          ) : (
            <div className={cn('grid gap-3', response.candidates.length > 1 && 'xl:grid-cols-2')}>
              {response.candidates.map((c) => (
                <CandidateCard
                  key={c.option_rank}
                  candidate={c}
                  baseP={response.base_p_fail}
                  constraints={constraints}
                  onSendToWhatIf={() => {
                    if (!runId) return
                    setOverrides(
                      runId,
                      Object.fromEntries(c.changes.map((ch) => [ch.parameter, ch.to_value])),
                    )
                    navigate(`/what-if?base=${runId}`)
                  }}
                />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
