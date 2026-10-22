import { useRuns } from '@/api/runs'

/**
 * Picks a finished run (FINAL_RESULT) as the base for a what-if or a recommendation request.
 * Lists the 50 most recent runs; older ones can be opened from History.
 */
export function FinishedRunPicker({
  value,
  onChange,
  label = 'Base run',
}: {
  value: string | null
  onChange: (runId: string) => void
  label?: string
}) {
  const runs = useRuns({}, 50, 0)
  const finished = (runs.data?.rows ?? []).filter((r) => r.status === 'FINAL_RESULT')
  return (
    <label className="flex min-w-72 flex-col gap-1 text-xs text-text-muted">
      {label}
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-border bg-panel px-2 py-1 text-sm text-text"
      >
        <option value="" disabled>
          {runs.isLoading ? 'Loading…' : finished.length ? 'Select a finished run' : 'No finished runs yet'}
        </option>
        {value && !finished.some((r) => r.run_id === value) && (
          <option value={value}>{value.slice(0, 8)}</option>
        )}
        {finished.map((r) => (
          <option key={r.run_id} value={r.run_id}>
            {r.run_id.slice(0, 8)} · {r.machine_id} / {r.material_lot_id} · {r.label ?? '—'}{' '}
            {r.p_fail != null ? `P ${r.p_fail.toFixed(2)}` : ''}
            {r.scenario_label ? ` · ${r.scenario_label}` : ''}
            {r.is_whatif ? ' · what-if' : ''}
          </option>
        ))}
      </select>
    </label>
  )
}
