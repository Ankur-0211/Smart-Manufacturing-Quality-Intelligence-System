/**
 * Which run controls are allowed in each state. Mirrors the FSM transition table (roadmap §9.5.1),
 * so the UI never offers a command the server would reject with INVALID_STATE_TRANSITION.
 */
import { TERMINAL_STATUSES, type RunMode, type RunStatus } from './model'

export interface ControlAvailability {
  run: boolean
  step: boolean
  pause: boolean
  resume: boolean
  reset: boolean
  abort: boolean
  override: boolean
}

const STAGE_STATUSES: ReadonlySet<RunStatus> = new Set([
  'MATERIAL_CONDITIONING',
  'PLASTICIZING',
  'INJECTION',
  'PACKING',
  'COOLING',
  'QUALITY_INSPECTION',
])

export function controlAvailability(status: RunStatus, mode: RunMode, hasRun: boolean): ControlAvailability {
  const terminal = TERMINAL_STATUSES.has(status)
  const started = hasRun && status !== 'INITIALIZED' && !terminal
  return {
    // A finished run cannot be re-run in place (UD-08): RUN starts a fresh run from the same recipe.
    run: !hasRun || status === 'INITIALIZED' || terminal,
    step: hasRun && mode === 'stepwise' && STAGE_STATUSES.has(status),
    pause: hasRun && mode === 'auto' && STAGE_STATUSES.has(status),
    resume: hasRun && status === 'PAUSED',
    reset: started,
    abort: started,
    override: hasRun && status === 'BLOCKED',
  }
}
