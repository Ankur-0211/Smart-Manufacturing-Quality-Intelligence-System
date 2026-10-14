import { describe, expect, it } from 'vitest'

import { controlAvailability } from './controls'

const enabled = (a: Record<string, boolean>) =>
  Object.entries(a)
    .filter(([, v]) => v)
    .map(([k]) => k)
    .sort()

describe('controlAvailability (mirrors roadmap 9.5.1 transitions)', () => {
  it('before any run only RUN is possible', () => {
    expect(enabled({ ...controlAvailability('INITIALIZED', 'auto', false) })).toEqual(['run'])
  })

  it('auto mode during a stage: pause, reset, abort', () => {
    expect(enabled({ ...controlAvailability('INJECTION', 'auto', true) })).toEqual([
      'abort',
      'pause',
      'reset',
    ])
  })

  it('stepwise mode during a stage: step, reset, abort (no pause)', () => {
    expect(enabled({ ...controlAvailability('PACKING', 'stepwise', true) })).toEqual([
      'abort',
      'reset',
      'step',
    ])
  })

  it('paused: resume, reset, abort', () => {
    expect(enabled({ ...controlAvailability('PAUSED', 'auto', true) })).toEqual(['abort', 'reset', 'resume'])
  })

  it('blocked: override, reset, abort', () => {
    expect(enabled({ ...controlAvailability('BLOCKED', 'auto', true) })).toEqual([
      'abort',
      'override',
      'reset',
    ])
  })

  it.each(['FINAL_RESULT', 'ABORTED'] as const)('terminal %s: only RUN (as a new run, UD-08)', (status) => {
    expect(enabled({ ...controlAvailability(status, 'auto', true) })).toEqual(['run'])
  })
})
