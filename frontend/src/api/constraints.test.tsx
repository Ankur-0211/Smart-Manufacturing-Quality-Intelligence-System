import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import { API, envelope, server } from '@/test/server'

import {
  type Constraints,
  nominalRecipe,
  outOfRange,
  type ParameterSpec,
  setpoints,
  useConstraints,
} from './constraints'

/** TEST-ONLY spec builder; real values always come from GET /constraints. */
function spec(over: Partial<ParameterSpec>): ParameterSpec {
  return {
    name: 'x',
    kind: 'setpoint',
    stage: 'PLASTICIZING',
    unit: 'c',
    dtype: 'float',
    min: 0,
    max: 10,
    nominal: 5,
    step: 1,
    actionable: true,
    display_name: 'X',
    provenance: 'unvalidated',
    ...over,
  }
}

const payload = {
  version: 'constraints-test',
  content_hash: 'abc',
  parameters: [
    spec({ name: 'a_c', nominal: 7 }),
    spec({ name: 'lot_mfi', kind: 'lot_attribute', nominal: 12 }),
    spec({ name: 'b_s', nominal: 2.5 }),
  ],
} as unknown as Constraints

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createQueryClient()}>{children}</QueryClientProvider>
}

describe('constraints', () => {
  it('loads the registry and derives setpoints and the nominal recipe from it', async () => {
    server.use(http.get(`${API}/constraints`, () => HttpResponse.json(envelope(payload))))
    const { result } = renderHook(() => useConstraints(), { wrapper })
    await waitFor(() => expect(result.current.data).toBeDefined())
    const data = result.current.data!
    expect(data.version).toBe('constraints-test')
    expect(setpoints(data).map((p) => p.name)).toEqual(['a_c', 'b_s'])
    expect(nominalRecipe(data)).toEqual({ a_c: 7, b_s: 2.5 })
  })

  it('checks the box only against registry bounds', () => {
    const s = spec({ min: 1, max: 3 })
    expect([0.5, 1, 3, 3.5].map((v) => outOfRange(s, v))).toEqual([true, false, false, true])
  })
})
