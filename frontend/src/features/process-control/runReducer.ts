/**
 * Pure reducer: SSE simulation events -> Process Control view state (roadmap §9.5, R2-P6 task 7).
 *
 * Client contract (roadmap §9.5.4): track `last_seq`; ignore duplicates; on a gap
 * (`seq > lastSeq + 1`) do NOT guess, mark `needsResync` so the hook fetches the full run state once.
 */
import {
  STAGE_META,
  STAGE_ORDER,
  TERMINAL_STATUSES,
  type PredictionView,
  type RunStatus,
  type SimulationEvent,
  type SimulationSnapshot,
  type StageName,
  type StageResultView,
} from './model'

export type StageVisualState = 'PENDING' | 'ACTIVE' | 'COMPLETED' | 'BLOCKED'

export interface StageView {
  state: StageVisualState
  result: StageResultView | null
  anomaly: boolean
  overridden: boolean
  inputsInScope: Record<string, unknown> | null
}

export type TimelineTone = 'info' | 'anomaly' | 'warning' | 'critical' | 'success'

export interface TimelineEntry {
  seq: number
  ts: string
  type: string
  stage: StageName | null
  summary: string
  tone: TimelineTone
}

export interface RunViewState {
  runId: string | null
  status: RunStatus
  statusBeforePause: RunStatus | null
  activeStage: StageName | null
  blockedStage: StageName | null
  stages: Record<StageName, StageView>
  timeline: TimelineEntry[]
  prediction: PredictionView | null
  lastSeq: number
  needsResync: boolean
  error: string | null
}

export type RunAction =
  | { kind: 'event'; event: SimulationEvent }
  | { kind: 'hydrate'; snapshot: SimulationSnapshot }
  | { kind: 'reset'; runId: string | null }

function emptyStages(): Record<StageName, StageView> {
  return Object.fromEntries(
    STAGE_ORDER.map((name) => [
      name,
      { state: 'PENDING', result: null, anomaly: false, overridden: false, inputsInScope: null },
    ]),
  ) as Record<StageName, StageView>
}

export function initialRunState(runId: string | null = null): RunViewState {
  return {
    runId,
    status: 'INITIALIZED',
    statusBeforePause: null,
    activeStage: null,
    blockedStage: null,
    stages: emptyStages(),
    timeline: [],
    prediction: null,
    lastSeq: 0,
    needsResync: false,
    error: null,
  }
}

export function isTerminal(status: RunStatus): boolean {
  return TERMINAL_STATUSES.has(status)
}

const fmt = (n: unknown, digits = 2): string => (typeof n === 'number' ? n.toFixed(digits) : '—')

function stageLabel(stage: StageName | null): string {
  return stage ? STAGE_META[stage].short.toUpperCase() : ''
}

/** One human-readable timeline line per event (roadmap §15.2 event timeline). */
export function summarize(event: SimulationEvent): { summary: string; tone: TimelineTone } {
  const p = event.payload
  const where = stageLabel(event.stage)
  switch (event.type) {
    case 'run.started':
      return { summary: 'run started', tone: 'info' }
    case 'stage.started':
      return { summary: `${where} started`, tone: 'info' }
    case 'stage.progress':
      return { summary: `${where} ${fmt(p.pct, 0)}%`, tone: 'info' }
    case 'stage.completed':
      return {
        summary: `${where} completed  h=${fmt(p.health_score)}  ${String(p.risk_level ?? '')}`,
        tone: p.risk_level === 'HIGH' || p.risk_level === 'CRITICAL' ? 'warning' : 'success',
      }
    case 'anomaly.flagged':
      return {
        summary: `anomaly ${where || 'GLOBAL'}${p.note ? ` — ${String(p.note)}` : ''}`,
        tone: 'anomaly',
      }
    case 'constraint.breached':
      return {
        summary: `${String(p.rule_id ?? 'constraint')}: ${String(p.message ?? '')}`,
        tone: p.severity === 'CRITICAL' ? 'critical' : 'warning',
      }
    case 'stage.blocked':
      return { summary: `${where} BLOCKED — ${String(p.reason ?? '')}`, tone: 'critical' }
    case 'stage.override_acknowledged':
      return { summary: `${where} override acknowledged`, tone: 'critical' }
    case 'prediction.ready':
      return {
        summary: `prediction ${String(p.label ?? '')}  P(fail)=${fmt(p.p_fail)}`,
        tone: p.label === 'FAIL' ? 'warning' : 'success',
      }
    case 'run.completed':
      return { summary: 'run completed', tone: 'success' }
    case 'run.paused':
      return { summary: 'run paused', tone: 'info' }
    case 'run.resumed':
      return { summary: 'run resumed', tone: 'info' }
    case 'run.reset':
      return { summary: 'run reset', tone: 'info' }
    case 'run.aborted':
      return { summary: `run aborted${p.reason ? ` — ${String(p.reason)}` : ''}`, tone: 'critical' }
    case 'run.error':
      return { summary: `error ${String(p.code ?? '')}: ${String(p.message ?? '')}`, tone: 'critical' }
  }
}

function withStage(state: RunViewState, stage: StageName, patch: Partial<StageView>): RunViewState {
  return { ...state, stages: { ...state.stages, [stage]: { ...state.stages[stage], ...patch } } }
}

function applyEvent(state: RunViewState, event: SimulationEvent): RunViewState {
  const stage = event.stage
  const p = event.payload
  switch (event.type) {
    case 'run.started':
      return { ...state, runId: event.run_id, status: 'MATERIAL_CONDITIONING', error: null }
    case 'stage.started':
      if (!stage) return state
      return {
        ...withStage(state, stage, {
          state: 'ACTIVE',
          inputsInScope: (p.inputs_in_scope as Record<string, unknown> | undefined) ?? null,
        }),
        status: stage,
        activeStage: stage,
      }
    case 'stage.completed': {
      if (!stage) return state
      const result = p as unknown as StageResultView
      return withStage(state, stage, {
        state: 'COMPLETED',
        result,
        anomaly: state.stages[stage].anomaly || Boolean(result.anomaly?.flag),
        overridden: state.stages[stage].overridden || Boolean(result.overridden),
      })
    }
    case 'anomaly.flagged':
      return stage ? withStage(state, stage, { anomaly: true }) : state
    case 'stage.blocked':
      if (!stage) return state
      return {
        ...withStage(state, stage, { state: 'BLOCKED' }),
        status: 'BLOCKED',
        blockedStage: stage,
        activeStage: stage,
      }
    case 'stage.override_acknowledged':
      if (!stage) return state
      return { ...withStage(state, stage, { overridden: true }), blockedStage: null, status: stage }
    case 'prediction.ready':
      return {
        ...withStage(state, 'QUALITY_INSPECTION', { state: 'COMPLETED' }),
        prediction: p as unknown as PredictionView,
        status: 'QUALITY_INSPECTION',
        activeStage: 'QUALITY_INSPECTION',
      }
    case 'run.completed':
      return { ...state, status: 'FINAL_RESULT', activeStage: null }
    case 'run.paused':
      return { ...state, statusBeforePause: state.status, status: 'PAUSED' }
    case 'run.resumed':
      return { ...state, status: state.statusBeforePause ?? state.status, statusBeforePause: null }
    case 'run.reset':
      return { ...initialRunState(state.runId), lastSeq: state.lastSeq, timeline: state.timeline }
    case 'run.aborted':
      return { ...state, status: 'ABORTED', activeStage: null }
    case 'run.error':
      return { ...state, error: `${String(p.code ?? 'ERROR')}: ${String(p.message ?? '')}` }
    case 'constraint.breached':
    case 'stage.progress':
      return state
  }
}

function hydrate(snapshot: SimulationSnapshot): RunViewState {
  let state: RunViewState = {
    ...initialRunState(snapshot.run_id),
    status: snapshot.status,
    blockedStage: snapshot.blocked_stage,
    activeStage: snapshot.current_stage,
    prediction: snapshot.prediction,
    lastSeq: snapshot.last_seq,
  }
  for (const result of snapshot.stage_results) {
    state = withStage(state, result.stage_name, {
      state: result.blocked && !result.overridden ? 'BLOCKED' : 'COMPLETED',
      result,
      anomaly: result.anomaly.flag,
      overridden: Boolean(result.overridden),
    })
  }
  if (snapshot.current_stage && state.stages[snapshot.current_stage].state === 'PENDING') {
    state = withStage(state, snapshot.current_stage, { state: 'ACTIVE' })
  }
  if (snapshot.prediction) state = withStage(state, 'QUALITY_INSPECTION', { state: 'COMPLETED' })
  const timeline = snapshot.timeline.map((e) => ({
    ...summarize(e),
    seq: e.seq,
    ts: e.ts,
    type: e.type,
    stage: e.stage,
  }))
  return { ...state, timeline }
}

export function runReducer(state: RunViewState, action: RunAction): RunViewState {
  if (action.kind === 'reset') return initialRunState(action.runId)
  if (action.kind === 'hydrate') return hydrate(action.snapshot)

  const event = action.event
  if (state.runId && event.run_id !== state.runId) return state // stale stream
  if (event.seq <= state.lastSeq) return state // duplicate after reconnect
  if (event.seq > state.lastSeq + 1) return { ...state, needsResync: true } // gap: resync, don't guess

  const next = applyEvent({ ...state, runId: state.runId ?? event.run_id }, event)
  const entry: TimelineEntry = {
    ...summarize(event),
    seq: event.seq,
    ts: event.ts,
    type: event.type,
    stage: event.stage,
  }
  return { ...next, lastSeq: event.seq, needsResync: false, timeline: [...next.timeline, entry] }
}
