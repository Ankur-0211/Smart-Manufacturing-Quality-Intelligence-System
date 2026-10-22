import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { RISK_TEXT } from '@/components/pipeline/stateStyle'
import { STAGE_META, type PredictionView, type StageName } from '@/features/process-control/model'
import { cn } from '@/lib/utils'

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="rounded border border-border bg-panel-raised p-3">
      <h4 className="mb-1 text-[11px] font-semibold tracking-widest text-text-muted uppercase">{title}</h4>
      {children}
    </section>
  )
}

function RiskOrigin({ mass }: { mass: { stage: StageName; share: number }[] }) {
  const sorted = [...mass].sort((a, b) => b.share - a.share)
  if (sorted.length === 0) return null
  return (
    <p className="mt-3 text-xs text-text-muted">
      Risk origin:{' '}
      {sorted.map((m, i) => (
        <span key={m.stage} className="numeric text-text">
          {i > 0 && ' | '}
          {STAGE_META[m.stage].short.toUpperCase()} {Math.round(m.share * 100)}%
        </span>
      ))}
    </p>
  )
}

/**
 * Quality result card (Plan §15.2, roadmap §7.13). Three DISTINCT concepts, never merged:
 * model-predicted failure probability, operational risk, and anomaly status.
 * Every number shown comes from the API payload passed in; nothing is computed or defaulted here.
 */
export function ResultCard({
  prediction,
  runId = null,
}: {
  prediction: PredictionView | null
  /** The finished run this result belongs to; enables the follow-up actions. */
  runId?: string | null
}) {
  if (!prediction) {
    return (
      <section aria-label="Quality result" className="rounded border border-border bg-panel p-4">
        <h3 className="text-xs font-semibold tracking-widest text-text-muted uppercase">Prediction</h3>
        <p className="mt-1 text-sm text-text-muted">Awaiting the quality inspection stage.</p>
      </section>
    )
  }
  const p = prediction
  const notReleasable = p.constraint_override_applied
  const anomaly = p.anomaly_global

  return (
    <section aria-label="Quality result" className="rounded border border-border bg-panel p-4">
      <header className="flex items-center justify-between">
        <h3 className="text-xs font-semibold tracking-widest text-text-muted uppercase">Quality result</h3>
        {p.is_mock && (
          <span className="rounded bg-mock px-2 py-0.5 text-[10px] font-bold text-white">MOCK OUTPUT</span>
        )}
      </header>

      {notReleasable && (
        <p
          role="alert"
          className="mt-2 rounded border border-blocked px-3 py-2 text-sm font-bold text-blocked"
        >
          NOT RELEASABLE — critical constraint breach was overridden. Model output shown for reference only.
        </p>
      )}

      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <Block title="Model-predicted failure probability">
          <p className="numeric text-2xl">
            {p.p_fail.toFixed(2)} <span className="text-xs text-text-muted">(calibrated)</span>
          </p>
          <p className={cn('text-sm font-semibold', notReleasable && 'text-text-muted')}>
            {notReleasable ? `Model label: ${p.label}` : `Prediction: ${p.label}`}
          </p>
          <p className="numeric mt-1 text-[11px] text-text-muted">
            threshold {p.threshold_used.toFixed(2)} · {p.model_version}
          </p>
        </Block>

        <Block title="Operational risk">
          <p className={cn('text-2xl font-semibold', RISK_TEXT[p.risk_level])}>{p.risk_level}</p>
          <ul className="mt-1 space-y-0.5 text-[11px] text-text-muted">
            {p.risk_drivers.map((d) => (
              <li key={`${d.source}-${d.detail}`}>
                {d.source}: {d.detail}
              </li>
            ))}
          </ul>
        </Block>

        <Block title="Anomaly status">
          {anomaly === null ? (
            <p className="text-sm text-text-muted">Not evaluated</p>
          ) : (
            <p
              className={cn(
                'text-sm font-semibold',
                anomaly.is_anomaly ? 'text-anomaly' : 'text-risk-normal',
              )}
            >
              {anomaly.is_anomaly ? '! Unusual process condition' : 'No global anomaly'}
            </p>
          )}
          {p.ood?.is_out_of_distribution && (
            <p className="mt-1 text-[11px] text-risk-medium">
              Outside training range on {p.ood.features_outside.length} feature(s): extrapolation
            </p>
          )}
        </Block>
      </div>

      <RiskOrigin mass={p.stage_risk_mass} />

      {p.caveats.length > 0 && (
        <ul aria-label="Caveats" className="mt-3 space-y-0.5 text-xs text-risk-medium">
          {p.caveats.map((c) => (
            <li key={c.code}>
              {c.code}: {c.message}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {runId ? (
          <>
            <Link
              to={`/explainability?run=${runId}`}
              className="rounded border border-border px-3 py-1 text-xs uppercase hover:bg-panel-raised"
            >
              Why this prediction?
            </Link>
            <Link
              to={`/recommendations?run=${runId}`}
              className="rounded border border-border px-3 py-1 text-xs uppercase hover:bg-panel-raised"
            >
              What should I change?
            </Link>
            <Link
              to={`/what-if?base=${runId}`}
              className="rounded border border-border px-3 py-1 text-xs uppercase hover:bg-panel-raised"
            >
              Try a what-if
            </Link>
            <Link
              to={`/history/${runId}`}
              className="rounded border border-border px-3 py-1 text-xs uppercase hover:bg-panel-raised"
            >
              Save scenario
            </Link>
          </>
        ) : null}
      </div>
    </section>
  )
}
