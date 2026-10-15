/**
 * Live run state over SSE with gap re-sync and polling fallback (roadmap §9.5.4, Plan R17).
 *
 * - EventSource reconnects automatically and resends `Last-Event-ID`; the server replays from there.
 * - A `seq` gap marks `needsResync`; the hook fetches the full run state once and hydrates.
 * - After `maxSseFailures` consecutive errors without a successful open, it closes SSE and polls
 *   `GET /simulation/runs/{id}` every `pollIntervalMs` until the run is terminal.
 */
import { useCallback, useEffect, useReducer, useRef, useState } from 'react'

import { API_BASE_URL, apiGet } from '@/api/client'

import { useEventSourceFactory } from './eventSource'
import { EVENT_TYPES, type SimulationEvent, type SimulationSnapshot } from './model'
import { initialRunState, isTerminal, runReducer, type RunViewState } from './runReducer'

export type Transport = 'idle' | 'connecting' | 'sse' | 'polling' | 'closed'
type Phase = 'connecting' | 'sse' | 'polling'

/** The subset of the browser EventSource API the hook uses (injectable for tests). */
export interface EventSourceLike {
  onopen: ((this: EventSourceLike, ev: Event) => unknown) | null
  onerror: ((this: EventSourceLike, ev: Event) => unknown) | null
  addEventListener(type: string, listener: (ev: MessageEvent<string>) => void): void
  close(): void
}

export interface RunEventsOptions {
  baseUrl?: string
  createEventSource?: (url: string) => EventSourceLike
  fetchSnapshot?: (runId: string) => Promise<SimulationSnapshot>
  pollIntervalMs?: number
  maxSseFailures?: number
}

const defaultFetch = async (runId: string): Promise<SimulationSnapshot> =>
  (await apiGet<SimulationSnapshot>(`/simulation/runs/${encodeURIComponent(runId)}`)).data

export interface RunEvents {
  state: RunViewState
  transport: Transport
}

export function useRunEvents(runId: string | null, options: RunEventsOptions = {}): RunEvents {
  const {
    baseUrl = API_BASE_URL,
    createEventSource: createOverride,
    fetchSnapshot = defaultFetch,
    pollIntervalMs = 300,
    maxSseFailures = 2,
  } = options

  const contextFactory = useEventSourceFactory()
  const createEventSource = createOverride ?? contextFactory
  const [state, dispatch] = useReducer(runReducer, runId, initialRunState)
  // Connection phase is only ever set from EventSource callbacks; everything else is derived.
  const [conn, setConn] = useState<{ runId: string | null; phase: Phase }>({ runId, phase: 'connecting' })
  const phase: Phase = conn.runId === runId ? conn.phase : 'connecting'

  // Reset the view when the run changes (React's "adjust state during render" pattern).
  const [prevRunId, setPrevRunId] = useState(runId)
  if (prevRunId !== runId) {
    setPrevRunId(runId)
    dispatch({ kind: 'reset', runId })
  }

  const sourceRef = useRef<EventSourceLike | null>(null)
  const resyncInFlight = useRef(false)

  // Keep the latest fetcher without re-subscribing when callers pass inline functions.
  const fetchRef = useRef(fetchSnapshot)
  useEffect(() => {
    fetchRef.current = fetchSnapshot
  }, [fetchSnapshot])

  const resync = useCallback(async (id: string) => {
    if (resyncInFlight.current) return
    resyncInFlight.current = true
    try {
      dispatch({ kind: 'hydrate', snapshot: await fetchRef.current(id) })
    } catch {
      // Keep current state; the next event, poll or reconnect will try again.
    } finally {
      resyncInFlight.current = false
    }
  }, [])

  // SSE subscription
  useEffect(() => {
    if (!runId) return
    const source = createEventSource(`${baseUrl}/simulation/runs/${encodeURIComponent(runId)}/events`)
    sourceRef.current = source
    let failures = 0

    source.onopen = () => {
      failures = 0
      setConn({ runId, phase: 'sse' })
    }
    source.onerror = () => {
      failures += 1
      if (failures >= maxSseFailures) {
        source.close()
        sourceRef.current = null
        setConn({ runId, phase: 'polling' })
      }
    }
    for (const type of EVENT_TYPES) {
      source.addEventListener(type, (message) => {
        failures = 0
        try {
          dispatch({ kind: 'event', event: JSON.parse(message.data) as SimulationEvent })
        } catch {
          // Malformed frame: force a full re-sync instead of rendering a guess.
          void resync(runId)
        }
      })
    }
    return () => {
      source.close()
      sourceRef.current = null
    }
  }, [runId, baseUrl, createEventSource, maxSseFailures, resync])

  // Gap detected by the reducer -> one snapshot fetch.
  useEffect(() => {
    if (runId && state.needsResync) void resync(runId)
  }, [runId, state.needsResync, resync])

  // Close the stream once the run is terminal (the server also closes it).
  const terminal = isTerminal(state.status)
  useEffect(() => {
    if (terminal && sourceRef.current) {
      sourceRef.current.close()
      sourceRef.current = null
    }
  }, [terminal])

  // Polling fallback.
  const polling = phase === 'polling'
  useEffect(() => {
    if (!runId || !polling || terminal) return
    void resync(runId)
    const timer = setInterval(() => void resync(runId), pollIntervalMs)
    return () => clearInterval(timer)
  }, [runId, polling, terminal, pollIntervalMs, resync])

  const transport: Transport = !runId ? 'idle' : terminal ? 'closed' : phase
  return { state, transport }
}
