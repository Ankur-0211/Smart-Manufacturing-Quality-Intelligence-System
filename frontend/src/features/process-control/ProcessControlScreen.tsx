import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiClientError } from '@/api/client'
import { useConstraints } from '@/api/constraints'
import {
  useCreateAndStartRun,
  useRunCommand,
  useRunState,
  type CreateRunRequest,
  type OverrideRequest,
  type RunCommand,
} from '@/api/runs'
import { clientErrors, serverErrors } from '@/components/params/recipeValidation'
import { RunSetupPanel } from '@/components/params/RunSetupPanel'
import { useEffectiveRecipe } from '@/components/params/useEffectiveRecipe'
import { ActiveStagePanel } from '@/components/pipeline/ActiveStagePanel'
import { EventTimeline } from '@/components/pipeline/EventTimeline'
import { RunControls } from '@/components/pipeline/RunControls'
import { StagePipeline } from '@/components/pipeline/StagePipeline'
import { ResultCard } from '@/components/result/ResultCard'
import { useRunSetup } from '@/stores/runSetup'

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
 * RUN creates a run from the setup panel (context pickers + registry-driven recipe), starts it and
 * follows it live over SSE with polling fallback. `?run=<id>` (from History) opens an existing run;
 * RUN on a finished run starts a fresh one from the setup (finished runs are immutable, UD-08).
 */
export function ProcessControlScreen() {
  const [params, setParams] = useSearchParams()
  const runId = params.get('run')
  const { state, transport } = useRunEvents(runId)
  const runQuery = useRunState(runId)
  const command = useRunCommand(runId)
  const createRun = useCreateAndStartRun()
  const setup = useRunSetup()
  const recipe = useEffectiveRecipe()
  const constraints = useConstraints().data
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

  // A new run is created from the setup draft when nothing is open or the open run is finished.
  const createsNewRun = !runId || terminal
  const missingContext = !setup.machineId || !setup.productId || !setup.lotId
  const invalidRecipe = !constraints || !recipe || Object.keys(clientErrors(constraints, recipe)).length > 0
  const setupReason = missingContext
    ? 'Choose a machine, product and material lot to run.'
    : invalidRecipe
      ? 'Fix the highlighted parameters to run.'
      : null
  const createRunNow = () => {
    if (!recipe || !setup.machineId || !setup.productId || !setup.lotId) return
    const body = {
      machine_id: setup.machineId,
      product_id: setup.productId,
      material_lot_id: setup.lotId,
      parameters: recipe,
      mode,
      speed_factor: speed,
      halt_on_critical: true,
    } as CreateRunRequest
    createRun.mutate(body, {
      onSuccess: (created) => {
        setSelected(null)
        setParams({ run: created.run_id })
      },
    })
  }
  const copyRunToSetup = () => {
    if (!run) return
    setup.setContext({
      machineId: ctx.machine?.machine_id ?? null,
      productId: ctx.product?.product_id ?? null,
      lotId: ctx.material_lot?.material_lot_id ?? null,
    })
    setup.setRecipe({ ...run.parameters })
  }
  const shown = runId
    ? {
        machine: ctx.machine?.machine_id,
        product: ctx.product?.product_id,
        lot: ctx.material_lot?.material_lot_id,
      }
    : { machine: setup.machineId, product: setup.productId, lot: setup.lotId }
  const createErrors = serverErrors(createRun.isError ? createRun.error : null)
  const createErrorShownInPanel =
    createErrors.general.length > 0 || Object.keys(createErrors.fields).length > 0

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
            <span className="text-text-muted">Machine</span> {shown.machine ?? '—'}
          </span>
          <span>
            <span className="text-text-muted">Product</span> {shown.product ?? '—'}
          </span>
          <span>
            <span className="text-text-muted">Lot</span> {shown.lot ?? '—'}
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
            createsNewRun
              ? setupReason
                ? undefined
                : createRunNow
              : () => send({ command: 'start', body: { mode, speed_factor: speed } })
          }
          onStep={() => send({ command: 'advance' })}
          onPause={() => send({ command: 'pause' })}
          onResume={() => send({ command: 'resume' })}
          onReset={() => send({ command: 'reset' })}
          onAbort={() => send({ command: 'abort', body: { reason: 'Operator abort' } })}
          disabledReason={command.isPending || createRun.isPending ? 'Sending…' : null}
          hint={createsNewRun ? setupReason : null}
        />
      </section>

      {!runId && (
        <p className="text-sm text-text-muted">
          Set up a run below and press RUN, or{' '}
          <Link to="/history" className="text-state-active">
            open a run from History
          </Link>
          .
        </p>
      )}
      {command.isError && <CommandError error={command.error} />}
      {createRun.isError && !createErrorShownInPanel && <CommandError error={createRun.error} />}
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
          <ResultCard prediction={state.prediction} runId={state.status === 'FINAL_RESULT' ? runId : null} />
        </div>
        <div className="flex flex-col gap-4">
          <div className="rounded border border-border bg-panel p-4">
            <EventTimeline entries={state.timeline} />
          </div>
          <section aria-label="Parameter panel" className="rounded border border-border bg-panel p-4">
            <RunSetupPanel server={createErrors} onUseRun={run ? copyRunToSetup : undefined} />
          </section>
        </div>
      </div>
    </div>
  )
}
