import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useRunState, useSetLabel, type SimulationState } from '@/api/runs'
import { ActiveStagePanel } from '@/components/pipeline/ActiveStagePanel'
import { EventTimeline } from '@/components/pipeline/EventTimeline'
import { StagePipeline } from '@/components/pipeline/StagePipeline'
import { ResultCard } from '@/components/result/ResultCard'
import type { SimulationSnapshot, StageName } from '@/features/process-control/model'
import { initialRunState, runReducer } from '@/features/process-control/runReducer'

/** The API's SimulationState carries stage results / prediction as JSON objects matching the
 * provisional view types (roadmap §7.9, §7.12). */
function toSnapshot(state: SimulationState): SimulationSnapshot {
  return state as unknown as SimulationSnapshot
}

function LabelEditor({ runId, current }: { runId: string; current: string | null | undefined }) {
  const [value, setValue] = useState(current ?? '')
  const mutation = useSetLabel(runId)
  return (
    <form
      aria-label="Scenario label"
      className="flex items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        mutation.mutate(value.trim() || null)
      }}
    >
      <label className="flex flex-col gap-1 text-xs text-text-muted">
        Scenario label
        <input
          value={value}
          maxLength={200}
          onChange={(e) => setValue(e.target.value)}
          className="w-64 rounded border border-border bg-panel px-2 py-1 text-sm text-text"
        />
      </label>
      <button
        type="submit"
        disabled={mutation.isPending}
        className="rounded border border-state-active px-3 py-1 text-xs text-state-active uppercase disabled:opacity-40"
      >
        Save scenario
      </button>
      {mutation.isSuccess && <span className="text-xs text-risk-normal">Saved</span>}
      {mutation.isError && (
        <span role="alert" className="text-xs text-risk-critical">
          {mutation.error.message}
        </span>
      )}
    </form>
  )
}

/** Read-only view of one persisted run (roadmap R2-P8): same components as Process Control. */
export function RunDetailScreen() {
  const { runId = '' } = useParams()
  const { data, isPending, isError, error } = useRunState(runId)
  const [selected, setSelected] = useState<StageName | null>(null)
  const view = useMemo(
    () => (data ? runReducer(initialRunState(runId), { kind: 'hydrate', snapshot: toSnapshot(data) }) : null),
    [data, runId],
  )

  if (isPending) return <p className="text-sm text-text-muted">Loading run…</p>
  if (isError || !data || !view) {
    return (
      <p role="alert" className="text-sm text-risk-critical">
        Could not load run {runId.slice(0, 8)}: {error?.message ?? 'not found'}
      </p>
    )
  }

  const ctx = data.context as {
    machine?: { machine_id?: string }
    product?: { product_id?: string }
    material_lot?: { material_lot_id?: string }
  }
  const focus = selected ?? (view.stages.QUALITY_INSPECTION.state === 'COMPLETED' ? null : view.activeStage)

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">
            Run <span className="numeric">{runId.slice(0, 8)}</span>
          </h2>
          <p className="numeric text-xs text-text-muted">
            {ctx.machine?.machine_id} · {ctx.product?.product_id} · {ctx.material_lot?.material_lot_id} ·
            status {data.status}
            {data.is_whatif && data.parent_run_id && (
              <>
                {' '}
                · what-if of{' '}
                <Link to={`/history/${data.parent_run_id}`} className="text-state-active">
                  {data.parent_run_id.slice(0, 8)}
                </Link>
              </>
            )}
          </p>
        </div>
        <div className="flex gap-3 text-xs">
          <Link to="/history" className="text-text-muted hover:text-text">
            ← History
          </Link>
          <Link to={`/?run=${runId}`} className="text-state-active">
            Open in Process Control
          </Link>
        </div>
      </header>

      <LabelEditor key={data.scenario_label ?? ''} runId={runId} current={data.scenario_label} />

      <section aria-label="Stage pipeline" className="rounded border border-border bg-panel px-4 py-3">
        <StagePipeline
          stages={view.stages}
          prediction={view.prediction}
          selectedStage={selected}
          onSelectStage={(s) => setSelected((cur) => (cur === s ? null : s))}
        />
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <ResultCard prediction={view.prediction} />
          <div className="rounded border border-border bg-panel p-4">
            <ActiveStagePanel stage={focus} view={focus ? view.stages[focus] : null} />
          </div>
        </div>
        <div className="rounded border border-border bg-panel p-4">
          <EventTimeline entries={view.timeline} />
        </div>
      </div>
    </div>
  )
}
