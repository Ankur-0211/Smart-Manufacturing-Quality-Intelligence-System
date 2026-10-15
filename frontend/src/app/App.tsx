import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { createBrowserRouter, createMemoryRouter, RouterProvider } from 'react-router-dom'

import type { EventSourceFactory } from '@/features/process-control/eventSource'
import { EventSourceProvider } from '@/features/process-control/EventSourceProvider'

import { createQueryClient } from './queryClient'
import { routes } from './routes'

interface AppProps {
  /** Tests pass initial entries to use an in-memory router. */
  initialEntries?: string[]
  queryClient?: QueryClient
  /** Tests inject a fake EventSource. */
  eventSourceFactory?: EventSourceFactory
}

export function App({ initialEntries, queryClient, eventSourceFactory }: AppProps) {
  const [client] = useState(() => queryClient ?? createQueryClient())
  const [router] = useState(() =>
    initialEntries ? createMemoryRouter(routes, { initialEntries }) : createBrowserRouter(routes),
  )
  return (
    <QueryClientProvider client={client}>
      <EventSourceProvider factory={eventSourceFactory}>
        <RouterProvider router={router} />
      </EventSourceProvider>
    </QueryClientProvider>
  )
}
