import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import type { Schemas } from '@/api/client'
import { useExplanation } from '@/api/predict'
import { useRunState } from '@/api/runs'
import { ShapBars, type ShapBar } from '@/components/charts/ShapBars'
import { StageRiskDonut } from '@/components/charts/StageRiskDonut'
import { STAGE_COLOURS } from '@/components/charts/stageColours'
import { RISK_TEXT } from '@/components/pipeline/stateStyle'
import { FinishedRunPicker } from '@/features/whatif/FinishedRunPicker'
import { STAGE_META, type RiskLevel, type StageName } from '@/features/process-control/model'
import { DISCLAIMER_SHAP } from '@/lib/disclaimers'
import { cn } from '@/lib/utils'

type Explanation = Schemas['LocalExplanation']

interface StoredPrediction {
  prediction_id?: string
  p_fail?: number
  label?: string
  risk_level?: string
  model_version?: string
  threshold_used?: number
  caveats?: { code: string; message: string; features?: string[] }[]
  explanation?: Explanation | null
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="rounded border border-border bg-panel p-4">
      <h3 className="mb-2 text-xs font-semibold tracking-widest text-text-muted uppercase">{title}</h3>
      {children}
    </section>
  )
}

/**
 * Explainability (roadmap R2-P7 task 6; Plan §11). Shows the stored local explanation of a finished
 * run's prediction: signed attributions (per feature or grouped), stage risk mass, caveats, and the
 * permanent DISCLAIMER_SHAP. Everything shown comes from the API payload.
 */
export function ExplainabilityScreen() {
  const [params, setParams] = useSearchParams()
  const runId = params.get('run')
  const run = useRunState(runId)
  const prediction = (run.data?.prediction ?? null) as StoredPrediction | null
  const stored = prediction?.explanation ?? null
  // Older predictions without a stored explanation are recomputed by the server when possible.
  const fetched = useExplanation(prediction && !stored ? (prediction.prediction_id ?? null) : null)
  const explanation = stored ?? fetched.data ?? null
  const [grouped, setGrouped] = useState(false)

  const attributions = explanation?.attributions ?? []
  const groups = explanation?.grouped_attributions ?? []
  const mass = (explanation?.stage_risk_mass ?? []) as { stage: StageName; share: number }[]
  const bars: ShapBar[] = grouped
    ? groups.map((g) => ({ key: g.group, label: g.group, value: g.shap_sum }))
    : attributions.map((a) => ({ key: a.feature, label: a.display_name, value: a.shap_value }))
  const caveats = prediction?.caveats ?? []
  const showBanner = Boolean(explanation?.show_caveat_banner) || caveats.length > 0

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-sm font-semibold tracking-widest text-text-muted uppercase">Explainability</h2>

      <section
        aria-label="Explained run"
        className="flex flex-wrap items-end justify-between gap-3 rounded border border-border bg-panel px-4 py-3"
      >
        <FinishedRunPicker label="Run" value={runId} onChange={(id) => setParams({ run: id })} />
        {prediction?.p_fail != null && (
          <div className="numeric flex flex-wrap gap-4 text-sm">
            <span>
              <span className="text-text-muted">Predicted P(fail)</span> {prediction.p_fail.toFixed(2)}{' '}
              {prediction.label}
              {prediction.threshold_used != null && (
                <span className="text-xs text-text-muted"> (threshold {prediction.threshold_used})</span>
              )}
            </span>
            {prediction.risk_level && (
              <span>
                <span className="text-text-muted">Operational risk</span>{' '}
                <span className={RISK_TEXT[prediction.risk_level as RiskLevel]}>{prediction.risk_level}</span>
              </span>
            )}
            {prediction.model_version && <span className="text-text-muted">{prediction.model_version}</span>}
            <Link to={`/?run=${runId}`} className="text-state-active">
              Open run
            </Link>
          </div>
        )}
      </section>

      {!runId && <p className="text-sm text-text-muted">Choose a finished run to explain its prediction.</p>}
      {runId && run.data && !prediction && (
        <p role="alert" className="text-sm text-risk-high">
          This run has no prediction yet ({run.data.status}).
        </p>
      )}
      {prediction && !explanation && fetched.isPending && (
        <p className="text-sm text-text-muted">Loading the explanation…</p>
      )}
      {prediction && !explanation && fetched.isError && (
        <p role="alert" className="text-sm text-risk-critical">
          No explanation available: {fetched.error.message}
        </p>
      )}

      {explanation && (
        <>
          {showBanner && (
            <section
              role="alert"
              aria-label="Explanation caveats"
              className="rounded border border-anomaly px-3 py-2 text-xs"
            >
              <p className="font-semibold text-anomaly">Read these attributions with care:</p>
              {caveats.length > 0 ? (
                <ul className="mt-1 list-disc pl-4">
                  {caveats.map((c) => (
                    <li key={c.code}>
                      {c.code}: {c.message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>The model flagged this input as unusual (out of distribution or anomalous).</p>
              )}
            </section>
          )}

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <Panel title="Feature attributions">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-xs text-text-muted">
                    Right (red) pushes toward FAIL, left (green) toward PASS. Top {attributions.length} by
                    size.
                  </p>
                  <div role="group" aria-label="Attribution view" className="flex gap-1">
                    {[
                      { label: 'Features', value: false },
                      { label: 'Groups', value: true },
                    ].map((o) => (
                      <button
                        key={o.label}
                        type="button"
                        aria-pressed={grouped === o.value}
                        onClick={() => setGrouped(o.value)}
                        disabled={o.value && groups.length === 0}
                        className={cn(
                          'rounded border px-2 py-0.5 text-xs disabled:opacity-40',
                          grouped === o.value
                            ? 'border-state-active text-state-active'
                            : 'border-border text-text',
                        )}
                      >
                        {o.label}
                      </button>
                    ))}
                  </div>
                </div>
                {bars.length > 0 ? (
                  <ShapBars bars={bars} />
                ) : (
                  <p className="text-sm text-text-muted">No attributions.</p>
                )}
                <table
                  className="numeric mt-3 w-full text-xs"
                  aria-label={grouped ? 'Grouped attributions' : 'Attributions'}
                >
                  <thead className="text-left text-text-muted">
                    {grouped ? (
                      <tr>
                        <th className="font-normal">Group</th>
                        <th className="text-right font-normal">SHAP sum</th>
                      </tr>
                    ) : (
                      <tr>
                        <th className="font-normal">Feature</th>
                        <th className="text-right font-normal">Value</th>
                        <th className="text-right font-normal">SHAP</th>
                        <th className="text-right font-normal">Direction</th>
                        <th className="text-right font-normal">Stage</th>
                      </tr>
                    )}
                  </thead>
                  <tbody>
                    {grouped
                      ? groups.map((g) => (
                          <tr key={g.group}>
                            <td>{g.group}</td>
                            <td className="text-right">{g.shap_sum.toFixed(3)}</td>
                          </tr>
                        ))
                      : attributions.map((a) => (
                          <tr key={a.feature}>
                            <td>{a.display_name}</td>
                            <td className="text-right">{a.value ?? '—'}</td>
                            <td
                              className={cn(
                                'text-right',
                                a.shap_value >= 0 ? 'text-risk-critical' : 'text-risk-normal',
                              )}
                            >
                              {a.shap_value > 0 ? '+' : ''}
                              {a.shap_value.toFixed(3)}
                            </td>
                            <td className="text-right">
                              {a.direction === 'toward_fail' ? 'toward FAIL' : 'toward PASS'}
                            </td>
                            <td className="text-right">
                              {STAGE_META[a.stage as StageName]?.short ?? a.stage}
                            </td>
                          </tr>
                        ))}
                  </tbody>
                </table>
              </Panel>
            </div>

            <Panel title="Stage risk mass">
              {mass.length > 0 ? (
                <div className="flex flex-col items-center gap-2">
                  <StageRiskDonut shares={mass} />
                  <ul className="numeric w-full text-xs" aria-label="Stage shares">
                    {[...mass]
                      .sort((a, b) => b.share - a.share)
                      .map((m) => (
                        <li key={m.stage} className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-1">
                            <span
                              aria-hidden="true"
                              className="inline-block h-2 w-2 rounded-full"
                              style={{ background: STAGE_COLOURS[m.stage] }}
                            />
                            {STAGE_META[m.stage]?.long ?? m.stage}
                          </span>
                          <span>{Math.round(m.share * 100)} %</span>
                        </li>
                      ))}
                  </ul>
                </div>
              ) : (
                <p className="text-sm text-text-muted">No stage risk mass reported.</p>
              )}
            </Panel>
          </div>

          <p className="text-xs text-text-muted">
            Method: {explanation.method} on the model&apos;s {explanation.output_space} margin (base value{' '}
            {explanation.base_value.toFixed(3)}, background {explanation.background_version}). The margin is
            before calibration, so attribution sizes are not probability changes; their signs carry over to
            the calibrated P(fail).
          </p>
        </>
      )}

      <p
        role="note"
        aria-label="SHAP disclaimer"
        className="rounded border border-border px-3 py-2 text-xs text-text"
      >
        {DISCLAIMER_SHAP}
      </p>
    </div>
  )
}
