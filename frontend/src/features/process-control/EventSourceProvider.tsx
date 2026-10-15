import type { ReactNode } from 'react'

import { browserEventSource, EventSourceContext, type EventSourceFactory } from './eventSource'

export function EventSourceProvider({
  factory,
  children,
}: {
  factory?: EventSourceFactory
  children: ReactNode
}) {
  return (
    <EventSourceContext.Provider value={factory ?? browserEventSource}>
      {children}
    </EventSourceContext.Provider>
  )
}
