/**
 * EventSource factory, injectable through context (tests, or environments without EventSource).
 * Without a browser EventSource the stub fails immediately, which drives `useRunEvents` into its
 * polling fallback (roadmap §9.5.4).
 */
import { createContext, useContext } from 'react'

import type { EventSourceLike } from './useRunEvents'

export type EventSourceFactory = (url: string) => EventSourceLike

class UnavailableEventSource implements EventSourceLike {
  onopen: EventSourceLike['onopen'] = null
  onerror: EventSourceLike['onerror'] = null
  private closed = false

  constructor() {
    // Two failures -> the hook switches to polling. Async so handlers are attached first.
    setTimeout(() => {
      for (let i = 0; i < 2 && !this.closed; i += 1) this.onerror?.call(this, new Event('error'))
    }, 0)
  }

  addEventListener(): void {}

  close(): void {
    this.closed = true
  }
}

export const browserEventSource: EventSourceFactory = (url) =>
  typeof EventSource === 'undefined'
    ? new UnavailableEventSource()
    : (new EventSource(url) as unknown as EventSourceLike)

export const EventSourceContext = createContext<EventSourceFactory>(browserEventSource)

export function useEventSourceFactory(): EventSourceFactory {
  return useContext(EventSourceContext)
}
