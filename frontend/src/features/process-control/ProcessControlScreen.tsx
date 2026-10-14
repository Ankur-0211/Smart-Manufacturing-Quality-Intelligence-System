import { useState } from 'react'

import { ActiveStagePanel } from '@/components/pipeline/ActiveStagePanel'
import { EventTimeline } from '@/components/pipeline/EventTimeline'
import { RunControls } from '@/components/pipeline/RunControls'
import { StagePipeline } from '@/components/pipeline/StagePipeline'
import { ResultCard } from '@/components/result/ResultCard'

import type { RunMode, SpeedFactor, StageName } from './model'
import { useRunEvents } from './useRunEvents'

/**
 * Process Control workspace (Plan §15.2; roadmap R2-P6).
 *
 * Current state: the visual components are live and driven by real run events through
 * `useRunEvents`. There is no run yet because creating and starting runs needs the simulation API
 * (R2-P4) and the context/parameter panels need the reference and constraint endpoints, which depend
 * on Role 1's contracts and registry. Nothing on this screen is pre-filled with example values.
 */
export function ProcessControlScreen() {
  const [runId] = useState<string | null>(null)
  const [mode, setMode] = useState<RunMode>('auto')
  const [speed, setSpeed] = useState<SpeedFactor>('1x')
  const [selected, setSelected] = useState<StageName | null>(null)
  const { state } = useRunEvents(runId)

  const focus = selected ?? state.activeStage
  const focusView = focus ? state.stages[focus] : null

  return (
    <div className="flex flex-col gap-4">
      <h2 className="sr-only">Process Control</h2>
      <section
        aria-label="Run context"
        className="flex flex-wrap items-center justify-between gap-3 rounded border border-border bg-panel px-4 py-2"
      >
        <div className="numeric flex gap-4 text-sm">
          <span>
            <span className="text-text-muted">Machine</span> —
          </span>
          <span>
            <span className="text-text-muted">Product</span> —
          </span>
          <span>
            <span className="text-text-muted">Lot</span> —
          </span>
          <span>
            <span className="text-text-muted">Run</span> {state.runId ? state.runId.slice(0, 8) : '—'}
          </span>
        </div>
        <RunControls
          status={state.status}
          mode={mode}
          speed={speed}
          hasRun={Boolean(state.runId)}
          onModeChange={setMode}
          onSpeedChange={setSpeed}
          disabledReason="Run controls connect to the simulation API in R2-P4."
        />
      </section>

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
              and the reference endpoints. They are waiting for the shared constraint registry.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
