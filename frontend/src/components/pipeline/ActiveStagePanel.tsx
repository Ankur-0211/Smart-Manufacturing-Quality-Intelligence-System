import { STAGE_META, type IndicatorValue, type StageName } from '@/features/process-control/model'
import type { StageView } from '@/features/process-control/runReducer'
import { cn } from '@/lib/utils'

import { RISK_TEXT, STATE_GLYPH } from './stateStyle'

function show(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  return String(value)
}

function KeyValues({ title, values }: { title: string; values: Record<string, unknown> | null | undefined }) {
  const entries = Object.entries(values ?? {})
  if (entries.length === 0) return null
  return (
    <div>
      <h4 className="mt-3 mb-1 text-xs font-semibold text-text-muted uppercase">{title}</h4>
      <dl className="numeric grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 text-xs">
        {entries.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="truncate text-text-muted">{k}</dt>
            <dd className="text-right">{show(v)}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

/**
 * Details of the active (or selected) stage (Plan §15.2). Indicator values are shown verbatim with
 * their provenance; the UI never recomputes them (roadmap R2-P6 compatibility rule).
 */
export function ActiveStagePanel({ stage, view }: { stage: StageName | null; view: StageView | null }) {
  if (!stage || !view) {
    return (
      <section aria-label="Active stage" className="text-sm text-text-muted">
        No active stage. Stage inputs, upstream values and derived indicators appear here while a run
        executes.
      </section>
    )
  }
  const meta = STAGE_META[stage]
  const result = view.result
  const indicators = Object.entries(result?.indicators ?? {}) as [string, IndicatorValue][]

  return (
    <section aria-label={`Stage details: ${meta.long}`}>
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">
          {meta.long} <span className="numeric text-text-muted">{STATE_GLYPH[view.state]}</span>
        </h3>
        <span
          className={cn('text-xs font-semibold', result ? RISK_TEXT[result.risk_level] : 'text-text-muted')}
        >
          {view.state === 'COMPLETED' && result
            ? `health ${result.health_score.toFixed(2)} · ${result.risk_level}`
            : view.state}
        </span>
      </header>

      {view.state === 'ACTIVE' && <p className="mt-1 text-xs text-state-active">Module status: analysing…</p>}
      {view.anomaly && (
        <p className="mt-1 text-xs text-anomaly">
          ! Anomaly flagged{result?.anomaly.note ? ` — ${result.anomaly.note}` : ''} (unusual condition,
          independent of risk)
        </p>
      )}
      {result?.blocked && (
        <p role="alert" className="mt-1 text-xs text-blocked">
          [/] Blocked: {result.block_reason ?? 'critical constraint breach'}
          {view.overridden ? ' — override acknowledged' : ''}
        </p>
      )}

      <KeyValues title="Inputs in scope" values={view.inputsInScope ?? result?.inputs_used} />
      <KeyValues title="From upstream stages" values={result?.upstream_in} />

      {indicators.length > 0 && (
        <div>
          <h4 className="mt-3 mb-1 text-xs font-semibold text-text-muted uppercase">Derived indicators</h4>
          <dl className="numeric grid grid-cols-[minmax(0,1fr)_auto_auto] gap-x-3 text-xs">
            {indicators.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="truncate text-text-muted">{k}</dt>
                <dd className="text-right">{show(v)}</dd>
                <dd className="text-[10px] text-text-muted" title="Value provenance">
                  {result?.indicator_provenance[k] ?? 'unknown'}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {result && result.notes.length > 0 && (
        <ul className="mt-3 list-disc pl-4 text-xs">
          {result.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}

      {result && result.constraint_breaches.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs" aria-label="Constraint breaches">
          {result.constraint_breaches.map((b) => (
            <li
              key={b.rule_id}
              className={b.severity === 'CRITICAL' ? 'text-risk-critical' : 'text-risk-medium'}
            >
              <span className="font-semibold">{b.severity}</span> {b.rule_id}: {b.message}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
