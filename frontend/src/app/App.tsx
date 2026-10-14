import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { createBrowserRouter, createMemoryRouter, RouterProvider } from 'react-router-dom'

import { createQueryClient } from './queryClient'
import { routes } from './routes'

interface AppProps {
  /** Tests pass initial entries to use an in-memory router. */
  initialEntries?: string[]
  queryClient?: QueryClient
}

export function App({ initialEntries, queryClient }: AppProps) {
  const [client] = useState(() => queryClient ?? createQueryClient())
  const [router] = useState(() =>
    initialEntries ? createMemoryRouter(routes, { initialEntries }) : createBrowserRouter(routes),
  )
  return (
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
