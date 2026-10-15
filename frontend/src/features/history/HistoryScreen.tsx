import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useRuns, type RunFilters } from '@/api/runs'
import { RISK_TEXT } from '@/components/pipeline/stateStyle'
import type { RiskLevel } from '@/features/process-control/model'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 20

function utc(ts: string): string {
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? ts : d.toISOString().slice(0, 16).replace('T', ' ')
}

function Select<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T | ''
  options: readonly (readonly [T | '', string])[]
  onChange: (v: T | '') => void
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T | '')}
        className="rounded border border-border bg-panel px-2 py-1 text-sm text-text"
      >
        {options.map(([v, text]) => (
          <option key={v || 'any'} value={v}>
            {text}
          </option>
        ))}
      </select>
    </label>
  )
}

/**
 * Run history (roadmap R2-P8, P0 part): filterable, paginated list of persisted runs and scenarios.
 * Every value comes from GET /simulation/runs; mock-backed rows are labelled as such.
 */
export function HistoryScreen() {
  const [filters, setFilters] = useState<RunFilters>({})
  const [page, setPage] = useState(0)
  const { data, isPending, isError, error, isFetching } = useRuns(filters, PAGE_SIZE, page * PAGE_SIZE)

  const update = (patch: Partial<RunFilters>) => {
    setFilters((f) => ({ ...f, ...patch }))
    setPage(0)
  }
  const total = data?.total ?? 0
  const rows = data?.rows ?? []
  const first = total === 0 ? 0 : page * PAGE_SIZE + 1
  const last = Math.min(total, (page + 1) * PAGE_SIZE)

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">History</h2>

      <form
        aria-label="Run filters"
        className="flex flex-wrap items-end gap-3 rounded border border-border bg-panel p-3"
        onSubmit={(e) => e.preventDefault()}
      >
        <label className="flex flex-col gap-1 text-xs text-text-muted">
          Machine
          <input
            value={filters.machine_id ?? ''}
            onChange={(e) => update({ machine_id: e.target.value.trim() || undefined })}
            placeholder="e.g. MC-03"
            className="numeric w-28 rounded border border-border bg-panel px-2 py-1 text-sm text-text"
          />
        </label>
        <Select
          label="Result"
          value={filters.label ?? ''}
          options={[
            ['', 'Any'],
            ['PASS', 'PASS'],
            ['FAIL', 'FAIL'],
          ]}
          onChange={(v) => update({ label: v || undefined })}
        />
        <Select
          label="Operational risk"
          value={filters.risk_level ?? ''}
          options={[
            ['', 'Any'],
            ['NORMAL', 'NORMAL'],
            ['LOW', 'LOW'],
            ['MEDIUM', 'MEDIUM'],
            ['HIGH', 'HIGH'],
            ['CRITICAL', 'CRITICAL'],
          ]}
          onChange={(v) => update({ risk_level: v || undefined })}
        />
        <Select
          label="Run type"
          value={filters.is_whatif === undefined ? '' : filters.is_whatif ? 'whatif' : 'original'}
          options={[
            ['', 'All'],
            ['original', 'Original runs'],
            ['whatif', 'What-if runs'],
          ]}
          onChange={(v) => update({ is_whatif: v === '' ? undefined : v === 'whatif' })}
        />
        <Select
          label="Inference"
          value={filters.inference_backend ?? ''}
          options={[
            ['', 'All'],
            ['real', 'Real model'],
            ['mock', 'Mock'],
          ]}
          onChange={(v) => update({ inference_backend: v || undefined })}
        />
        {isFetching && <span className="text-xs text-text-muted">Loading…</span>}
      </form>

      {isError ? (
        <p role="alert" className="text-sm text-risk-critical">
          Could not load runs: {error.message}
        </p>
      ) : isPending ? (
        <p className="text-sm text-text-muted">Loading runs…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-text-muted">No runs match these filters.</p>
      ) : (
        <div className="overflow-x-auto rounded border border-border">
          <table className="numeric w-full text-left text-xs">
            <thead className="bg-panel-raised text-text-muted">
              <tr>
                {[
                  'Created (UTC)',
                  'Run',
                  'Machine',
                  'Product',
                  'Lot',
                  'Status',
                  'Result',
                  'P(fail)',
                  'Op. risk',
                  'Model',
                  'Scenario',
                ].map((h) => (
                  <th key={h} scope="col" className="px-3 py-2 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.run_id} className="border-t border-border hover:bg-panel-raised">
                  <td className="px-3 py-1.5">{utc(r.created_at)}</td>
                  <td className="px-3 py-1.5">
                    <Link
                      to={`/history/${r.run_id}`}
                      className="text-state-active underline-offset-2 hover:underline"
                    >
                      {r.run_id.slice(0, 8)}
                    </Link>
                    {r.is_whatif && (
                      <span className="ml-1 rounded bg-panel-raised px-1 text-[10px] text-text-muted">
                        what-if
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-1.5">{r.machine_id}</td>
                  <td className="px-3 py-1.5">{r.product_id}</td>
                  <td className="px-3 py-1.5">{r.material_lot_id}</td>
                  <td className="px-3 py-1.5">{r.status}</td>
                  <td className="px-3 py-1.5">{r.label ?? '—'}</td>
                  <td className="px-3 py-1.5">
                    {r.p_fail === null || r.p_fail === undefined ? '—' : r.p_fail.toFixed(2)}
                  </td>
                  <td className={cn('px-3 py-1.5', r.risk_level ? RISK_TEXT[r.risk_level as RiskLevel] : '')}>
                    {r.risk_level ?? '—'}
                  </td>
                  <td className="px-3 py-1.5">
                    {r.model_version ?? '—'}
                    {r.inference_backend === 'mock' && (
                      <span className="ml-1 rounded bg-mock px-1 text-[10px] font-bold text-white">MOCK</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5">{r.scenario_label ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <nav aria-label="Pagination" className="flex items-center gap-3 text-xs text-text-muted">
        <button
          type="button"
          disabled={page === 0}
          onClick={() => setPage((p) => p - 1)}
          className="rounded border border-border px-2 py-1 disabled:opacity-40"
        >
          Previous
        </button>
        <span className="numeric">
          {first}–{last} of {total}
        </span>
        <button
          type="button"
          disabled={last >= total}
          onClick={() => setPage((p) => p + 1)}
          className="rounded border border-border px-2 py-1 disabled:opacity-40"
        >
          Next
        </button>
      </nav>
    </div>
  )
}
