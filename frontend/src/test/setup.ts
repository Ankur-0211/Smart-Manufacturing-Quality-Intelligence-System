import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { useRunSetup } from '@/stores/runSetup'

import { server } from './server'

beforeAll(async () => {
  server.listen({ onUnhandledFrame: 'error' })
  // Charts are code-split (components/charts/lazy.tsx). Loading them once up front keeps a slow
  // first import of the chart library from racing a test's assertions on a busy machine.
  await Promise.all([
    import('@/components/charts/ShapBars'),
    import('@/components/charts/StageRiskDonut'),
    import('@/components/charts/SensitivityCurve'),
    import('@/components/charts/OutcomeBars'),
    import('@/components/charts/SeriesLine'),
  ])
})
afterEach(() => {
  server.resetHandlers()
  useRunSetup.setState({ machineId: null, productId: null, lotId: null, recipe: null })
  cleanup()
})
afterAll(() => server.close())
