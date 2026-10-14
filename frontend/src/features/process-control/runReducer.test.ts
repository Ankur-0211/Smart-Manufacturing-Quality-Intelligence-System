import { describe, expect, it } from 'vitest'

import { fullRun, prediction, RUN_ID, stageResult, StreamBuilder } from '@/test/fixtures/runEvents'

import type { SimulationEvent, SimulationSnapshot } from './model'
import { initialRunState, runReducer, type RunViewState } from './runReducer'

function play(events: SimulationEvent[], start: RunViewState = initialRunState(RUN_ID)): RunViewState {
  return events.reduce((s, event) => runReducer(s, { kind: 'event', event }), start)
}

describe('runReducer', () => {
  it('plays a full run in order', () => {
    const s = play(fullRun())
    expect(s.status).toBe('FINAL_RESULT')
    expect(s.lastSeq).toBe(fullRun().length)
    expect(Object.values(s.stages).every((v) => v.state === 'COMPLETED')).toBe(true)
    expect(s.stages.COOLING.result?.risk_level).toBe('HIGH')
    expect(s.stages.PLASTICIZING.anomaly).toBe(true)
    expect(s.stages.MATERIAL_CONDITIONING.anomaly).toBe(false)
    expect(s.prediction?.p_fail).toBe(0.71)
    expect(s.timeline).toHaveLength(fullRun().length)
    expect(s.timeline.find((t) => t.type === 'anomaly.flagged')?.tone).toBe('anomaly')
  })

  it('marks the active stage while a stage runs', () => {
    const events = new StreamBuilder().push('run.started').push('stage.started', 'INJECTION').events
    const s = play(events)
    expect(s.activeStage).toBe('INJECTION')
    expect(s.status).toBe('INJECTION')
    expect(s.stages.INJECTION.state).toBe('ACTIVE')
  })

  it('ignores duplicates delivered after a reconnect', () => {
    const events = fullRun()
    const once = play(events.slice(0, 4))
    const twice = play(events.slice(0, 4), once)
    expect(twice).toBe(once)
  })

  it('flags a gap for resync instead of applying out-of-order events', () => {
    const events = fullRun()
    const s = play([events[0]!, events[1]!, events[4]!])
    expect(s.needsResync).toBe(true)
    expect(s.lastSeq).toBe(2)
    expect(s.timeline).toHaveLength(2)
  })

  it('ignores events from another run', () => {
    const other = new StreamBuilder('other-run').push('run.started').events
    expect(play(other)).toEqual(initialRunState(RUN_ID))
  })

  it('handles BLOCKED then override', () => {
    const blocked = stageResult('PLASTICIZING', {
      blocked: true,
      block_reason: 'melt above degradation ceiling',
      substate: 'BLOCKED',
      risk_level: 'CRITICAL',
      risk_ordinal: 4,
    })
    const b = new StreamBuilder()
      .push('run.started')
      .stage('MATERIAL_CONDITIONING')
      .push('stage.started', 'PLASTICIZING')
      .push('constraint.breached', 'PLASTICIZING', {
        rule_id: 'HC-001',
        severity: 'CRITICAL',
        message: 'ceiling',
      })
      .push('stage.blocked', 'PLASTICIZING', { reason: 'melt above degradation ceiling' })
    let s = play(b.events)
    expect(s.status).toBe('BLOCKED')
    expect(s.blockedStage).toBe('PLASTICIZING')
    expect(s.stages.PLASTICIZING.state).toBe('BLOCKED')
    expect(s.timeline.at(-2)?.tone).toBe('critical')

    b.push('stage.override_acknowledged', 'PLASTICIZING', { acknowledgement: 'ok' }).push(
      'stage.completed',
      'PLASTICIZING',
      { ...blocked, overridden: true } as unknown as Record<string, unknown>,
    )
    s = play(b.events)
    expect(s.blockedStage).toBeNull()
    expect(s.stages.PLASTICIZING.state).toBe('COMPLETED')
    expect(s.stages.PLASTICIZING.overridden).toBe(true)
  })

  it('pauses and resumes to the previous status', () => {
    const b = new StreamBuilder().push('run.started').push('stage.started', 'PACKING').push('run.paused')
    let s = play(b.events)
    expect(s.status).toBe('PAUSED')
    s = play(b.push('run.resumed').events)
    expect(s.status).toBe('PACKING')
  })

  it('reset clears stages but keeps the timeline', () => {
    const b = new StreamBuilder().push('run.started').stage('MATERIAL_CONDITIONING').push('run.reset')
    const s = play(b.events)
    expect(s.status).toBe('INITIALIZED')
    expect(s.stages.MATERIAL_CONDITIONING.state).toBe('PENDING')
    expect(s.timeline.map((t) => t.type)).toEqual([
      'run.started',
      'stage.started',
      'stage.completed',
      'run.reset',
    ])
  })

  it('records aborts and errors', () => {
    const s = play(
      new StreamBuilder()
        .push('run.started')
        .push('run.error', null, { code: 'INTERNAL_ERROR', message: 'boom' })
        .push('run.aborted', null, { reason: 'ERROR:INTERNAL_ERROR' }).events,
    )
    expect(s.status).toBe('ABORTED')
    expect(s.error).toBe('INTERNAL_ERROR: boom')
  })

  it('hydrates from a snapshot after a gap', () => {
    const snapshot: SimulationSnapshot = {
      run_id: RUN_ID,
      status: 'FINAL_RESULT',
      mode: 'auto',
      blocked_stage: null,
      current_stage: null,
      stage_results: [stageResult('MATERIAL_CONDITIONING'), stageResult('COOLING', { risk_level: 'HIGH' })],
      prediction: prediction(),
      timeline: fullRun().slice(0, 3),
      last_seq: 17,
    }
    const s = runReducer({ ...initialRunState(RUN_ID), needsResync: true }, { kind: 'hydrate', snapshot })
    expect(s.needsResync).toBe(false)
    expect(s.lastSeq).toBe(17)
    expect(s.stages.COOLING.state).toBe('COMPLETED')
    expect(s.stages.QUALITY_INSPECTION.state).toBe('COMPLETED')
    expect(s.stages.INJECTION.state).toBe('PENDING')
    expect(s.timeline).toHaveLength(3)
  })
})
