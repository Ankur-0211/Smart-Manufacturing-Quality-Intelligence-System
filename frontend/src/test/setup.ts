import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { useRunSetup } from '@/stores/runSetup'

import { server } from './server'

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  server.resetHandlers()
  useRunSetup.setState({ machineId: null, productId: null, lotId: null, recipe: null })
  cleanup()
})
afterAll(() => server.close())
