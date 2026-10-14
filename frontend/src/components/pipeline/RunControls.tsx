import { controlAvailability } from '@/features/process-control/controls'
import type { RunMode, RunStatus, SpeedFactor } from '@/features/process-control/model'
import { cn } from '@/lib/utils'

export interface RunControlHandlers {
  onRun?: () => void
  onStep?: () => void
  onPause?: () => void
  onResume?: () => void
  onReset?: () => void
  onAbort?: () => void
  onModeChange?: (mode: RunMode) => void
  onSpeedChange?: (speed: SpeedFactor) => void
}

interface RunControlsProps extends RunControlHandlers {
  status: RunStatus
  mode: RunMode
  speed: SpeedFactor
  hasRun: boolean
  /** When set, every control is disabled and this reason is shown (e.g. API not available yet). */
  disabledReason?: string | null
}

const SPEEDS: SpeedFactor[] = ['0.5x', '1x', '2x', 'instant']

function Button({
  label,
  enabled,
  onClick,
  tone = 'default',
}: {
  label: string
  enabled: boolean
  onClick?: () => void
  tone?: 'default' | 'primary' | 'danger'
}) {
  return (
    <button
      type="button"
      disabled={!enabled || !onClick}
      onClick={onClick}
      className={cn(
        'rounded border px-3 py-1 text-xs font-semibold tracking-wide uppercase disabled:cursor-not-allowed disabled:opacity-40',
        tone === 'primary' && 'border-state-active text-state-active hover:bg-state-active/10',
        tone === 'danger' && 'border-risk-critical text-risk-critical hover:bg-risk-critical/10',
        tone === 'default' && 'border-border text-text hover:bg-panel-raised',
      )}
    >
      {label}
    </button>
  )
}

/** RUN / STEP / PAUSE / RESUME / RESET / ABORT plus mode and presentation speed (Plan §15.2, F17). */
export function RunControls(props: RunControlsProps) {
  const { status, mode, speed, hasRun, disabledReason } = props
  const can = controlAvailability(status, mode, hasRun)
  const off = Boolean(disabledReason)

  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Run controls">
      <Button label="Run" tone="primary" enabled={!off && can.run} onClick={props.onRun} />
      <Button label="Step" enabled={!off && can.step} onClick={props.onStep} />
      {status === 'PAUSED' ? (
        <Button label="Resume" enabled={!off && can.resume} onClick={props.onResume} />
      ) : (
        <Button label="Pause" enabled={!off && can.pause} onClick={props.onPause} />
      )}
      <Button label="Reset" enabled={!off && can.reset} onClick={props.onReset} />
      <Button label="Abort" tone="danger" enabled={!off && can.abort} onClick={props.onAbort} />

      <label className="ml-3 flex items-center gap-1 text-xs text-text-muted">
        Mode
        <select
          value={mode}
          disabled={off || (hasRun && status !== 'INITIALIZED')}
          onChange={(e) => props.onModeChange?.(e.target.value as RunMode)}
          className="rounded border border-border bg-panel px-1 py-0.5 text-text"
        >
          <option value="auto">auto</option>
          <option value="stepwise">stepwise</option>
        </select>
      </label>
      {/* "Presentation speed", never "process time" (Plan §7.4). */}
      <label className="flex items-center gap-1 text-xs text-text-muted">
        Presentation speed
        <select
          value={speed}
          disabled={off}
          onChange={(e) => props.onSpeedChange?.(e.target.value as SpeedFactor)}
          className="rounded border border-border bg-panel px-1 py-0.5 text-text"
        >
          {SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      {disabledReason && <span className="text-xs text-text-muted">{disabledReason}</span>}
    </div>
  )
}
