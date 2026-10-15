import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { fullRun, prediction, RUN_ID } from '@/test/fixtures/runEvents'

import type { SimulationSnapshot } from './model'
import { FakeEventSource } from '@/test/fakeEventSource'

import { useRunEvents } from './useRunEvents'

const create = (url: string) => new FakeEventSource(url)

function snapshot(over: Partial<SimulationSnapshot> = {}): SimulationSnapshot {
  return {
    run_id: RUN_ID,
    status: 'COOLING',
    mode: 'auto',
    blocked_stage: null,
    current_stage: 'COOLING',
    stage_results: [],
    prediction: null,
    timeline: [],
    last_seq: 9,
    ...over,
  }
}

afterEach(() => {
  FakeEventSource.instances = []
  vi.useRealTimers()
})

describe('useRunEvents', () => {
  it('is idle without a run', () => {
    const { result } = renderHook(() => useRunEvents(null, { createEventSource: create }))
    expect(result.current.transport).toBe('idle')
    expect(FakeEventSource.instances).toHaveLength(0)
  })

  it('streams events over SSE and closes when the run completes', () => {
    const { result } = renderHook(() =>
      useRunEvents(RUN_ID, { createEventSource: create, baseUrl: 'http://api.test/api/v1' }),
    )
    const es = FakeEventSource.instances[0]!
    expect(es.url).toBe(`http://api.test/api/v1/simulation/runs/${RUN_ID}/events`)
    expect(result.current.transport).toBe('connecting')
    act(() => es.open())
    expect(result.current.transport).toBe('sse')

    act(() => fullRun().forEach((e) => es.emit(e)))
    expect(result.current.state.status).toBe('FINAL_RESULT')
    expect(result.current.transport).toBe('closed')
    expect(es.closed).toBe(true)
  })

  it('re-syncs once from the run state when a seq gap is detected', async () => {
    const fetchSnapshot = vi.fn(async () => snapshot())
    const { result } = renderHook(() => useRunEvents(RUN_ID, { createEventSource: create, fetchSnapshot }))
    const es = FakeEventSource.instances[0]!
    const events = fullRun()
    act(() => {
      es.emit(events[0]!)
      es.emit(events[5]!) // gap
    })
    await waitFor(() => expect(result.current.state.lastSeq).toBe(9))
    expect(fetchSnapshot).toHaveBeenCalledTimes(1)
    expect(fetchSnapshot).toHaveBeenCalledWith(RUN_ID)
    expect(result.current.state.status).toBe('COOLING')
  })

  it('re-syncs instead of guessing on a malformed frame', async () => {
    const fetchSnapshot = vi.fn(async () => snapshot())
    renderHook(() => useRunEvents(RUN_ID, { createEventSource: create, fetchSnapshot }))
    act(() => FakeEventSource.instances[0]!.emitRaw('stage.completed', '{not json'))
    await waitFor(() => expect(fetchSnapshot).toHaveBeenCalledTimes(1))
  })

  it('falls back to polling after repeated SSE failures and stops when terminal', async () => {
    vi.useFakeTimers()
    let calls = 0
    const fetchSnapshot = vi.fn(async () => {
      calls += 1
      return calls < 3
        ? snapshot({ last_seq: calls })
        : snapshot({ status: 'FINAL_RESULT', prediction: prediction(), last_seq: 20 })
    })
    const { result } = renderHook(() =>
      useRunEvents(RUN_ID, { createEventSource: create, fetchSnapshot, pollIntervalMs: 300 }),
    )
    const es = FakeEventSource.instances[0]!
    act(() => es.fail())
    expect(result.current.transport).toBe('connecting')
    await act(async () => es.fail())
    expect(es.closed).toBe(true)
    expect(result.current.transport).toBe('polling')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(result.current.state.status).toBe('FINAL_RESULT')
    expect(result.current.transport).toBe('closed')
    const settled = fetchSnapshot.mock.calls.length
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })
    expect(fetchSnapshot.mock.calls.length).toBe(settled)
  })

  it('resets state when the run changes', () => {
    const { result, rerender } = renderHook(({ id }) => useRunEvents(id, { createEventSource: create }), {
      initialProps: { id: RUN_ID as string | null },
    })
    act(() => FakeEventSource.instances[0]!.emit(fullRun()[0]!))
    expect(result.current.state.lastSeq).toBe(1)
    rerender({ id: 'another-run' })
    expect(result.current.state.lastSeq).toBe(0)
    expect(result.current.state.runId).toBe('another-run')
    expect(FakeEventSource.instances[0]!.closed).toBe(true)
  })
})
