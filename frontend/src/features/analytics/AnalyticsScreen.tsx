import { useState } from 'react'

import {
  DEFAULT_ANALYTICS_FILTERS,
  useAnalyticsSummary,
  useByMachine,
  useByMaterial,
  useByParameter,
  useSpc,
  type AnalyticsFilters,
  type Outcome,
} from '@/api/analytics'
import { setpoints, useConstraints } from '@/api/constraints'
import { useMachines } from '@/api/reference'
import { OutcomeBars, SeriesLine } from '@/components/charts/lazy'
import { unitLabel } from '@/components/params/recipeValidation'
import { RISK_TEXT } from '@/components/pipeline/stateStyle'
import { RISK_LEVELS, STAGE_META, type StageName } from '@/features/process-control/model'
import { cn } from '@/lib/utils'

/** Below this many scored runs a share is shown with a caution, not hidden. */
const FEW_RUNS = 10

const EXCLUSION_TEXT: Record<string, [string, string]> = {
  whatif: ['what-if scenario', 'what-if scenarios'],
  mock: ['run scored by MOCK intelligence', 'runs scored by MOCK intelligence'],
  unfinished: ['run without a final result', 'runs without a final result'],
}

function exclusionText(key: string, n: number): string {
  const [one, many] = EXCLUSION_TEXT[key] ?? [key, key]
  return `${n} ${n === 1 ? one : many}`
}

function pct(rate: number | null | undefined): string {
  return rate == null ? '—' : `${Math.round(rate * 100)} %`
}

function Panel({
  title,
  children,
  actions,
}: {
  title: string
  children: React.ReactNode
  actions?: React.ReactNode
}) {
  return (
    <section aria-label={title} className="flex flex-col gap-2 rounded border border-border bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold tracking-widest text-text-muted uppercase">{title}</h3>
        {actions}
      </div>
      {children}
    </section>
  )
}

/** A table of grouped outcomes: the numbers behind a bar chart. */
function OutcomeTable({
  label,
  keyHeader,
  rows,
}: {
  label: string
  keyHeader: string
  rows: (Outcome & { key: string })[]
}) {
  return (
    <table className="numeric w-full text-xs" aria-label={label}>
      <thead className="text-left text-text-muted">
        <tr>
          <th className="font-normal">{keyHeader}</th>
          <th className="text-right font-normal">Runs</th>
          <th className="text-right font-normal">Predicted FAIL</th>
          <th className="text-right font-normal">Share</th>
          <th className="text-right font-normal">Mean P(fail)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.key}>
            <td>{r.key}</td>
            <td className="text-right">{r.runs}</td>
            <td className="text-right">
              {r.predicted_fail}/{r.with_prediction}
            </td>
            <td className="text-right">{pct(r.predicted_fail_rate)}</td>
            <td className="text-right">{r.mean_p_fail == null ? '—' : r.mean_p_fail.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Empty() {
  return <p className="text-sm text-text-muted">No stored runs match these filters.</p>
}

/**
 * Analytics (roadmap R2-P8 tasks 3-5, P1). Every number is an SQL aggregation over stored runs
 * from /analytics/*. "Predicted FAIL share" is the model's label share, not an observed defect
 * rate. The active exclusions and how many runs each removed are always stated.
 */
export function AnalyticsScreen() {
  const [filters, setFilters] = useState<AnalyticsFilters>(DEFAULT_ANALYTICS_FILTERS)
  const [materialGroup, setMaterialGroup] = useState<'lot' | 'resin_grade'>('lot')
  const constraints = useConstraints().data
  const params = constraints ? setpoints(constraints) : []
  const [parameter, setParameter] = useState('melt_temp_c')
  const [buckets, setBuckets] = useState(5)
  const machines = useMachines().data ?? []
  const [spcMachine, setSpcMachine] = useState('')

  const summary = useAnalyticsSummary(filters)
  const byMachine = useByMachine(filters)
  const byMaterial = useByMaterial(filters, materialGroup)
  const byParameter = useByParameter(filters, parameter, buckets)
  // Default to the first machine that has runs in scope, so the series is not empty by accident.
  const spcMachineId = spcMachine || byMachine.data?.rows[0]?.key || machines[0]?.machine_id || ''
  const spc = useSpc(filters, spcMachineId, parameter)

  const s = summary.data
  const spec = params.find((p) => p.name === parameter)
  const unit = unitLabel(spec?.unit)
  const set = (patch: Partial<AnalyticsFilters>) => setFilters((f) => ({ ...f, ...patch }))
  const excluded = Object.entries(s?.excluded ?? {})

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-sm font-semibold tracking-widest text-text-muted uppercase">Analytics</h2>

      <section
        aria-label="Analytics filters"
        className="flex flex-col gap-2 rounded border border-border bg-panel px-4 py-3"
      >
        <div className="flex flex-wrap items-end gap-4 text-xs">
          {(
            [
              ['includeWhatif', 'Include what-if scenarios'],
              ['includeMock', 'Include MOCK-scored runs'],
              ['includeUnfinished', 'Include runs without a final result'],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={filters[key]}
                onChange={(e) => set({ [key]: e.target.checked })}
              />
              {label}
            </label>
          ))}
          <label className="flex flex-col gap-1 text-text-muted">
            From
            <input
              type="date"
              value={filters.from}
              onChange={(e) => set({ from: e.target.value })}
              className="rounded border border-border bg-panel px-2 py-1 text-text"
            />
          </label>
          <label className="flex flex-col gap-1 text-text-muted">
            To
            <input
              type="date"
              value={filters.to}
              onChange={(e) => set({ to: e.target.value })}
              className="rounded border border-border bg-panel px-2 py-1 text-text"
            />
          </label>
        </div>
        <p className="text-xs text-text-muted" aria-label="Exclusions applied">
          {!s
            ? 'Loading…'
            : excluded.length === 0
              ? 'No exclusions: every stored run in the date range is counted.'
              : `Excluded: ${excluded.map(([k, n]) => exclusionText(k, n)).join(', ')}.`}{' '}
          Shares are the model&apos;s predicted FAIL labels, not observed defects.
        </p>
      </section>

      {summary.isError && (
        <p role="alert" className="text-sm text-risk-critical">
          Analytics unavailable: {summary.error.message}
        </p>
      )}

      {s && (
        <section aria-label="Totals" className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {[
            ['Runs', String(s.runs)],
            ['With a prediction', String(s.with_prediction)],
            ['Predicted FAIL share', `${pct(s.predicted_fail_rate)} (${s.predicted_fail})`],
            ['Mean predicted P(fail)', s.mean_p_fail == null ? '—' : s.mean_p_fail.toFixed(2)],
            ['NOT RELEASABLE (overridden critical)', String(s.not_releasable)],
          ].map(([label, value]) => (
            <div key={label} className="rounded border border-border bg-panel px-3 py-2">
              <p className="text-[11px] text-text-muted">{label}</p>
              <p className="numeric text-lg">{value}</p>
            </div>
          ))}
        </section>
      )}
      {s && s.with_prediction > 0 && s.with_prediction < FEW_RUNS && (
        <p role="note" className="text-xs text-anomaly">
          Only {s.with_prediction} scored run{s.with_prediction > 1 ? 's' : ''}: treat the shares below as
          anecdotal.
        </p>
      )}

      {s && s.runs === 0 ? (
        <Empty />
      ) : (
        s && (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              <Panel title="Runs over time">
                <SeriesLine points={s.runs_over_time.map((d) => ({ x: d.day, y: d.runs }))} name="runs" />
                <OutcomeTable
                  label="Runs per day"
                  keyHeader="Day"
                  rows={s.runs_over_time.map((d) => ({ ...d, key: d.day }))}
                />
              </Panel>

              <Panel title="Operational risk and stages">
                <p className="numeric text-xs" aria-label="Operational risk distribution">
                  {RISK_LEVELS.filter((l) => s.risk_levels[l]).map((l) => (
                    <span key={l} className={cn('mr-3', RISK_TEXT[l])}>
                      {l} {s.risk_levels[l]}
                    </span>
                  ))}
                </p>
                <table className="numeric w-full text-xs" aria-label="Stage risk frequency">
                  <thead className="text-left text-text-muted">
                    <tr>
                      <th className="font-normal">Stage</th>
                      {RISK_LEVELS.map((l) => (
                        <th key={l} className="text-right font-normal">
                          {l}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {s.stage_risk_frequency.map((row) => (
                      <tr key={row.stage}>
                        <td>{STAGE_META[row.stage as StageName]?.long ?? row.stage}</td>
                        {RISK_LEVELS.map((l) => {
                          const n = row.counts[l] ?? 0
                          return (
                            <td
                              key={l}
                              className={cn('text-right', n ? RISK_TEXT[l] : 'text-text-muted')}
                              style={{
                                background: n
                                  ? `color-mix(in srgb, var(--color-risk-${l.toLowerCase()}) ${Math.round((n / row.total) * 35)}%, transparent)`
                                  : undefined,
                              }}
                            >
                              {n}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>

              <Panel title="By machine">
                {byMachine.data && byMachine.data.rows.length > 0 ? (
                  <>
                    <OutcomeBars
                      bars={byMachine.data.rows.map((r) => ({
                        label: r.key,
                        rate: r.predicted_fail_rate,
                        runs: r.runs,
                      }))}
                    />
                    <OutcomeTable label="By machine" keyHeader="Machine" rows={byMachine.data.rows} />
                  </>
                ) : (
                  <Empty />
                )}
              </Panel>

              <Panel
                title="By material"
                actions={
                  <div role="group" aria-label="Material grouping" className="flex gap-1">
                    {(
                      [
                        ['lot', 'Lot'],
                        ['resin_grade', 'Resin grade'],
                      ] as const
                    ).map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        aria-pressed={materialGroup === value}
                        onClick={() => setMaterialGroup(value)}
                        className={cn(
                          'rounded border px-2 py-0.5 text-xs',
                          materialGroup === value
                            ? 'border-state-active text-state-active'
                            : 'border-border text-text',
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                }
              >
                {byMaterial.data && byMaterial.data.rows.length > 0 ? (
                  <>
                    <OutcomeBars
                      bars={byMaterial.data.rows.map((r) => ({
                        label: r.key,
                        rate: r.predicted_fail_rate,
                        runs: r.runs,
                      }))}
                    />
                    <OutcomeTable
                      label="By material"
                      keyHeader={materialGroup === 'lot' ? 'Lot' : 'Resin grade'}
                      rows={byMaterial.data.rows}
                    />
                  </>
                ) : (
                  <Empty />
                )}
              </Panel>
            </div>

            <Panel
              title="By parameter"
              actions={
                <div className="flex flex-wrap items-end gap-2 text-xs">
                  <label className="flex flex-col gap-1 text-text-muted">
                    Parameter
                    <select
                      value={parameter}
                      onChange={(e) => setParameter(e.target.value)}
                      className="rounded border border-border bg-panel px-2 py-1 text-sm text-text"
                    >
                      {params.map((p) => (
                        <option key={p.name} value={p.name}>
                          {p.display_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-text-muted">
                    Buckets
                    <select
                      value={buckets}
                      onChange={(e) => setBuckets(Number(e.target.value))}
                      className="rounded border border-border bg-panel px-2 py-1 text-sm text-text"
                    >
                      {[3, 4, 5, 6, 8, 10].map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              }
            >
              {byParameter.isError && (
                <p role="alert" className="text-xs text-risk-critical">
                  {byParameter.error.message}
                </p>
              )}
              {byParameter.data && (
                <>
                  <p className="text-xs text-text-muted">
                    Equal-width buckets over the registry window {byParameter.data.window.min}–
                    {byParameter.data.window.max}
                    {unit ? ` ${unit}` : ''} ({constraints?.version}).
                  </p>
                  <div className="grid gap-4 lg:grid-cols-2">
                    <OutcomeBars
                      bars={byParameter.data.rows.map((r) => ({
                        label: `${r.lo}–${r.hi}`,
                        rate: r.predicted_fail_rate,
                        runs: r.runs,
                      }))}
                    />
                    <OutcomeTable
                      label="By parameter"
                      keyHeader={`${spec?.display_name ?? parameter}${unit ? ` (${unit})` : ''}`}
                      rows={byParameter.data.rows.map((r) => ({ ...r, key: `${r.lo}–${r.hi}` }))}
                    />
                  </div>
                </>
              )}
            </Panel>
          </>
        )
      )}

      <Panel
        title="SPC drift"
        actions={
          <label className="flex flex-col gap-1 text-xs text-text-muted">
            Machine
            <select
              value={spcMachineId}
              onChange={(e) => setSpcMachine(e.target.value)}
              className="rounded border border-border bg-panel px-2 py-1 text-sm text-text"
            >
              {machines.map((m) => (
                <option key={m.machine_id} value={m.machine_id}>
                  {m.machine_id}
                </option>
              ))}
            </select>
          </label>
        }
      >
        <p className="text-xs text-text-muted">
          {spec?.display_name ?? parameter} on {spcMachineId || '—'}, oldest first (parameter chosen under By
          parameter).
        </p>
        {spc.data && (
          <>
            {!spc.data.spc.available && (
              <p role="note" aria-label="SPC status" className="text-xs text-anomaly">
                {spc.data.spc.reason}
              </p>
            )}
            {spc.data.series.length > 0 ? (
              <>
                <SeriesLine
                  points={spc.data.series.map((p) => ({
                    x: p.created_at.slice(0, 16).replace('T', ' '),
                    y: p.value,
                  }))}
                  name={spec?.display_name ?? parameter}
                />
                <p className="numeric text-xs" aria-label="SPC series summary">
                  {spc.data.series.length} runs · min {Math.min(...spc.data.series.map((p) => p.value))} · max{' '}
                  {Math.max(...spc.data.series.map((p) => p.value))}
                  {unit ? ` ${unit}` : ''}
                </p>
              </>
            ) : (
              <Empty />
            )}
          </>
        )}
      </Panel>
    </div>
  )
}
