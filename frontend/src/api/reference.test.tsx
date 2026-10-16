import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import { runState } from '@/test/fixtures/runState'
import { API, envelope, server } from '@/test/server'

import { ApiClientError } from './client'
import { useMachines } from './reference'
import { type CreateRunRequest, useCreateRun } from './runs'

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createQueryClient()}>{children}</QueryClientProvider>
}

const request = {
  machine_id: 'MC-03',
  product_id: 'PP-JBOX-42',
  material_lot_id: 'A-771',
  parameters: { melt_temp_c: 230 },
} as unknown as CreateRunRequest

describe('reference and run creation hooks', () => {
  it('loads machines', async () => {
    server.use(
      http.get(`${API}/machines`, () =>
        HttpResponse.json(envelope([{ machine_id: 'MC-03', machine_type: 'ELECTRIC' }])),
      ),
    )
    const { result } = renderHook(() => useMachines(), { wrapper })
    await waitFor(() => expect(result.current.data?.[0]?.machine_id).toBe('MC-03'))
  })

  it('creates a run and posts the request as-is', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API}/simulation/runs`, async ({ request: req }) => {
        body = await req.json()
        return HttpResponse.json(envelope(runState()), { status: 201 })
      }),
    )
    const { result } = renderHook(() => useCreateRun(), { wrapper })
    let created: unknown
    await act(async () => {
      created = await result.current.mutateAsync(request)
    })
    expect(body).toEqual(request)
    expect(created).toMatchObject({ status: 'INITIALIZED' })
  })

  it('surfaces registry 422 details to the caller', async () => {
    server.use(
      http.post(`${API}/simulation/runs`, () =>
        HttpResponse.json(
          {
            data: null,
            error: {
              code: 'PARAM_OUT_OF_RANGE',
              message: 'parameters.melt_temp_c: too high',
              field: 'parameters.melt_temp_c',
              details: [
                {
                  field: 'parameters.melt_temp_c',
                  code: 'PARAM_OUT_OF_RANGE',
                  message: 'too high',
                  limit: 295,
                  value: 300,
                },
              ],
            },
            meta: { request_id: 'req-422' },
          },
          { status: 422 },
        ),
      ),
    )
    const { result } = renderHook(() => useCreateRun(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync(request).catch(() => undefined)
    })
    await waitFor(() => expect(result.current.error).toBeInstanceOf(ApiClientError))
    const error = result.current.error as ApiClientError
    expect(error.code).toBe('PARAM_OUT_OF_RANGE')
    expect(error.details?.[0]).toMatchObject({ limit: 295, value: 300 })
  })
})
