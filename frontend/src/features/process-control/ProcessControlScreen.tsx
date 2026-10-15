import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiClientError } from '@/api/client'
import { useRunCommand, useRunState, type OverrideRequest, type RunCommand } from '@/api/runs'
import { ActiveStagePanel } from '@/components/pipeline/ActiveStagePanel'
import { EventTimeline } from '@/components/pipeline/EventTimeline'
import { RunControls } from '@/components/pipeline/RunControls'
import { StagePipeline } from '@/components/pipeline/StagePipeline'
import { ResultCard } from '@/components/result/ResultCard'

import { STAGE_META, TERMINAL_STATUSES, type RunMode, type SpeedFactor, type StageName } from './model'
import { useRunEvents, type Transport } from './useRunEvents'

/** Only S1-S5 can block (roadmap §9.5.1), so a blocked stage is always overridable. */
function asOverridable(stage: StageName): OverrideRequest['stage'] {
  if (stage === 'QUALITY_INSPECTION') throw new Error('QUALITY_INSPECTION cannot be blocked')
  return stage
}

const TRANSPORT_LABEL: Record<Transport, string> = {
  idle: 'no run',
  connecting: 'connecting…',
  sse: 'live (SSE)',
  polling: 'live (polling)',
  closed: 'finished',
}

function CommandError({ error }: { error: Error }) {
  const api = error instanceof ApiClientError ? error : null
  return (
    <p role="alert" className="rounded border border-risk-critical px-3 py-2 text-xs text-risk-critical">
      {api ? `${api.code}: ` : ''}
      {error.message}
      {api?.hint ? ` — ${api.hint}` : ''}
      {api?.requestId ? <span className="text-text-muted"> (request {api.requestId})</span> : null}
    </p>
  )
}

function OverridePanel({
  stage,
  pending,
  onOverride,
}: {
  stage: StageName
  pending: boolean
  onOverride: (acknowledgement: string) => void
}) {
  const [ack, setAck] = useState('')
  return (
    <section
      aria-label="Blocked stage override"
      className="rounded border border-blocked bg-panel px-4 py-3 text-sm"
    >
      <p className="font-semibold text-blocked">
        [/] {STAGE_META[stage].long} is BLOCKED by a critical constraint breach.
      </p>
      <p className="mt-1 text-xs text-text-muted">
        Continuing records an override. The final result will be shown as NOT RELEASABLE.
      </p>
      <form
        className="mt-2 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          onOverride(ack.trim())
        }}
      >
        <label className="flex flex-col gap-1 text-xs text-text-muted">
          Acknowledgement (required)
          <input
            value={ack}
            onChange={(e) => setAck(e.target.value)}
            className="w-80 rounded border border-border bg-panel px-2 py-1 text-sm text-text"
          />
        </label>
        <button
          type="submit"
          disabled={pending || ack.trim().length < 3}
          className="rounded border border-blocked px-3 py-1 text-xs font-semibold text-blocked uppercase disabled:opacity-40"
        >
          Override and continue
        </button>
      </form>
    </section>
  )
}

/**
 * Process Control workspace (Plan §15.2; roadmap R2-P6).
 *
 * Opens an existing run with `?run=<id>` (from History) and follows it live over SSE, with polling
 * fallback. Controls call the real run-command endpoints. Creating runs (machine/product/lot
 * selection and the recipe sliders) needs recipe validation from the shared contracts and the
 * constraint registry, so it is not available yet. Nothing on this screen is pre-filled.
 */
export function ProcessControlScreen() {
  const [params] = useSearchParams()
  const runId = params.get('run')
  const { state, transport } = useRunEvents(runId)
  const runQuery = useRunState(runId)
  const command = useRunCommand(runId)
  const [modeChoice, setModeChoice] = useState<RunMode | null>(null)
  const [speedChoice, setSpeedChoice] = useState<SpeedFactor | null>(null)
  const [selected, setSelected] = useState<StageName | null>(null)

  const run = runQuery.data
  const mode: RunMode = modeChoice ?? (run?.mode as RunMode | undefined) ?? 'auto'
  const speed: SpeedFactor = speedChoice ?? (run?.speed_factor as SpeedFactor | undefined) ?? '1x'
  const terminal = TERMINAL_STATUSES.has(state.status)
  const send = (cmd: RunCommand) => command.mutate(cmd)
  const ctx = (run?.context ?? {}) as {
    machine?: { machine_id?: string }
    product?: { product_id?: string }
    material_lot?: { material_lot_id?: string }
  }

  const focus = selected ?? state.activeStage
  const focusView = focus ? state.stages[focus] : null

  return (
    <div className="flex flex-col gap-4">
      <h2 className="sr-only">Process Control</h2>
      <section
        aria-label="Run context"
        className="flex flex-wrap items-center justify-between gap-3 rounded border border-border bg-panel px-4 py-2"
      >
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
          <span>
            <span className="text-text-muted">Run</span> {runId ? runId.slice(0, 8) : '—'}
          </span>
          <span className="text-xs text-text-muted" aria-label="Connection">
            {TRANSPORT_LABEL[transport]}
          </span>
        </div>
        <RunControls
          status={state.status}
          mode={mode}
          speed={speed}
          hasRun={Boolean(runId)}
          onModeChange={setModeChoice}
          onSpeedChange={setSpeedChoice}
          onRun={
            runId && !terminal
              ? () => send({ command: 'start', body: { mode, speed_factor: speed } })
              : undefined
          }
          onStep={() => send({ command: 'advance' })}
          onPause={() => send({ command: 'pause' })}
          onResume={() => send({ command: 'resume' })}
          onReset={() => send({ command: 'reset' })}
          onAbort={() => send({ command: 'abort', body: { reason: 'Operator abort' } })}
          disabledReason={
            runId
              ? command.isPending
                ? 'Sending…'
                : null
              : 'Open a run from History. Creating runs needs recipe validation (waiting for the shared contracts).'
          }
        />
      </section>

      {!runId && (
        <p className="text-sm text-text-muted">
          No run selected.{' '}
          <Link to="/history" className="text-state-active">
            Open a run from History
          </Link>
          .
        </p>
      )}
      {command.isError && <CommandError error={command.error} />}
      {state.error && (
        <p role="alert" className="text-xs text-risk-critical">
          Run error: {state.error}
        </p>
      )}
      {state.status === 'BLOCKED' && state.blockedStage && (
        <OverridePanel
          stage={state.blockedStage}
          pending={command.isPending}
          onOverride={(acknowledgement) =>
            send({
              command: 'override',
              body: { stage: asOverridable(state.blockedStage!), acknowledgement },
            })
          }
        />
      )}

      <section aria-label="Stage pipeline" className="rounded border border-border bg-panel px-4 py-3">
        <StagePipeline
          stages={state.stages}
          prediction={state.prediction}
          selectedStage={selected}
          onSelectStage={(s) => setSelected((cur) => (cur === s ? null : s))}
        />
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <div className="rounded border border-border bg-panel p-4">
            <ActiveStagePanel stage={focus} view={focusView} />
          </div>
          <ResultCard prediction={state.prediction} />
        </div>
        <div className="flex flex-col gap-4">
          <div className="rounded border border-border bg-panel p-4">
            <EventTimeline entries={state.timeline} />
          </div>
          <section aria-label="Parameter panel" className="rounded border border-border bg-panel p-4">
            <h3 className="text-xs font-semibold tracking-widest text-text-muted uppercase">
              Parameter panel
            </h3>
            <p className="mt-1 text-sm text-text-muted">
              Machine, product, lot selection and the recipe sliders are built from <code>/constraints</code>{' '}
              and the reference endpoints. They are waiting for the shared contracts and the registry loader.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
